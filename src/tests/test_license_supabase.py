import datetime
import unittest

from src.core.license_manager import LicenseManager
from src.core.supabase_desktop import DesktopBackendError


class FakeBackend:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error

    def has_session(self):
        return True

    def license_status(self, _version):
        if self.error:
            raise self.error
        return self.response


def manager_with(backend):
    manager = LicenseManager.__new__(LicenseManager)
    manager.chassi = "HARDWARE-123456"
    manager.secure_backend = backend
    manager._last_license_data = {}
    manager._last_system_config = {}
    manager._obter_versao_atual = lambda: "2.0.0"
    manager._registrar_erro_conexao = lambda _error: None
    return manager


class SupabaseLicenseTests(unittest.TestCase):
    def test_converte_contrato_seguro_para_tela_legada(self):
        expiry = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=10)).isoformat()
        backend = FakeBackend({
            "license": {
                "status": "active", "license_type": "subscription",
                "expires_at": expiry, "extra_messages": 4, "monthly_price": 250,
            },
            "company": {"name": "Loja Teste", "manager_name": "Gestor", "phone": "99999999999"},
            "usage": {"messages_used": 3, "daily_limit": 30},
            "system": {"current_version": "2.0.0"},
        })
        result = manager_with(backend).validar_licenca()
        self.assertEqual(result["status"], "ativa")
        self.assertEqual(result["concessionaria"], "Loja Teste")
        self.assertEqual(result["enviadas_hoje"], 3)
        self.assertEqual(result["mensagens_extras"], 4)

    def test_indisponibilidade_nao_vira_migracao(self):
        result = manager_with(FakeBackend(error=DesktopBackendError("NETWORK_ERROR"))).validar_licenca()
        self.assertEqual(result["status"], "erro_conexao")


if __name__ == "__main__":
    unittest.main()
