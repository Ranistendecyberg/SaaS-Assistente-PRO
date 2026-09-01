import io
import json
import unittest
import urllib.error
from unittest.mock import patch

from admin_supabase import AdminSupabaseClient, SupabaseAuthError


class Response:
    def __init__(self, data):
        self.data = json.dumps(data).encode("utf-8")
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self): return self.data


class AdminSupabaseClientTests(unittest.TestCase):
    def test_sign_in_nao_armazena_senha(self):
        with patch("urllib.request.urlopen", return_value=Response({"access_token": "token", "refresh_token": "refresh", "user": {"id": "u1"}})):
            session = AdminSupabaseClient().sign_in("Admin@Example.com", "segredo")
        self.assertEqual(session.access_token, "token")
        self.assertFalse(hasattr(session, "password"))

    def test_filtra_somente_totp_verificado(self):
        factors = [{"id": "1", "factor_type": "totp", "status": "unverified"}, {"id": "2", "factor_type": "phone", "status": "verified"}, {"id": "3", "factor_type": "totp", "status": "verified"}]
        with patch("urllib.request.urlopen", return_value=Response({"factors": factors})):
            result = AdminSupabaseClient().verified_totp_factors("token")
        self.assertEqual([item["id"] for item in result], ["3"])

    def test_erro_http_estruturado(self):
        error = urllib.error.HTTPError("url", 401, "unauthorized", {}, io.BytesIO(b'{"code":"invalid_credentials","msg":"bad"}'))
        with patch("urllib.request.urlopen", side_effect=error), self.assertRaises(SupabaseAuthError) as raised:
            AdminSupabaseClient().sign_in("a@b.com", "x")
        self.assertEqual(raised.exception.status, 401)
        self.assertEqual(raised.exception.code, "invalid_credentials")


if __name__ == "__main__": unittest.main()
