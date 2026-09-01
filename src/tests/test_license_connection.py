import unittest
from unittest.mock import patch

from src.core.license_manager import LicenseManager


class LicenseConnectionTests(unittest.TestCase):
    def build_manager(self):
        manager = LicenseManager.__new__(LicenseManager)
        manager.chassi = "MAQUINA-TESTE"
        manager._last_db_error = None
        manager._registrar_erro_conexao = lambda erro: None
        return manager

    @patch("src.core.license_manager.time.sleep", return_value=None)
    def test_falha_de_conexao_nao_vira_novo_cadastro(self, _sleep):
        manager = self.build_manager()
        chamadas = []

        def consulta(_caminho):
            chamadas.append(True)
            manager._last_db_error = TimeoutError("tempo excedido")
            return None

        manager._db_get = consulta

        resultado = manager.validar_licenca()

        self.assertEqual(resultado["status"], "erro_conexao")
        self.assertEqual(len(chamadas), 3)

    def test_json_nulo_confirmado_significa_nao_registrado(self):
        manager = self.build_manager()

        def consulta(_caminho):
            manager._last_db_error = None
            return None

        manager._db_get = consulta

        resultado = manager.validar_licenca()

        self.assertEqual(resultado["status"], "nao_registrado")


if __name__ == "__main__":
    unittest.main()
