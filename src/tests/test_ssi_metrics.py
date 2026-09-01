from types import SimpleNamespace

import pandas as pd

from src.core.ssi_metrics import (
    calculate_percentage,
    format_model_year,
    recommendation_summary,
)
from src.ui.screens.dashboard_comparativo_screen import DashboardComparativoScreen


class _Combo:
    def __init__(self, text):
        self.text = text

    def currentText(self):
        return self.text


class _Db:
    def get_leads_mapping(self):
        return {}

    def find_lead(self, *args, **kwargs):
        return None


class _Screen:
    _calcular_participacao_whatsapp = lambda self, df, tipo: (0, 0.0)


def _official(top, zero, missing=0):
    return ["100,00%"] * top + ["0,00%"] * zero + ["-"] * missing


def myhonda_ssi_frame():
    size = 14
    return pd.DataFrame({
        "Relação de Posse: Name": [f"POSSE{i}-9C2TESTE{i:09d}" for i in range(size)],
        "Cliente": [f"Cliente {i}" for i in range(size)],
        "CPF do funcionário (Vendedor)": ["12345678901"] * size,
        "Consultor_Nome": ["Vendedor Teste"] * size,
        "Modelo": ["CG 160"] * size,
        "Ano do modelo": ["2.026"] * size,
        "Modalidade de Compra": ["CONSORCIO"] * size,
        "Data de resposta SSI 2W": ["12/08/2026 09:01"] * size,
        "Loja": ["Loja Teste"] * size,
        "Avaliação experiência compra dealer moto": [10] * 12 + [7, 6],
        "Compraria outra mesmo dealer moto": [10] * 12 + [5, 6],
        "Recomendaria dealer amigo e familia moto": [10] * 12 + [5, 6],
        "Conforto das instalações moto": [10] * 10 + [6, 8, None, None],
        "Atenção no atendimento do vendedor moto": [10] * 13 + [None],
        "Realizou Test-Ride": ["Sim"] * 3 + ["Não"] * 9 + [None, None],
        "Negociação Geral": [10] * 12 + [3, None],
        "Avaliação Entrega Motocicleta": [10] * 12 + [7, None],
        "(%) Recompra": _official(12, 2),
        "(%) Recomendação": _official(12, 2),
        "(%) Instalação e Infraestrutura": _official(10, 4),
        "(%) Atendimento": _official(13, 1),
        "(%) Test Ride": _official(3, 9, 2),
        "(%) Negociação": _official(12, 2),
        "(%) Satisfação Geral": _official(12, 2),
        "(%) Avaliação Entrega Motocicleta": _official(12, 1, 1),
    })


def test_official_ssi_aggregates_match_saved_myhonda_report():
    df = myhonda_ssi_frame()

    assert round(calculate_percentage(df, "satisfaction"), 4) == 85.7143
    assert round(calculate_percentage(df, "recommendation"), 4) == 85.7143
    assert round(calculate_percentage(df, "installations"), 4) == 71.4286
    assert round(calculate_percentage(df, "service"), 4) == 92.8571
    assert round(calculate_percentage(df, "test_ride"), 4) == 25.0
    assert round(calculate_percentage(df, "negotiation"), 4) == 85.7143
    assert round(calculate_percentage(df, "delivery"), 4) == 92.3077
    assert round(calculate_percentage(df, "repurchase"), 4) == 85.7143

    summary = recommendation_summary(df)
    assert summary == {
        "promoters": 12,
        "neutrals": 0,
        "detractors": 2,
        "nps": 71.42857142857143,
        "valid": 14,
    }


def test_legacy_fallback_preserves_honda_missing_value_rules():
    df = myhonda_ssi_frame().drop(columns=[column for column in myhonda_ssi_frame().columns if column.startswith("(%)")])

    assert round(calculate_percentage(df, "service"), 4) == 92.8571
    assert round(calculate_percentage(df, "negotiation"), 4) == 85.7143
    assert round(calculate_percentage(df, "installations"), 4) == 71.4286
    assert round(calculate_percentage(df, "test_ride"), 4) == 25.0
    assert round(calculate_percentage(df, "delivery"), 4) == 92.3077


def test_general_report_uses_ssi_satisfaction_and_separate_nps():
    screen = _Screen()
    screen.df_ssi = myhonda_ssi_frame()
    screen.combo_loja = _Combo("Todas as Unidades")
    screen.combo_mes = _Combo("08/2026")
    screen.combo_consultor = _Combo("Todos")
    screen.sent_surveys = set()
    screen.db = _Db()
    screen.engine_tsi = SimpleNamespace()

    metrics, modalities, ranking, _, responses = DashboardComparativoScreen._calcular_metricas_ssi(screen)

    assert round(metrics["ssi"], 4) == 85.7143
    assert round(metrics["nps"], 4) == 71.4286
    assert round(metrics["dimensoes"]["Atendimento Vendedor"], 4) == 92.8571
    assert round(modalities[0]["ssi"], 4) == 85.7143
    assert round(modalities[0]["nps"], 4) == 71.4286
    assert round(ranking[0]["ssi"], 4) == 85.7143
    assert round(ranking[0]["media"], 4) == 85.7143
    assert round(ranking[0]["nps"], 4) == 71.4286
    assert responses[12]["notas_pilares"]["Recompra"] == "5"
    assert responses[0]["modelo"] == "CG 160 (2026)"
    assert format_model_year("2.026") == "2026"
    assert format_model_year(2026.0) == "2026"

    html = DashboardComparativoScreen._render_ssi_html(
        screen, metrics, modalities, ranking, responses
    )
    assert "NPS Recomendação" in html
    assert "Recomendação T2B" in html
    assert "Satisfação Geral" in html
