"""Proteção centralizada para recursos internos de suporte.

O segredo local nunca é suficiente sozinho: o computador também precisa ter
uma autorização de diagnóstico vigente, emitida pelo backend e limitada no
tempo. As tentativas são comparadas em tempo constante e limitadas por sessão.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import threading
import time

from src.core.telemetry import record_event


class DeveloperAccessGuard:
    _SALT = b"SaaS-Assistente-PRO-dev-v2"
    _ITERATIONS = 310_000
    _PASSWORD_DIGEST = bytes.fromhex(
        "af5444c28d60c9f306a25830fdcfe9136e3fd8bc650ed8bb84d4c61737564ad4"
    )
    _MAX_FAILURES = 5
    _LOCK_SECONDS = 15 * 60
    _failures = 0
    _blocked_until = 0.0
    _authorization_cache = (0.0, False, "")
    _lock = threading.Lock()

    @classmethod
    def authorization_status(cls, force=False):
        """Confirma no servidor se este computador recebeu acesso temporário."""
        now = time.monotonic()
        cached_at, allowed, reason = cls._authorization_cache
        if not force and cached_at and now - cached_at < 60:
            return allowed, reason
        try:
            from src.core.license_manager import LicenseManager

            data = LicenseManager.get_instance().validar_licenca()
            value = data.get("diagnostico_detalhado_ate")
            if data.get("status") not in {"ativa", "trial"} or not value:
                allowed, reason = False, "DIAGNOSTIC_AUTHORIZATION_REQUIRED"
                cls._authorization_cache = (now, allowed, reason)
                return allowed, reason
            expires = dt.datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=dt.timezone.utc)
            allowed = expires > dt.datetime.now(dt.timezone.utc)
            reason = "" if allowed else "DIAGNOSTIC_AUTHORIZATION_REQUIRED"
        except Exception:
            allowed, reason = False, "DIAGNOSTIC_AUTHORIZATION_UNAVAILABLE"
        cls._authorization_cache = (now, allowed, reason)
        return allowed, reason

    @classmethod
    def remaining_lock_seconds(cls):
        return max(0, int(cls._blocked_until - time.monotonic() + 0.999))

    @classmethod
    def verify_password(cls, password):
        """Valida o segredo com PBKDF2 e aplica bloqueio progressivo da sessão."""
        with cls._lock:
            remaining = cls.remaining_lock_seconds()
            if remaining:
                record_event("developer_access", "ACCESS_BLOCKED", "WARN", remaining_seconds=remaining)
                return False, "BLOCKED"
            candidate = hashlib.pbkdf2_hmac(
                "sha256", str(password or "").encode("utf-8"), cls._SALT, cls._ITERATIONS
            )
            if hmac.compare_digest(candidate, cls._PASSWORD_DIGEST):
                cls._failures = 0
                record_event("developer_access", "ACCESS_GRANTED")
                return True, "OK"
            cls._failures += 1
            remaining_attempts = cls._MAX_FAILURES - cls._failures
            if remaining_attempts <= 0:
                cls._failures = 0
                cls._blocked_until = time.monotonic() + cls._LOCK_SECONDS
                record_event("developer_access", "ACCESS_LOCKED", "WARN")
                return False, "LOCKED"
            record_event(
                "developer_access", "ACCESS_DENIED", "WARN",
                remaining_attempts=remaining_attempts,
            )
            return False, f"INVALID:{remaining_attempts}"
