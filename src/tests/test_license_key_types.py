import unittest

from src.core.license_manager import LicenseManager


class LicenseKeyTypesTests(unittest.TestCase):
    def build_manager(self, key_data, license_data=None, patch_result=True):
        manager = LicenseManager.__new__(LicenseManager)
        manager.chassi = "MAQUINA-TESTE"
        manager._last_db_error = None
        manager.patches = []

        def db_get(path):
            manager._last_db_error = None
            if path.startswith("chaves/"):
                return dict(key_data)
            if path == "licencas/MAQUINA-TESTE":
                return dict(license_data or {})
            return None

        def db_patch(path, data):
            manager.patches.append((path, dict(data)))
            return patch_result

        manager._db_get = db_get
        manager._db_patch = db_patch
        return manager

    def test_chave_expirada_nao_altera_licenca(self):
        manager = self.build_manager({
            "status": "nova",
            "tipo": "mensagens",
            "quantidade": 30,
            "data_expiracao_chave": "2000-01-01 12:00:00",
        })

        resultado = manager.ativar_chave("MSG-30-TESTE")

        self.assertFalse(resultado["sucesso"])
        self.assertIn("expirou", resultado["mensagem"])
        self.assertEqual(manager.patches[0][0], "chaves/MSG-30-TESTE")
        self.assertEqual(manager.patches[0][1]["status"], "expirada")

    def test_data_vencimento_preserva_validade_mais_distante(self):
        manager = self.build_manager(
            {
                "status": "nova",
                "tipo": "data_vencimento",
                "data_vencimento": "2099-06-30 22:00:00",
                "data_expiracao_chave": "2099-01-01 00:00:00",
                "concessionaria": "Empresa Teste",
            },
            {"data_expiracao": "2100-12-31 22:00:00"}
        )

        resultado = manager.ativar_chave("VCT-20990630-TESTE")

        self.assertTrue(resultado["sucesso"])
        path, updates = manager.patches[0]
        self.assertEqual(path, "")
        self.assertEqual(
            updates["licencas/MAQUINA-TESTE/data_expiracao"],
            "2100-12-31 22:00:00"
        )
        self.assertEqual(updates["chaves/VCT-20990630-TESTE/status"], "usada")

    def test_data_vencimento_estende_licenca_mais_curta(self):
        manager = self.build_manager(
            {
                "status": "nova",
                "tipo": "data_vencimento",
                "data_vencimento": "2099-06-30",
                "data_expiracao_chave": "2099-01-01 00:00:00",
            },
            {"data_expiracao": "2026-08-31 22:00:00"}
        )

        resultado = manager.ativar_chave("VCT-20990630-TESTE")

        self.assertTrue(resultado["sucesso"])
        self.assertEqual(
            manager.patches[0][1]["licencas/MAQUINA-TESTE/data_expiracao"],
            "2099-06-30 22:00:00"
        )

    def test_falha_atomica_nao_confirma_consumo(self):
        manager = self.build_manager(
            {
                "status": "nova",
                "tipo": "dias",
                "dias": 30,
                "data_expiracao_chave": "2099-01-01 00:00:00",
            },
            {"data_expiracao": "2026-08-31 22:00:00"},
            patch_result=False
        )

        resultado = manager.ativar_chave("PRO-30-TESTE")

        self.assertFalse(resultado["sucesso"])
        self.assertIn("não foi consumida", resultado["mensagem"])

    def test_chave_antiga_sem_prazo_continua_compativel(self):
        manager = self.build_manager(
            {"status": "nova", "tipo": "dias", "dias": 15},
            {"data_expiracao": "2026-08-31 22:00:00"}
        )

        resultado = manager.ativar_chave("PRO-15-LEGADA")

        self.assertTrue(resultado["sucesso"])
        self.assertEqual(
            manager.patches[0][1]["chaves/PRO-15-LEGADA/status"],
            "usada"
        )


if __name__ == "__main__":
    unittest.main()
