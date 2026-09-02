"""Autenticação de usuários da versão 2.0.

Somente tokens de sessão são persistidos, protegidos pelo DPAPI do Windows.
Senhas e códigos recebidos por e-mail nunca são gravados localmente.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional

from src.core.paths import get_base_dir
from src.core.supabase_desktop import (
    DesktopBackendError,
    SUPABASE_PUBLISHABLE_KEY,
    SUPABASE_URL,
    _dpapi_transform,
)


ACCOUNT_API_PATH = "/functions/v1/account-api"


@dataclass
class UserSession:
    access_token: str
    refresh_token: str
    expires_at: int
    user_id: str


class SupabaseUserClient:
    def __init__(self, timeout: int = 20):
        self.timeout = timeout
        data_dir = os.path.join(get_base_dir(), "app_data")
        os.makedirs(data_dir, exist_ok=True)
        self.session_path = os.path.join(data_dir, "supabase_user.dat")

    @staticmethod
    def _normalized_email(email: str) -> str:
        return str(email or "").strip().lower()

    def _post(self, url: str, payload: Dict[str, Any], bearer: str = "") -> Dict[str, Any]:
        headers = {
            "apikey": SUPABASE_PUBLISHABLE_KEY,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Client-Info": "saas-assistente-desktop/2.0",
        }
        if bearer:
            headers["Authorization"] = f"Bearer {bearer}"
        request = urllib.request.Request(
            url,
            method="POST",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
        )
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
            code = str(
                body.get("error_code") or body.get("code") or body.get("error")
                or body.get("msg") or "HTTP_ERROR"
            )
            raise DesktopBackendError(code.upper(), error.code) from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise DesktopBackendError("NETWORK_ERROR") from error

    def _session_from_response(self, response: Dict[str, Any]) -> UserSession:
        access_token = str(response.get("access_token") or "")
        refresh_token = str(response.get("refresh_token") or "")
        user = dict(response.get("user") or {})
        expires_in = int(response.get("expires_in") or 3600)
        # Os tokens do GoTrue sao opacos e seu tamanho pode mudar entre versoes.
        # A autenticidade do access token e validada pelo Supabase em cada chamada;
        # aqui basta exigir que os campos obrigatorios tenham sido devolvidos.
        if not access_token or not refresh_token or not user.get("id"):
            raise DesktopBackendError("INVALID_SERVER_RESPONSE")
        session = UserSession(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=int(time.time()) + max(60, expires_in),
            user_id=str(user["id"]),
        )
        self._save_session(session)
        return session

    def _save_session(self, session: UserSession) -> None:
        payload = json.dumps({
            "version": 1,
            "access_token": session.access_token,
            "refresh_token": session.refresh_token,
            "expires_at": session.expires_at,
            "user_id": session.user_id,
        }).encode("utf-8")
        protected = _dpapi_transform(payload)
        temporary = self.session_path + ".tmp"
        with open(temporary, "wb") as file:
            file.write(protected)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, self.session_path)

    def load_session(self) -> Optional[UserSession]:
        try:
            with open(self.session_path, "rb") as file:
                payload = json.loads(
                    _dpapi_transform(file.read(), decrypt=True).decode("utf-8")
                )
            session = UserSession(
                access_token=str(payload.get("access_token") or ""),
                refresh_token=str(payload.get("refresh_token") or ""),
                expires_at=int(payload.get("expires_at") or 0),
                user_id=str(payload.get("user_id") or ""),
            )
            if not session.access_token or not session.refresh_token or not session.user_id:
                return None
            return session
        except (OSError, ValueError, TypeError, json.JSONDecodeError, DesktopBackendError):
            return None

    def clear_session(self) -> None:
        try:
            os.remove(self.session_path)
        except FileNotFoundError:
            pass

    def sign_up(self, email: str, password: str) -> Dict[str, Any]:
        email = self._normalized_email(email)
        if len(password) < 8:
            raise DesktopBackendError("WEAK_PASSWORD")
        response = self._post(
            f"{SUPABASE_URL}/auth/v1/signup",
            {"email": email, "password": password},
        )
        if response.get("access_token"):
            self._session_from_response(response)
        return response

    def verify_signup(self, email: str, code: str) -> UserSession:
        response = self._post(
            f"{SUPABASE_URL}/auth/v1/verify",
            {
                "email": self._normalized_email(email),
                "token": "".join(filter(str.isdigit, str(code))),
                "type": "signup",
            },
        )
        return self._session_from_response(response)

    def sign_in(self, email: str, password: str) -> UserSession:
        response = self._post(
            f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
            {"email": self._normalized_email(email), "password": password},
        )
        return self._session_from_response(response)

    def refresh_session(self, refresh_token: str = "") -> UserSession:
        current = self.load_session()
        token = refresh_token or (current.refresh_token if current else "")
        if not token:
            raise DesktopBackendError("USER_SESSION_REQUIRED")
        response = self._post(
            f"{SUPABASE_URL}/auth/v1/token?grant_type=refresh_token",
            {"refresh_token": token},
        )
        return self._session_from_response(response)

    def active_session(self) -> UserSession:
        session = self.load_session()
        if not session:
            raise DesktopBackendError("USER_SESSION_REQUIRED", 401)
        if session.expires_at <= int(time.time()) + 60:
            return self.refresh_session(session.refresh_token)
        return session

    def request_password_recovery(self, email: str) -> None:
        self._post(
            f"{SUPABASE_URL}/auth/v1/recover",
            {"email": self._normalized_email(email)},
        )

    def account_request(self, action: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        session = self.active_session()
        return self._post(
            f"{SUPABASE_URL}{ACCOUNT_API_PATH}",
            {"action": action, **(payload or {})},
            bearer=session.access_token,
        )

    def create_company_trial(
        self,
        company_name: str,
        owner_name: str,
        phone: str,
        cnpj: str,
        hardware_id: str,
        app_version: str,
    ) -> Dict[str, Any]:
        return self.account_request("create_company_trial", {
            "company_name": str(company_name).strip(),
            "owner_name": str(owner_name).strip(),
            "phone": "".join(filter(str.isdigit, str(phone))),
            "cnpj": "".join(filter(str.isdigit, str(cnpj))),
            "hardware_id": str(hardware_id).strip(),
            "app_version": str(app_version).strip(),
        })
