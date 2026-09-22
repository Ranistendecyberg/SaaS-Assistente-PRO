import datetime
import unittest
import uuid
from unittest.mock import MagicMock, patch

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
    def tearDown(self):
        LicenseManager._cached_chassi = ""

    @patch(
        "src.core.license_manager.subprocess.check_output",
        return_value=b"12345678-1234-ABCD-9876-1234567890AB\r\n",
    )
    def test_hardware_uuid_aceita_saida_de_uma_linha_do_powershell(self, check_output):
        LicenseManager._cached_chassi = ""
        manager = LicenseManager.__new__(LicenseManager)
        hardware_id = manager._obter_chassi_maquina()
        self.assertEqual(hardware_id, "12345678-1234-ABCD-9876-1234567890AB")
        self.assertFalse(check_output.call_args.kwargs["shell"])

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

    def test_reserva_confirma_e_libera_envio_por_id_idempotente(self):
        backend = MagicMock()
        backend.reserve_message.return_value = {"ok": True, "allowed": True}
        backend.confirm_message.return_value = {"ok": True, "reservation_status": "confirmed"}
        backend.release_message.return_value = {"ok": True, "reservation_status": "released"}
        manager = manager_with(backend)

        allowed, message, reservation_id = manager.reservar_envio()
        self.assertTrue(allowed)
        self.assertEqual(message, "")
        self.assertEqual(str(uuid.UUID(reservation_id)), reservation_id)
        backend.reserve_message.assert_called_once_with(reservation_id)

        self.assertEqual(manager.confirmar_envio(reservation_id), (True, ""))
        self.assertEqual(manager.liberar_reserva_envio(reservation_id), (True, ""))


if __name__ == "__main__":
    unittest.main()
