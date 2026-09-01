"""Cliente mínimo do Supabase Auth usado pelo gerador_admin."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional

SUPABASE_URL = "https://hnwvtoiiuqagzmuqygkw.supabase.co"
SUPABASE_PUBLISHABLE_KEY = "sb_publishable_B9FIBJ6QvRZ691rGqN5Drw_W-GOXmsI"


class SupabaseAuthError(RuntimeError):
    def __init__(self, message: str, status: int = 0, code: str = ""):
        super().__init__(message)
        self.status = status
        self.code = code


@dataclass
class AdminSession:
    access_token: str
    refresh_token: str
    user: Dict[str, Any]


class AdminSupabaseClient:
    def __init__(self, timeout: int = 20):
        self.timeout = timeout

    def _request(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None, token: str = "") -> Dict[str, Any]:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {
            "apikey": SUPABASE_PUBLISHABLE_KEY,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Client-Info": "saas-desktop-admin/2.0",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(f"{SUPABASE_URL}{path}", method=method, data=data, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as error:
            raw = error.read().decode("utf-8", errors="replace")
            try:
                body = json.loads(raw)
            except json.JSONDecodeError:
                body = {}
            message = body.get("msg") or body.get("message") or body.get("error_description") or body.get("error") or f"Falha HTTP {error.code}"
            code = str(body.get("code") or body.get("error_code") or "")
            raise SupabaseAuthError(str(message), error.code, code) from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise SupabaseAuthError("Não foi possível conectar ao servidor de autenticação.", 0, "network_error") from error

    def sign_in(self, email: str, password: str) -> AdminSession:
        result = self._request("POST", "/auth/v1/token?grant_type=password", {"email": email.strip().lower(), "password": password})
        token = str(result.get("access_token") or "")
        if not token:
            raise SupabaseAuthError("O servidor não retornou uma sessão válida.")
        return AdminSession(token, str(result.get("refresh_token") or ""), dict(result.get("user") or {}))

    def get_user(self, token: str) -> Dict[str, Any]:
        return self._request("GET", "/auth/v1/user", token=token)

    def verified_totp_factors(self, token: str):
        user = self.get_user(token)
        return [factor for factor in (user.get("factors") or []) if factor.get("factor_type") == "totp" and factor.get("status") == "verified"]

    def remove_unverified_factors(self, token: str) -> None:
        user = self.get_user(token)
        for factor in user.get("factors") or []:
            if factor.get("status") == "unverified" and factor.get("id"):
                try:
                    self._request("DELETE", f"/auth/v1/factors/{factor['id']}", token=token)
                except SupabaseAuthError:
                    pass

    def enroll_totp(self, token: str) -> Dict[str, Any]:
        self.remove_unverified_factors(token)
        return self._request("POST", "/auth/v1/factors", {
            "factor_type": "totp",
            "friendly_name": "Gerador Admin - Computador Principal",
            "issuer": "SaaS Assistente Desktop",
        }, token=token)

    def challenge_and_verify(self, token: str, factor_id: str, code: str) -> AdminSession:
        challenge = self._request("POST", f"/auth/v1/factors/{factor_id}/challenge", {}, token=token)
        challenge_id = str(challenge.get("id") or "")
        if not challenge_id:
            raise SupabaseAuthError("Não foi possível iniciar a verificação MFA.")
        verified = self._request("POST", f"/auth/v1/factors/{factor_id}/verify", {"challenge_id": challenge_id, "code": code}, token=token)
        access_token = str(verified.get("access_token") or "")
        if not access_token:
            raise SupabaseAuthError("O código não gerou uma sessão MFA válida.")
        return AdminSession(access_token, str(verified.get("refresh_token") or ""), dict(verified.get("user") or {}))

    def confirm_admin_access(self, token: str) -> Dict[str, Any]:
        return self._request("POST", "/functions/v1/admin-api", {"action": "list_installations"}, token=token)

    def admin_request(self, token: str, action: str, **payload) -> Dict[str, Any]:
        return self._request(
            "POST", "/functions/v1/admin-api", {"action": action, **payload}, token=token
        )

    def issue_migration_claim(self, token: str, hardware_id: str) -> Dict[str, Any]:
        return self.admin_request(
            token, "issue_migration_claim", hardware_id=str(hardware_id).strip()
        )

    def import_legacy_snapshot(self, token: str, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        payload = {"action": "import_legacy_snapshot", **snapshot}
        return self._request("POST", "/functions/v1/admin-api", payload, token=token)


def friendly_auth_error(error: Exception) -> str:
    if not isinstance(error, SupabaseAuthError):
        return "Não foi possível concluir a autenticação."
    if error.code in {"invalid_credentials", "invalid_grant"} or error.status == 400:
        return "E-mail ou senha incorretos."
    if error.code == "mfa_verification_failed" or error.status == 422:
        return "Código do autenticador inválido ou expirado."
    if error.status == 401:
        return "Sessão de acesso inválida. Entre novamente."
    if error.status == 403:
        return "Este usuário não possui permissão administrativa ativa."
    if error.status == 428:
        return "A verificação em duas etapas é obrigatória."
    messages = {
        "KEY_ALREADY_USED": "Esta chave já foi utilizada. Corrija o benefício diretamente na licença da máquina.",
        "KEY_ALREADY_REVOKED": "Esta chave já foi revogada.",
        "KEY_EXPIRED": "Esta chave já expirou e não pode mais ser utilizada.",
        "KEY_NOT_FOUND": "A chave selecionada não foi encontrada. Atualize os dados e tente novamente.",
        "KEY_NOT_REVOCABLE": "Esta chave não está disponível para revogação.",
    }
    if str(error) in messages:
        return messages[str(error)]
    return str(error)
