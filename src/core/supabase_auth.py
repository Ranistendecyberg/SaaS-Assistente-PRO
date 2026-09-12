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
import uuid
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
BILLING_API_PATH = "/functions/v1/billing-api"
EMAIL_OTP_MIN_LENGTH = 6
EMAIL_OTP_MAX_LENGTH = 10


@dataclass
class UserSession:
    access_token: str
    refresh_token: str
    expires_at: int
    user_id: str


@dataclass
class PasswordRecoverySession:
    """Sessão transitória de recuperação; nunca é persistida no computador."""

    access_token: str
    user_id: str
    totp_factors: list[Dict[str, Any]]


class SupabaseUserClient:
    def __init__(self, timeout: int = 20):
        self.timeout = timeout
        data_dir = os.path.join(get_base_dir(), "app_data")
        os.makedirs(data_dir, exist_ok=True)
        self.session_path = os.path.join(data_dir, "supabase_user.dat")

    @staticmethod
    def _normalized_email(email: str) -> str:
        return str(email or "").strip().lower()

    def _request(
        self, method: str, url: str, payload: Optional[Dict[str, Any]] = None,
        bearer: str = "",
    ) -> Dict[str, Any]:
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
            method=method,
            data=(
                json.dumps(payload, ensure_ascii=False).encode("utf-8")
                if payload is not None else None
            ),
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

    def _post(self, url: str, payload: Dict[str, Any], bearer: str = "") -> Dict[str, Any]:
        return self._request("POST", url, payload, bearer)

    def _get(self, url: str, bearer: str = "") -> Dict[str, Any]:
        return self._request("GET", url, None, bearer)

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

    def request_operation_confirmation(self) -> str:
        """Envia um OTP ao e-mail da sessão sem permitir criar outra conta."""
        session = self.active_session()
        profile = self._get(
            f"{SUPABASE_URL}/auth/v1/user",
            bearer=session.access_token,
        )
        email = self._normalized_email(profile.get("email"))
        if str(profile.get("id") or "") != session.user_id or "@" not in email:
            raise DesktopBackendError("INVALID_SERVER_RESPONSE")
        self._post(
            f"{SUPABASE_URL}/auth/v1/otp",
            {"email": email, "create_user": False},
        )
        return email

    def verify_operation_confirmation(self, email: str, code: str) -> UserSession:
        """Valida o OTP e persiste somente a sessão do mesmo usuário."""
        current = self.active_session()
        normalized_email = self._normalized_email(email)
        normalized_code = "".join(filter(str.isdigit, str(code)))
        if not EMAIL_OTP_MIN_LENGTH <= len(normalized_code) <= EMAIL_OTP_MAX_LENGTH:
            raise DesktopBackendError("INVALID_EMAIL_OTP")
        response = self._post(
            f"{SUPABASE_URL}/auth/v1/verify",
            {
                "email": normalized_email,
                "token": normalized_code,
                "type": "email",
            },
        )
        user = dict(response.get("user") or {})
        if (
            str(user.get("id") or "") != current.user_id
            or self._normalized_email(user.get("email")) != normalized_email
        ):
            raise DesktopBackendError("EMAIL_OTP_IDENTITY_MISMATCH")
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

    def verify_password_recovery(self, email: str, code: str) -> PasswordRecoverySession:
        """Valida o código de recuperação sem persistir a sessão temporária."""
        normalized_code = "".join(filter(str.isdigit, str(code)))
        if not EMAIL_OTP_MIN_LENGTH <= len(normalized_code) <= EMAIL_OTP_MAX_LENGTH:
            raise DesktopBackendError("INVALID_RECOVERY_CODE")
        response = self._post(
            f"{SUPABASE_URL}/auth/v1/verify",
            {
                "email": self._normalized_email(email),
                "token": normalized_code,
                "type": "recovery",
            },
        )
        access_token = str(response.get("access_token") or "")
        user = dict(response.get("user") or {})
        if not access_token or not user.get("id"):
            raise DesktopBackendError("INVALID_SERVER_RESPONSE")
        profile = self._get(
            f"{SUPABASE_URL}/auth/v1/user",
            bearer=access_token,
        )
        factors = list(profile.get("factors") or user.get("factors") or [])
        return PasswordRecoverySession(
            access_token=access_token,
            user_id=str(user["id"]),
            totp_factors=[
                factor for factor in factors
                if factor.get("factor_type") == "totp"
                and factor.get("status") == "verified"
            ],
        )

    def verify_recovery_totp(
        self, recovery: PasswordRecoverySession, factor_id: str, code: str,
    ) -> str:
        """Eleva somente a sessão transitória de recuperação para AAL2."""
        try:
            safe_factor_id = str(uuid.UUID(str(factor_id or "").strip()))
        except (ValueError, AttributeError):
            raise DesktopBackendError("INVALID_MFA_FACTOR") from None
        normalized_code = "".join(filter(str.isdigit, str(code)))
        if len(normalized_code) != 6:
            raise DesktopBackendError("INVALID_MFA_CODE")
        challenge = self._post(
            f"{SUPABASE_URL}/auth/v1/factors/{safe_factor_id}/challenge",
            {},
            bearer=recovery.access_token,
        )
        challenge_id = str(challenge.get("id") or "")
        if not challenge_id:
            raise DesktopBackendError("INVALID_SERVER_RESPONSE")
        verified = self._post(
            f"{SUPABASE_URL}/auth/v1/factors/{safe_factor_id}/verify",
            {
                "factor_id": safe_factor_id,
                "challenge_id": challenge_id,
                "code": normalized_code,
            },
            bearer=recovery.access_token,
        )
        access_token = str(verified.get("access_token") or "")
        user = dict(verified.get("user") or {})
        if not access_token or str(user.get("id") or "") != recovery.user_id:
            raise DesktopBackendError("INVALID_SERVER_RESPONSE")
        return access_token

    def update_recovered_password(self, recovery_access_token: str, password: str) -> None:
        """Troca a senha usando exclusivamente a sessão temporária de recuperação."""
        if len(password) < 8:
            raise DesktopBackendError("WEAK_PASSWORD")
        response = self._request(
            "PUT",
            f"{SUPABASE_URL}/auth/v1/user",
            {"password": password},
            bearer=str(recovery_access_token or ""),
        )
        if not response.get("id"):
            raise DesktopBackendError("INVALID_SERVER_RESPONSE")
        self.clear_session()

    def list_mfa_factors(self) -> Dict[str, Any]:
        """Retorna os fatores MFA do usuário autenticado.

        O endpoint de usuário é a fonte oficial dos fatores vinculados. Somente
        fatores ``verified`` devem ser usados para elevar a sessão a AAL2.
        """
        session = self.active_session()
        response = self._get(
            f"{SUPABASE_URL}/auth/v1/user",
            bearer=session.access_token,
        )
        factors = list(response.get("factors") or [])
        return {
            "all": factors,
            "totp": [
                factor for factor in factors
                if factor.get("factor_type") == "totp"
                and factor.get("status") == "verified"
            ],
        }

    def enroll_totp(self, friendly_name: str = "SaaS Assistente PRO") -> Dict[str, Any]:
        session = self.active_session()
        return self._post(
            f"{SUPABASE_URL}/auth/v1/factors",
            {
                "factor_type": "totp",
                "friendly_name": str(friendly_name).strip()[:64],
                "issuer": "SaaS Assistente PRO",
            },
            bearer=session.access_token,
        )

    def verify_totp(self, factor_id: str, code: str) -> UserSession:
        """Cria e valida um desafio TOTP, persistindo a nova sessão AAL2."""
        session = self.active_session()
        factor_id = str(factor_id or "").strip()
        normalized_code = "".join(filter(str.isdigit, str(code)))
        try:
            safe_factor_id = str(uuid.UUID(factor_id))
        except (ValueError, AttributeError):
            raise DesktopBackendError("INVALID_MFA_FACTOR") from None
        if len(normalized_code) != 6:
            raise DesktopBackendError("INVALID_MFA_CODE")
        challenge = self._post(
            f"{SUPABASE_URL}/auth/v1/factors/{safe_factor_id}/challenge",
            {},
            bearer=session.access_token,
        )
        challenge_id = str(challenge.get("id") or "")
        if not challenge_id:
            raise DesktopBackendError("INVALID_SERVER_RESPONSE")
        verified = self._post(
            f"{SUPABASE_URL}/auth/v1/factors/{safe_factor_id}/verify",
            {
                "factor_id": safe_factor_id,
                "challenge_id": challenge_id,
                "code": normalized_code,
            },
            bearer=session.access_token,
        )
        return self._session_from_response(verified)

    def account_request(self, action: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        session = self.active_session()
        return self._post(
            f"{SUPABASE_URL}{ACCOUNT_API_PATH}",
            {"action": action, **(payload or {})},
            bearer=session.access_token,
        )

    def billing_request(self, action: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        session = self.active_session()
        return self._post(
            f"{SUPABASE_URL}{BILLING_API_PATH}",
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

    def list_companies(self) -> Dict[str, Any]:
        return self.account_request("list_companies")

    def recover_principal_access(self, hardware_id: str) -> Dict[str, Any]:
        return self.account_request("recover_principal_access", {"hardware_id": hardware_id})

    def account_summary(self, company_id: str) -> Dict[str, Any]:
        return self.account_request("account_summary", {
            "company_id": str(company_id).strip(),
        })

    def create_business_unit(
        self, company_id: str, display_name: str, cnpj: str,
        unit_type: str = "branch",
    ) -> Dict[str, Any]:
        return self.account_request("create_business_unit", {
            "company_id": str(company_id).strip(),
            "display_name": str(display_name).strip(),
            "cnpj": "".join(filter(str.isdigit, str(cnpj))),
            "unit_type": str(unit_type).strip(),
        })

    def issue_device_link_code(
        self, company_id: str, business_unit_id: str = "",
    ) -> Dict[str, Any]:
        return self.account_request("issue_device_link_code", {
            "company_id": str(company_id).strip(),
            "business_unit_id": str(business_unit_id).strip(),
        })

    def transfer_principal(self, new_principal_installation_id: str) -> bool:
        """Solicita a transferência da licença principal para outro computador via OTP."""
        payload = {"action": "transfer_principal", "installation_id": new_principal_installation_id}
        # account-api endpoint takes care of the mutation, we just use secure_request_v2 / account_request
        response = self.account_request("transfer_principal", payload)
        if response and response.get("ok"):
            return True
        return False

    def schedule_device_removal(
        self, company_id: str, installation_id: str,
    ) -> Dict[str, Any]:
        return self.account_request("schedule_device_removal", {
            "company_id": str(company_id).strip(),
            "installation_id": str(installation_id).strip(),
        })

    def cancel_device_removal(
        self, company_id: str, installation_id: str,
    ) -> Dict[str, Any]:
        return self.account_request("cancel_device_removal", {
            "company_id": str(company_id).strip(),
            "installation_id": str(installation_id).strip(),
        })

    def billing_summary(self, company_id: str) -> Dict[str, Any]:
        return self.billing_request("billing_summary", {
            "company_id": str(company_id).strip(),
        })

    def refresh_company_payment(self, company_id: str, attempt_id: str) -> Dict[str, Any]:
        return self.billing_request("refresh_payment_status", {
            "company_id": str(company_id).strip(),
            "attempt_id": str(attempt_id).strip(),
        })

    def save_billing_profile(self, company_id: str, profile: Dict[str, Any]) -> Dict[str, Any]:
        allowed = {
            "legal_name", "billing_cnpj", "billing_email", "postal_code",
            "street", "street_number", "address_extra", "neighborhood",
            "city", "state",
        }
        clean_profile = {key: profile.get(key, "") for key in allowed}
        return self.billing_request("save_billing_profile", {
            "company_id": str(company_id).strip(), **clean_profile,
        })

    def create_company_payment(self, company_id: str, payment_method: str) -> Dict[str, Any]:
        return self.billing_request("create_payment", {
            "company_id": str(company_id).strip(),
            "payment_method": str(payment_method).strip().lower(),
        })
