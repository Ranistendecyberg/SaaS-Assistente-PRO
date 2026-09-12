import os
import tempfile
import unittest
from unittest.mock import patch

from src.core.supabase_auth import (
    PasswordRecoverySession,
    SupabaseUserClient,
    UserSession,
)
from src.core.supabase_desktop import DesktopBackendError


class SupabaseUserClientTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.client = SupabaseUserClient.__new__(SupabaseUserClient)
        self.client.timeout = 15
        self.client.session_path = os.path.join(self.temp.name, "user.dat")

    def tearDown(self):
        self.temp.cleanup()

    def test_signup_sends_password_only_to_supabase_auth_and_does_not_store_it(self):
        with patch.object(self.client, "_post", return_value={"user": {"id": "pending"}}) as post:
            self.client.sign_up(" Cliente@Example.com ", "SenhaSegura123")
        self.assertFalse(os.path.exists(self.client.session_path))
        url, body = post.call_args.args
        self.assertTrue(url.endswith("/auth/v1/signup"))
        self.assertEqual(body["email"], "cliente@example.com")
        self.assertEqual(body["password"], "SenhaSegura123")

    @patch("src.core.supabase_auth._dpapi_transform", side_effect=lambda data, decrypt=False: data)
    def test_signup_code_creates_protected_user_session(self, _transform):
        response = {
            "access_token": "a" * 80,
            "refresh_token": "r" * 40,
            "expires_in": 3600,
            "user": {"id": "user-123"},
        }
        with patch.object(self.client, "_post", return_value=response) as post:
            session = self.client.verify_signup("cliente@example.com", "123 456")
        self.assertEqual(session.user_id, "user-123")
        self.assertEqual(self.client.load_session().refresh_token, "r" * 40)
        self.assertEqual(post.call_args.args[1]["token"], "123456")
        with open(self.client.session_path, "rb") as file:
            stored = file.read().decode("utf-8")
        self.assertNotIn("123456", stored)
        self.assertNotIn("cliente@example.com", stored)

    @patch("src.core.supabase_auth._dpapi_transform", side_effect=lambda data, decrypt=False: data)
    def test_session_accepts_opaque_refresh_token_without_assuming_its_length(self, _transform):
        response = {
            "access_token": "signed-access-token",
            "refresh_token": "opaque",
            "expires_in": 3600,
            "user": {"id": "user-123"},
        }
        session = self.client._session_from_response(response)
        self.assertEqual(session.refresh_token, "opaque")
        self.assertEqual(self.client.load_session().refresh_token, "opaque")

    def test_company_trial_uses_authenticated_account_api(self):
        expected = {"ok": True, "installation_token": "x" * 64}
        with patch.object(self.client, "account_request", return_value=expected) as request:
            result = self.client.create_company_trial(
                "Grupo Teste", "Responsável", "(86) 99999-9999",
                "04.252.011/0001-10", "HARDWARE-123456", "2.0.0",
            )
        self.assertEqual(result, expected)
        action, payload = request.call_args.args
        self.assertEqual(action, "create_company_trial")
        self.assertEqual(payload["cnpj"], "04252011000110")
        self.assertEqual(payload["phone"], "86999999999")

    def test_operation_confirmation_sends_otp_only_to_current_user_email(self):
        session = UserSession("access", "refresh", 9999999999, "user-123")
        with patch.object(self.client, "active_session", return_value=session), \
                patch.object(self.client, "_get", return_value={
                    "id": "user-123", "email": " Cliente@Example.com ",
                }) as get, patch.object(self.client, "_post", return_value={}) as post:
            email = self.client.request_operation_confirmation()
        self.assertEqual(email, "cliente@example.com")
        self.assertEqual(get.call_args.kwargs["bearer"], "access")
        self.assertTrue(post.call_args.args[0].endswith("/auth/v1/otp"))
        self.assertEqual(post.call_args.args[1], {
            "email": "cliente@example.com", "create_user": False,
        })

    def test_operation_confirmation_code_replaces_only_same_user_session(self):
        current = UserSession("password", "refresh", 9999999999, "user-123")
        renewed = UserSession("otp", "new-refresh", 9999999999, "user-123")
        response = {
            "access_token": "otp", "refresh_token": "new-refresh",
            "user": {"id": "user-123", "email": "cliente@example.com"},
        }
        with patch.object(self.client, "active_session", return_value=current), \
                patch.object(self.client, "_post", return_value=response) as post, \
                patch.object(
                    self.client, "_session_from_response", return_value=renewed,
                ) as persist:
            result = self.client.verify_operation_confirmation(
                " Cliente@Example.com ", "12 34 56 78",
            )
        self.assertEqual(result, renewed)
        self.assertEqual(post.call_args.args[1], {
            "email": "cliente@example.com", "token": "12345678", "type": "email",
        })
        persist.assert_called_once_with(response)

    def test_operation_confirmation_rejects_identity_switch_before_persisting(self):
        current = UserSession("password", "refresh", 9999999999, "user-123")
        response = {
            "access_token": "otp", "refresh_token": "new-refresh",
            "user": {"id": "other-user", "email": "cliente@example.com"},
        }
        with patch.object(self.client, "active_session", return_value=current), \
                patch.object(self.client, "_post", return_value=response), \
                patch.object(self.client, "_session_from_response") as persist:
            with self.assertRaises(DesktopBackendError) as caught:
                self.client.verify_operation_confirmation(
                    "cliente@example.com", "12345678",
                )
        self.assertEqual(caught.exception.code, "EMAIL_OTP_IDENTITY_MISMATCH")
        persist.assert_not_called()

    def test_enterprise_helpers_keep_company_scope_on_server_requests(self):
        with patch.object(self.client, "account_request", return_value={"ok": True}) as request:
            self.client.account_summary("company-1")
            request.assert_called_with("account_summary", {"company_id": "company-1"})

            self.client.issue_device_link_code("company-1", "unit-1")
            request.assert_called_with("issue_device_link_code", {
                "company_id": "company-1", "business_unit_id": "unit-1",
            })

            self.client.schedule_device_removal("company-1", "installation-1")
            request.assert_called_with("schedule_device_removal", {
                "company_id": "company-1", "installation_id": "installation-1",
            })

    def test_billing_helpers_use_dedicated_authenticated_api(self):
        with patch.object(self.client, "billing_request", return_value={"ok": True}) as request:
            self.client.billing_summary("company-1")
            request.assert_called_with("billing_summary", {"company_id": "company-1"})

            self.client.create_company_payment("company-1", "PIX")
            request.assert_called_with("create_payment", {
                "company_id": "company-1", "payment_method": "pix",
            })

            self.client.save_billing_profile("company-1", {
                "legal_name": "Grupo Teste Ltda", "billing_cnpj": "123",
                "ignored_secret": "never-send",
            })
            payload = request.call_args.args[1]
            self.assertEqual(request.call_args.args[0], "save_billing_profile")
            self.assertNotIn("ignored_secret", payload)

    def test_mfa_factors_only_expose_verified_totp_for_challenge(self):
        session = UserSession("access", "refresh", 9999999999, "user-123")
        response = {"factors": [
            {"id": "verified", "factor_type": "totp", "status": "verified"},
            {"id": "pending", "factor_type": "totp", "status": "unverified"},
            {"id": "phone", "factor_type": "phone", "status": "verified"},
        ]}
        with patch.object(self.client, "active_session", return_value=session), \
                patch.object(self.client, "_get", return_value=response) as get:
            factors = self.client.list_mfa_factors()
        self.assertEqual([row["id"] for row in factors["totp"]], ["verified"])
        self.assertEqual(len(factors["all"]), 3)
        self.assertEqual(get.call_args.kwargs["bearer"], "access")

    def test_password_recovery_code_returns_transient_token_without_persisting_session(self):
        response = {"access_token": "recovery-access", "user": {"id": "user-123"}}
        with patch.object(self.client, "_post", return_value=response) as post, \
                patch.object(self.client, "_get", return_value={"factors": []}):
            recovery = self.client.verify_password_recovery(" Cliente@Example.com ", "123 456")
        self.assertEqual(recovery.access_token, "recovery-access")
        self.assertEqual(recovery.totp_factors, [])
        self.assertFalse(os.path.exists(self.client.session_path))
        self.assertEqual(post.call_args.args[1], {
            "email": "cliente@example.com", "token": "123456", "type": "recovery",
        })

    def test_password_recovery_accepts_eight_digit_email_otp(self):
        response = {"access_token": "recovery-access", "user": {"id": "user-123"}}
        with patch.object(self.client, "_post", return_value=response) as post, \
                patch.object(self.client, "_get", return_value={"factors": []}):
            recovery = self.client.verify_password_recovery(
                "cliente@example.com", "12 34 56 78"
            )
        self.assertEqual(recovery.access_token, "recovery-access")
        self.assertEqual(post.call_args.args[1]["token"], "12345678")

    def test_recovery_totp_elevates_only_transient_session(self):
        factor_id = "34e770dd-9ff9-416c-87fa-43b31d7ef225"
        recovery = PasswordRecoverySession(
            "aal1-token", "user-123", [{"id": factor_id}],
        )
        responses = [
            {"id": "challenge-1"},
            {"access_token": "aal2-token", "user": {"id": "user-123"}},
        ]
        with patch.object(self.client, "_post", side_effect=responses) as post:
            token = self.client.verify_recovery_totp(recovery, factor_id, "123 456")
        self.assertEqual(token, "aal2-token")
        self.assertEqual(post.call_args_list[0].kwargs["bearer"], "aal1-token")
        self.assertEqual(post.call_args_list[1].args[1]["code"], "123456")
        self.assertFalse(os.path.exists(self.client.session_path))

    def test_recovered_password_uses_temporary_bearer_and_clears_local_session(self):
        with patch.object(self.client, "_request", return_value={"id": "user-123"}) as request, \
                patch.object(self.client, "clear_session") as clear:
            self.client.update_recovered_password("temporary-token", "NovaSenha123")
        request.assert_called_once()
        self.assertEqual(request.call_args.args[:3], (
            "PUT", request.call_args.args[1], {"password": "NovaSenha123"},
        ))
        self.assertTrue(request.call_args.args[1].endswith("/auth/v1/user"))
        self.assertEqual(request.call_args.kwargs["bearer"], "temporary-token")
        clear.assert_called_once_with()

    def test_verify_totp_creates_challenge_and_persists_returned_aal2_session(self):
        factor_id = "34e770dd-9ff9-416c-87fa-43b31d7ef225"
        current = UserSession("aal1", "refresh", 9999999999, "user-123")
        renewed = UserSession("aal2", "new-refresh", 9999999999, "user-123")
        responses = [{"id": "challenge-1"}, {
            "access_token": "aal2", "refresh_token": "new-refresh",
            "expires_in": 3600, "user": {"id": "user-123"},
        }]
        with patch.object(self.client, "active_session", return_value=current), \
                patch.object(self.client, "_post", side_effect=responses) as post, \
                patch.object(self.client, "_session_from_response", return_value=renewed) as persist:
            result = self.client.verify_totp(factor_id, "123 456")
        self.assertEqual(result, renewed)
        self.assertTrue(post.call_args_list[0].args[0].endswith(f"/{factor_id}/challenge"))
        self.assertEqual(post.call_args_list[1].args[1]["code"], "123456")
        persist.assert_called_once_with(responses[1])

    @patch("src.core.supabase_auth._dpapi_transform", side_effect=lambda data, decrypt=False: data)
    def test_expired_session_is_refreshed_without_password(self, _transform):
        self.client._save_session(UserSession("a" * 80, "r" * 40, 1, "user-123"))
        renewed = UserSession("b" * 80, "s" * 40, 9999999999, "user-123")
        with patch.object(self.client, "refresh_session", return_value=renewed) as refresh:
            self.assertEqual(self.client.active_session(), renewed)
        refresh.assert_called_once_with("r" * 40)


if __name__ == "__main__":
    unittest.main()
