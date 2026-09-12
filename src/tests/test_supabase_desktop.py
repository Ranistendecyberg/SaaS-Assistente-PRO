import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from src.core.supabase_desktop import DesktopBackendError, SupabaseDesktopClient


class SupabaseDesktopClientTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        # Evita tocar no AppData real durante os testes.
        self.client = SupabaseDesktopClient.__new__(SupabaseDesktopClient)
        self.client.hardware_id = "HARDWARE-123456"
        self.client.timeout = 15
        self.client.session_path = os.path.join(self.temp.name, "session.dat")

    def tearDown(self):
        self.temp.cleanup()

    @patch("src.core.supabase_desktop._dpapi_transform", side_effect=lambda data, decrypt=False: data)
    def test_sessao_de_outro_hardware_e_rejeitada(self, _transform):
        self.client._save_session("b" * 64)
        other = SupabaseDesktopClient.__new__(SupabaseDesktopClient)
        other.hardware_id = "OUTRO-HARDWARE-9"
        other.timeout = 15
        other.session_path = self.client.session_path
        self.assertIsNone(other.load_session())

    @patch("src.core.supabase_desktop._dpapi_transform", side_effect=lambda data, decrypt=False: data)
    def test_vinculo_adicional_salva_somente_token_da_instalacao(self, _transform):
        token = "c" * 64
        with patch.object(
            self.client, "_request", return_value={"installation_token": token}
        ) as request:
            self.client.redeem_device_link_code("PC-ABCD-2345", "2.0.0")
        request.assert_called_once_with(
            "redeem_device_link_code",
            {"link_code": "PC-ABCD-2345", "app_version": "2.0.0"},
            require_session=False,
        )
        self.assertEqual(self.client.load_session().token, token)
        with open(self.client.session_path, "rb") as file:
            stored = file.read().decode("utf-8")
        self.assertNotIn("PC-ABCD-2345", stored)

    def test_pix_e_sempre_operado_pela_api_segura(self):
        with patch.object(self.client, "_request", return_value={"ok": True, "payment_id": "123"}) as request:
            result = self.client.create_pix()
        self.assertEqual(result["payment_id"], "123")
        request.assert_called_once_with("create_pix")

    def test_consulta_pix_vincula_identificador_a_instalacao(self):
        with patch.object(self.client, "_request", return_value={"ok": True, "aprovado": False}) as request:
            self.client.check_pix("PAYMENT-ABC")
        request.assert_called_once_with("check_pix", {"payment_id": "PAYMENT-ABC"})

    @patch("src.core.supabase_desktop.SUPABASE_PUBLISHABLE_KEY", "public-test-key")
    @patch("src.core.supabase_desktop.urllib.request.urlopen")
    def test_chamada_da_instalacao_envia_autorizacao_publicavel(self, urlopen):
        response = MagicMock()
        response.read.return_value = b'{"ok": true}'
        urlopen.return_value.__enter__.return_value = response
        with patch.object(self.client, "load_session") as session:
            session.return_value.token = "t" * 64
            self.client._request("license_status")
        request = urlopen.call_args.args[0]
        self.assertEqual(request.headers["Apikey"], "public-test-key")
        self.assertEqual(request.headers["Authorization"], "Bearer public-test-key")


if __name__ == "__main__":
    unittest.main()
