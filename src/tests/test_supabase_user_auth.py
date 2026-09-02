import os
import tempfile
import unittest
from unittest.mock import patch

from src.core.supabase_auth import SupabaseUserClient, UserSession


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

    @patch("src.core.supabase_auth._dpapi_transform", side_effect=lambda data, decrypt=False: data)
    def test_expired_session_is_refreshed_without_password(self, _transform):
        self.client._save_session(UserSession("a" * 80, "r" * 40, 1, "user-123"))
        renewed = UserSession("b" * 80, "s" * 40, 9999999999, "user-123")
        with patch.object(self.client, "refresh_session", return_value=renewed) as refresh:
            self.assertEqual(self.client.active_session(), renewed)
        refresh.assert_called_once_with("r" * 40)


if __name__ == "__main__":
    unittest.main()
