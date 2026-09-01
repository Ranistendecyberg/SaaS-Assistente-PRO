"""Telemetria técnica sanitizada, assíncrona e tolerante a falhas.

Nunca envia dados de clientes, conteúdo de páginas, tokens ou URLs completas.
Eventos que não puderem ser enviados permanecem em uma fila local limitada.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import platform
import re
import threading
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from src.core.paths import get_base_dir


SENSITIVE_KEYS = {
    "cliente", "nome", "telefone", "fone", "celular", "cpf", "cnpj",
    "mensagem", "message", "comentario", "verbalizacao", "html", "cookie",
    "token", "senha", "password", "url", "link",
}


def _machine_id() -> str:
    try:
        from src.core.license_manager import LicenseManager
        return LicenseManager().get_hardware_id()
    except Exception:
        return str(uuid.getnode())


def anonymous_id(value) -> str:
    """Identificador irreversível para correlacionar uma operação sem expô-la."""
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()[:12]


def _sanitize_text(value: str) -> str:
    text = str(value or "")
    text = re.sub(r"https?://[^\s'\"<>]+", lambda m: f"[URL:{urllib.parse.urlparse(m.group(0)).netloc or 'externa'}]", text)
    text = re.sub(r"(?<!\d)(?:\+?55)?\d{10,13}(?!\d)", "[TELEFONE_REMOVIDO]", text)
    text = re.sub(r"(?<!\d)\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?!\d)", "[CPF_REMOVIDO]", text)
    user_home = str(Path.home())
    if user_home:
        text = text.replace(user_home, "%USERPROFILE%")
    return text[:700]


def sanitize(value, key: str = ""):
    normalized_key = re.sub(r"[^a-z]", "", str(key).lower())
    if any(term in normalized_key for term in SENSITIVE_KEYS):
        return "[REMOVIDO]"
    if isinstance(value, dict):
        return {str(k)[:60]: sanitize(v, str(k)) for k, v in list(value.items())[:30]}
    if isinstance(value, (list, tuple)):
        return [sanitize(item) for item in list(value)[:30]]
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    return _sanitize_text(str(value))


class TelemetryClient:
    _instance = None
    _instance_lock = threading.Lock()

    def __init__(self):
        base = os.path.join(get_base_dir(), "app_data")
        os.makedirs(base, exist_ok=True)
        self.queue_path = os.path.join(base, "telemetry_queue.json")
        self.machine_id = _machine_id()
        self.session_id = uuid.uuid4().hex[:12]
        self._lock = threading.Lock()
        self._worker_running = False
        self._diagnostic_enabled = False
        self._diagnostic_checked_at = None
        self._diagnostic_check_running = False

    @classmethod
    def instance(cls):
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def _load_queue(self):
        try:
            with open(self.queue_path, "r", encoding="utf-8") as file:
                data = json.load(file)
                return data if isinstance(data, list) else []
        except Exception:
            return []

    def _save_queue(self, queue):
        try:
            with open(self.queue_path, "w", encoding="utf-8") as file:
                json.dump(queue[-400:], file, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def record(self, component: str, event: str, level: str = "INFO", details=None):
        now = _dt.datetime.now(_dt.timezone.utc)
        try:
            from src.version import __version__
            version = __version__
        except Exception:
            version = "desconhecida"
        payload = {
            "timestamp_utc": now.isoformat(timespec="seconds"),
            "level": str(level).upper()[:10],
            "component": _sanitize_text(component)[:60],
            "event": _sanitize_text(event)[:80],
            "session_id": self.session_id,
            "version": version,
            "environment": {
                "os": platform.system(),
                "os_release": platform.release(),
                "python": platform.python_version(),
                "frozen": bool(getattr(__import__('sys'), "frozen", False)),
            },
            "details": sanitize(details or {}),
            "diagnostic_mode": self.is_detailed_enabled(),
        }
        event_id = f"{int(now.timestamp() * 1000)}_{uuid.uuid4().hex[:7]}"
        entry = {"date": now.strftime("%Y-%m-%d"), "id": event_id, "payload": payload}
        with self._lock:
            queue = self._load_queue()
            queue.append(entry)
            self._save_queue(queue)
        self.flush_async()

    def is_detailed_enabled(self) -> bool:
        now = _dt.datetime.now(_dt.timezone.utc)
        if self._diagnostic_checked_at and (now - self._diagnostic_checked_at).total_seconds() < 300:
            return self._diagnostic_enabled
        self._diagnostic_checked_at = now
        if not self._diagnostic_check_running:
            self._diagnostic_check_running = True
            threading.Thread(target=self._refresh_diagnostic_mode, daemon=True).start()
        return self._diagnostic_enabled

    def _refresh_diagnostic_mode(self):
        try:
            now = _dt.datetime.now(_dt.timezone.utc)
            from src.core.supabase_desktop import SupabaseDesktopClient
            response = SupabaseDesktopClient(self.machine_id, timeout=5).license_status()
            value = (response.get("license") or {}).get("detailed_diagnostics_until")
            expires = _dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=_dt.timezone.utc)
            self._diagnostic_enabled = expires > now
        except Exception:
            self._diagnostic_enabled = False
        finally:
            self._diagnostic_check_running = False

    def flush_async(self):
        with self._lock:
            if self._worker_running:
                return
            self._worker_running = True
        threading.Thread(target=self._flush_worker, daemon=True).start()

    def _flush_worker(self):
        try:
            with self._lock:
                queue = self._load_queue()
            sent_ids = set()
            if queue:
                try:
                    from src.core.supabase_desktop import SupabaseDesktopClient
                    batch = queue[:100]
                    events = []
                    for entry in batch:
                        payload = dict(entry.get("payload") or {})
                        payload["occurred_at"] = payload.pop("timestamp_utc", None)
                        payload["app_version"] = payload.pop("version", None)
                        events.append(payload)
                    SupabaseDesktopClient(self.machine_id, timeout=8).send_telemetry(events)
                    sent_ids.update(entry.get("id") for entry in batch)
                except Exception:
                    pass
            with self._lock:
                current_queue = self._load_queue()
                remaining = [entry for entry in current_queue if entry.get("id") not in sent_ids]
                self._save_queue(remaining)
        finally:
            with self._lock:
                self._worker_running = False


def record_event(component: str, event: str, level: str = "INFO", **details):
    try:
        TelemetryClient.instance().record(component, event, level, details)
    except Exception:
        pass
