import os
import tempfile
import unittest
from types import SimpleNamespace

import pandas as pd

from src.core.dashboard_engine import DashboardEngine
from src.core.ssi_metrics import recommendation_summary
from src.ui.screens.dashboard_comparativo_screen import DashboardComparativoScreen


class _Combo:
    def __init__(self, text):
        self.text = text

    def currentText(self):
        return self.text


class _Database:
    def __init__(self, records=None):
        self.records = records or []

    def load_all_records(self):
        return self.records

    def get_leads_mapping(self):
        return {}

    def find_lead(self, *args, **kwargs):
        return None


class _TsiScreen:
    def _calcular_participacao_whatsapp(self, df, tipo):
        return 0, 0.0


class DashboardMetricIntegrityTests(unittest.TestCase):
    def test_missing_recommendation_is_not_a_detractor(self):
        screen = _TsiScreen()
        screen.df_tsi = pd.DataFrame({
            "Nota Pesquisa TSI": [90, 80, 70],
            "Recomendaria dealer amigo e família": [10, 6, None],
            "Avaliação satisfação geral": [10, 6, None],
            "Consultor_Nome": ["Ana", "Ana", "Ana"],
            "Loja_Nome": ["Loja", "Loja", "Loja"],
            "Mes": ["08/2026", "08/2026", "08/2026"],
        })
        screen.combo_loja = _Combo("Todas as Unidades")
        screen.combo_mes = _Combo("08/2026")
        screen.combo_consultor = _Combo("Todos")
        screen.db = _Database()
        screen.engine_tsi = SimpleNamespace(
            _normalizar_rotulo=lambda value: str(value).lower()
        )

        metrics, _, detractors, responses = (
            DashboardComparativoScreen._calcular_metricas_tsi(screen)
        )

        self.assertEqual(metrics["promotores_count"], 1)
        self.assertEqual(metrics["detratores_count"], 1)
        self.assertEqual(metrics["sem_nota_count"], 1)
        self.assertEqual(metrics["promotores_pct"], 50.0)
        self.assertEqual(metrics["detratores_pct"], 50.0)
        self.assertEqual(
            [item["status"] for item in responses],
            ["PROMOTOR", "DETRATOR", "SEM_NOTA"],
        )
        self.assertEqual(len(detractors), 1)

    def test_recommendation_summary_rejects_out_of_range_values(self):
        frame = pd.DataFrame({
            "Recomendaria dealer amigo e familia moto": [10, 8, 6, None, 100, -1]
        })
        self.assertEqual(recommendation_summary(frame), {
            "promoters": 1,
            "neutrals": 1,
            "detractors": 1,
            "nps": 0.0,
            "valid": 3,
        })

    def test_tsi_month_accepts_brazilian_iso_and_month_formats(self):
        engine = DashboardEngine.__new__(DashboardEngine)
        engine.db_manager = _Database([
            {"Data de Resposta": "01/08/2026 10:00"},
            {"Data de Resposta": "2026-09-08T12:30:00"},
            {"Data de Resposta": "7/2026"},
        ])
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        engine.config_path = os.path.join(temp_dir.name, "config.json")
        engine.config = {"lojas": [], "consultores": []}

        frame = engine.load_data()
        self.assertEqual(
            frame["Mes"].tolist(), ["08/2026", "09/2026", "07/2026"]
        )

    def test_sem_nota_filter_is_supported(self):
        responses = [
            {"status": "PROMOTOR", "cliente": "A"},
            {"status": "SEM_NOTA", "cliente": "B"},
        ]
        filtered, description = DashboardComparativoScreen._filtrar_respostas_por_estado(
            SimpleNamespace(), responses, {"statuses": ["SEM_NOTA"], "termo": ""}
        )
        self.assertEqual(filtered, [responses[1]])
        self.assertEqual(description, "Sem nota")


if __name__ == "__main__":
    unittest.main()
