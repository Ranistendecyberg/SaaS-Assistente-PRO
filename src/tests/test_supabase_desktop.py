import os
import tempfile
import unittest
from unittest.mock import patch

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
    def test_claim_salva_token_sem_gravar_codigo(self, _transform):
        token = "a" * 64
        with patch.object(self.client, "_request", return_value={"installation_token": token}):
            self.client.claim_legacy_installation("MIG-SEGREDO")
        session = self.client.load_session()
        self.assertEqual(session.token, token)
        with open(self.client.session_path, "rb") as file:
            stored = file.read().decode("utf-8")
        self.assertNotIn("MIG-SEGREDO", stored)

    @patch("src.core.supabase_desktop._dpapi_transform", side_effect=lambda data, decrypt=False: data)
    def test_sessao_de_outro_hardware_e_rejeitada(self, _transform):
        self.client._save_session("b" * 64)
        other = SupabaseDesktopClient.__new__(SupabaseDesktopClient)
        other.hardware_id = "OUTRO-HARDWARE-9"
        other.timeout = 15
        other.session_path = self.client.session_path
        self.assertIsNone(other.load_session())

    def test_resposta_sem_token_nao_cria_sessao(self):
        with patch.object(self.client, "_request", return_value={"ok": True}):
            with self.assertRaises(DesktopBackendError):
                self.client.claim_legacy_installation("MIG-INVALIDO")
        self.assertFalse(os.path.exists(self.client.session_path))

    def test_bootstrap_distingue_computador_novo(self):
        with patch.object(self.client, "_request", return_value={"mode": "new"}) as request:
            self.assertEqual(self.client.bootstrap_mode(), "new")
        request.assert_called_once_with("bootstrap_mode", require_session=False)

    @patch("src.core.supabase_desktop._dpapi_transform", side_effect=lambda data, decrypt=False: data)
    def test_cadastro_novo_salva_token_e_dados_nao_ficam_na_sessao(self, _transform):
        token = "c" * 64
        with patch.object(self.client, "_request", return_value={"installation_token": token}):
            self.client.register_new_installation(
                "Loja Teste", "Responsável", "86999999999"
            )
        self.assertEqual(self.client.load_session().token, token)
        with open(self.client.session_path, "rb") as file:
            stored = file.read().decode("utf-8")
        self.assertNotIn("Loja Teste", stored)

    def test_pix_e_sempre_operado_pela_api_segura(self):
        with patch.object(self.client, "_request", return_value={"ok": True, "payment_id": "123"}) as request:
            result = self.client.create_pix()
        self.assertEqual(result["payment_id"], "123")
        request.assert_called_once_with("create_pix")

    def test_consulta_pix_vincula_identificador_a_instalacao(self):
        with patch.object(self.client, "_request", return_value={"ok": True, "aprovado": False}) as request:
            self.client.check_pix("PAYMENT-ABC")
        request.assert_called_once_with("check_pix", {"payment_id": "PAYMENT-ABC"})


if __name__ == "__main__":
    unittest.main()
