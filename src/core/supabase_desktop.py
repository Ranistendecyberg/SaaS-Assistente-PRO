"""Cliente seguro do backend Supabase usado pelo aplicativo Desktop.

O aplicativo possui apenas a chave publicável do projeto. Todas as operações
sensíveis passam pela Edge Function ``desktop-api`` e exigem um token de
instalação aleatório, protegido localmente pelo DPAPI do Windows.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional

from src.core.paths import get_base_dir


SUPABASE_URL = "https://hnwvtoiiuqagzmuqygkw.supabase.co"
SUPABASE_PUBLISHABLE_KEY = "sb_publishable_B9FIBJ6QvRZ691rGqN5Drw_W-GOXmsI"
DESKTOP_API_PATH = "/functions/v1/desktop-api"


class DesktopBackendError(RuntimeError):
    def __init__(self, code: str, status: int = 0):
        super().__init__(code)
        self.code = code
        self.status = status


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_char)),
    ]


def _dpapi_transform(data: bytes, decrypt: bool = False) -> bytes:
    if os.name != "nt":
        raise DesktopBackendError("SECURE_STORAGE_UNAVAILABLE")
    source_buffer = ctypes.create_string_buffer(data)
    source = _DataBlob(len(data), ctypes.cast(source_buffer, ctypes.POINTER(ctypes.c_char)))
    target = _DataBlob()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    if decrypt:
        ok = crypt32.CryptUnprotectData(
            ctypes.byref(source), None, None, None, None, 0x01, ctypes.byref(target)
        )
    else:
        ok = crypt32.CryptProtectData(
            ctypes.byref(source), "SaaS Desktop Installation", None, None, None,
            0x01, ctypes.byref(target),
        )
    if not ok:
        raise DesktopBackendError("SECURE_STORAGE_ERROR")
    try:
        return ctypes.string_at(target.pbData, target.cbData)
    finally:
        kernel32.LocalFree(target.pbData)


@dataclass
class InstallationSession:
    hardware_id: str
    token: str


class SupabaseDesktopClient:
    def __init__(self, hardware_id: str, timeout: int = 15):
        self.hardware_id = str(hardware_id).strip()
        self.timeout = timeout
        data_dir = os.path.join(get_base_dir(), "app_data")
        os.makedirs(data_dir, exist_ok=True)
        self.session_path = os.path.join(data_dir, "supabase_installation.dat")

    def load_session(self) -> Optional[InstallationSession]:
        try:
            with open(self.session_path, "rb") as file:
                protected = file.read()
            payload = json.loads(_dpapi_transform(protected, decrypt=True).decode("utf-8"))
            if payload.get("hardware_id") != self.hardware_id:
                return None
            token = str(payload.get("token") or "")
            if len(token) < 40:
                return None
            return InstallationSession(self.hardware_id, token)
        except (OSError, ValueError, json.JSONDecodeError, DesktopBackendError):
            return None

    def has_session(self) -> bool:
        return self.load_session() is not None

    def _save_session(self, token: str) -> None:
        payload = json.dumps(
            {"version": 1, "hardware_id": self.hardware_id, "token": token},
            ensure_ascii=False,
        ).encode("utf-8")
        protected = _dpapi_transform(payload)
        temporary = self.session_path + ".tmp"
        with open(temporary, "wb") as file:
            file.write(protected)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, self.session_path)

    def _request(self, action: str, payload: Optional[Dict[str, Any]] = None,
                 require_session: bool = True) -> Dict[str, Any]:
        if not SUPABASE_PUBLISHABLE_KEY:
            raise DesktopBackendError("SERVER_CONFIGURATION_ERROR")
        body = {"action": action, "hardware_id": self.hardware_id, **(payload or {})}
        headers = {
            "apikey": SUPABASE_PUBLISHABLE_KEY,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Client-Info": "saas-assistente-desktop/2.0",
        }
        if require_session:
            session = self.load_session()
            if not session:
                raise DesktopBackendError("MIGRATION_REQUIRED", 401)
            headers["x-installation-token"] = session.token
        request = urllib.request.Request(
            f"{SUPABASE_URL}{DESKTOP_API_PATH}", method="POST",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"), headers=headers,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as error:
            raw = error.read().decode("utf-8", errors="replace")
            try:
                response = json.loads(raw)
            except json.JSONDecodeError:
                response = {}
            raise DesktopBackendError(str(response.get("error") or "HTTP_ERROR"), error.code) from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise DesktopBackendError("NETWORK_ERROR") from error

    def claim_legacy_installation(self, claim_code: str) -> Dict[str, Any]:
        result = self._request(
            "claim_legacy_installation",
            {"claim_code": str(claim_code).strip().upper()},
            require_session=False,
        )
        token = str(result.get("installation_token") or "")
        if len(token) < 40:
            raise DesktopBackendError("INVALID_SERVER_RESPONSE")
        self._save_session(token)
        return result

    def bootstrap_mode(self) -> str:
        result = self._request("bootstrap_mode", require_session=False)
        mode = str(result.get("mode") or "")
        if mode not in {"new", "legacy", "recovery_required"}:
            raise DesktopBackendError("INVALID_SERVER_RESPONSE")
        return mode

    def register_new_installation(self, company_name: str,
                                  manager_name: str, phone: str) -> Dict[str, Any]:
        result = self._request(
            "register_new_installation",
            {
                "company_name": str(company_name).strip(),
                "manager_name": str(manager_name).strip(),
                "phone": "".join(filter(str.isdigit, str(phone))),
            },
            require_session=False,
        )
        token = str(result.get("installation_token") or "")
        if len(token) < 40:
            raise DesktopBackendError("INVALID_SERVER_RESPONSE")
        self._save_session(token)
        return result

    def license_status(self, app_version: str = "") -> Dict[str, Any]:
        return self._request("license_status", {"app_version": app_version})

    def redeem_key(self, code: str) -> Dict[str, Any]:
        return self._request("redeem_key", {"code": str(code).strip().upper()})

    def consume_message(self) -> Dict[str, Any]:
        return self._request("consume_message")

    def create_pix(self) -> Dict[str, Any]:
        return self._request("create_pix")

    def check_pix(self, payment_id: str) -> Dict[str, Any]:
        return self._request("check_pix", {"payment_id": str(payment_id).strip()})

    def send_telemetry(self, events: list[dict]) -> Dict[str, Any]:
        return self._request("telemetry", {"events": events})

    def send_suggestion(self, suggestion: str) -> Dict[str, Any]:
        return self._request("suggestion", {"suggestion": suggestion})


def friendly_desktop_error(error: Exception) -> str:
    code = error.code if isinstance(error, DesktopBackendError) else "INTERNAL_ERROR"
    messages = {
        "INVALID_CLAIM": "O Código de Migração não corresponde a este computador ou já foi utilizado.",
        "CLAIM_EXPIRED": "Este Código de Migração expirou. Solicite um novo código ao suporte.",
        "NETWORK_ERROR": "Não foi possível conectar ao servidor. Verifique a internet e tente novamente.",
        "SECURE_STORAGE_UNAVAILABLE": "O armazenamento seguro do Windows não está disponível.",
        "SECURE_STORAGE_ERROR": "O Windows não conseguiu proteger o vínculo deste computador.",
        "UNAUTHORIZED": "O vínculo deste computador não é mais válido. Entre em contato com o suporte.",
        "INVALID_REGISTRATION": "Confira o nome da concessionária, responsável e telefone.",
        "INVALID_KEY": "A chave informada não existe ou já foi utilizada.",
        "KEY_EXPIRED": "Esta chave expirou antes de ser utilizada. Solicite uma nova chave.",
        "KEY_NOT_VALID_FOR_INSTALLATION": "Uma chave de mensagens extras não ativa um computador novo.",
        "KEY_COMPANY_MISMATCH": "A chave foi emitida para outra concessionária.",
        "INSTALLATION_ALREADY_EXISTS": "Este computador já possui cadastro. Entre em contato com o suporte.",
    }
    return messages.get(code, "Não foi possível concluir a migração deste computador.")
