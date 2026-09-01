import unittest
from unittest.mock import patch

from supabase.migration.legacy_snapshot import build_snapshot, parse_date, safe_summary


class LegacySnapshotTests(unittest.TestCase):
    def test_data_licenca_fecha_as_22_fortaleza(self):
        self.assertEqual(parse_date("2026-08-31", True), "2026-08-31T22:00:00-03:00")

    def test_exclui_logs_e_chaves_usadas(self):
        nodes = {
            "licencas": {"HARDWARE-123": {"concessionaria": "Loja", "status": "ativa", "data_expiracao": "2026-08-31", "logs": {"x": "sensivel"}}},
            "chaves": {
                "PRO-USADA": {"status": "usada", "tipo": "dias", "dias": 30},
                "MSG-NOVA": {"status": "nova", "tipo": "mensagens", "quantidade": 10, "data_expiracao_chave": "2026-08-13 10:00:00", "concessionaria": "Loja"},
            },
            "sistema": {"versao_atual": "1.8.3", "preco_padrao": 250},
        }
        with patch("supabase.migration.legacy_snapshot.fetch", side_effect=lambda node: nodes[node]):
            snapshot = build_snapshot()
        self.assertNotIn("logs", snapshot["licenses"][0])
        self.assertEqual(snapshot["available_key"]["code"], "MSG-NOVA")
        self.assertEqual(safe_summary(snapshot)["licenses"], 1)

    def test_chave_nova_legada_sem_prazo_recebe_24_horas(self):
        nodes = {
            "licencas": {"HARDWARE-123": {"concessionaria": "Loja", "status": "ativa", "data_expiracao": "2026-08-31"}},
            "chaves": {"PRO-NOVA": {"status": "nova", "tipo": "dias", "dias": 1, "concessionaria": "Loja"}},
            "sistema": {"versao_atual": "1.8.3"},
        }
        with patch("supabase.migration.legacy_snapshot.fetch", side_effect=lambda node: nodes[node]):
            snapshot = build_snapshot()
        self.assertIsNotNone(snapshot["available_key"]["usable_until"])


if __name__ == "__main__": unittest.main()
