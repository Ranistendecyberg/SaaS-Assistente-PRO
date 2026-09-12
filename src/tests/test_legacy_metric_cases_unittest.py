"""Inclui na suíte unittest os cenários históricos originalmente escritos como funções."""

import unittest

from src.tests.test_dashboard_calc import test_math
from src.tests.test_dashboard_tsi_gerencial import (
    test_tsi_usa_nota_oficial_e_mantem_ausencia_no_denominador,
)
from src.tests.test_ssi_metrics import (
    test_general_report_uses_ssi_satisfaction_and_separate_nps,
    test_legacy_fallback_preserves_honda_missing_value_rules,
    test_official_ssi_aggregates_match_saved_myhonda_report,
)
from src.tests.test_tsi_annual_history import (
    test_filtro_anual_tsi_usa_intervalo_exato_do_salesforce,
    test_monitor_ssi_aceita_intervalo_personalizado_quando_relatorio_concluiu,
    test_monitor_ssi_aguarda_status_oficial_concluido,
    test_monitor_tsi_conclui_quando_intervalo_anual_estabiliza,
    test_monitor_tsi_nao_importa_tabela_antiga_enquanto_relatorio_executa,
)


class LegacyMetricCasesTests(unittest.TestCase):
    def test_dashboard_math(self):
        test_math()

    def test_tsi_official_score_and_missing_denominator(self):
        test_tsi_usa_nota_oficial_e_mantem_ausencia_no_denominador()

    def test_ssi_official_aggregates(self):
        test_official_ssi_aggregates_match_saved_myhonda_report()

    def test_ssi_legacy_fallback(self):
        test_legacy_fallback_preserves_honda_missing_value_rules()

    def test_ssi_general_report(self):
        test_general_report_uses_ssi_satisfaction_and_separate_nps()

    def test_tsi_annual_filter(self):
        test_filtro_anual_tsi_usa_intervalo_exato_do_salesforce()

    def test_tsi_annual_monitor_completion(self):
        test_monitor_tsi_conclui_quando_intervalo_anual_estabiliza()

    def test_tsi_monitor_ignores_old_table(self):
        test_monitor_tsi_nao_importa_tabela_antiga_enquanto_relatorio_executa()

    def test_ssi_monitor_accepts_custom_interval(self):
        test_monitor_ssi_aceita_intervalo_personalizado_quando_relatorio_concluiu()

    def test_ssi_monitor_waits_for_completion(self):
        test_monitor_ssi_aguarda_status_oficial_concluido()


if __name__ == "__main__":
    unittest.main()
