import os
import unittest
from types import MethodType, SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pandas as pd
from bs4 import BeautifulSoup
from src.core.dashboard_engine import DashboardEngine
from src.ui.screens.dashboard_screen import DashboardScreen, tsi_note_colors
from src.ui.screens.dashboard_comparativo_screen import DashboardComparativoScreen
from src.ui.screens.extraction_screen import ExtractionScreen

COLS = [
    'Avaliação satisfação instalações e infra',
    'Avaliação satisfação consultor',
    'Avaliação satisfação qualidade',
    'Avaliação satisfação entrega',
    'Avaliação satisfação custo benefício',
]


class Top2BoxGoalTests(unittest.TestCase):
    def test_comment_colors_follow_honda_note_bands(self):
        self.assertEqual(tsi_note_colors(9), ('#16A34A', '#DCFCE7', '#166534'))
        self.assertEqual(tsi_note_colors(10), ('#16A34A', '#DCFCE7', '#166534'))
        self.assertEqual(tsi_note_colors(8), ('#F59E0B', '#FEF3C7', '#92400E'))
        self.assertEqual(tsi_note_colors(6), ('#EF4444', '#FEE2E2', '#B91C1C'))
        self.assertEqual(tsi_note_colors(float('nan')), ('#94A3B8', '#F1F5F9', '#475569'))

    def frame(self, score=8, meta=75):
        return pd.DataFrame([{**dict.fromkeys(COLS, score), 'Loja_Meta': meta}])

    def metrics(self, frame):
        return DashboardEngine.calculate_metrics(SimpleNamespace(), frame)

    def test_high_tsi_does_not_mean_goal_achieved(self):
        result = self.metrics(self.frame())
        self.assertEqual(result['tsi_global'], 80)
        self.assertEqual(result['top2box_global'], 0)
        self.assertEqual(result['pesquisas_recuperacao'], 3)

    def test_nine_and_ten_are_both_top2box(self):
        for score in (9, 10):
            with self.subTest(score=score):
                result = self.metrics(self.frame(score, 100))
                self.assertEqual(result['top2box_global'], 100)
                self.assertEqual(result['tsi_global'], score * 10)
                self.assertEqual(result['pesquisas_recuperacao'], 0)

    def test_unreachable_and_missing_goals(self):
        self.assertEqual(self.metrics(self.frame(meta=100))['pesquisas_recuperacao'], -1)
        self.assertEqual(self.metrics(self.frame(meta=0))['pesquisas_recuperacao'], 0)
        empty_scores = pd.DataFrame([{**dict.fromkeys(COLS, None), 'Loja_Meta': 75}])
        self.assertEqual(self.metrics(empty_scores)['pesquisas_recuperacao'], -2)

    def test_recovery_integer_boundary_and_partial_answers(self):
        frame = pd.DataFrame([{**dict.fromkeys(COLS, 9), COLS[0]: 8, 'Loja_Meta': 90}])
        self.assertEqual(self.metrics(frame)['pesquisas_recuperacao'], 1)
        frame[COLS[1]] = None
        self.assertEqual(self.metrics(frame)['top2box_global'], 75)
        self.assertEqual(self.metrics(frame)['pesquisas_recuperacao'], 2)

    def renderer(self):
        fake = SimpleNamespace()
        fake._filtrar_respostas_por_estado = MethodType(
            DashboardComparativoScreen._filtrar_respostas_por_estado, fake)
        fake._formatar_verbalizacao_pdf = DashboardComparativoScreen._formatar_verbalizacao_pdf
        return fake

    def test_manager_html_and_pdf_goal_is_on_top2box_not_tsi(self):
        for pdf in (False, True):
            html = DashboardComparativoScreen._render_tsi_html(self.renderer(), {
                'tsi': 98, 'top2box': 60, 'meta_top2box': 75,
                'total_respostas': 1, 'dimensoes': {},
            }, [], [], is_pdf=pdf)
            soup = BeautifulSoup(html, 'html.parser')
            cards = {card.select_one('.kpi-title').get_text(): card
                     for card in soup.select('.grid-kpis > .card')}
            self.assertIn('98.0%', cards['Índice TSI (%)'].get_text())
            self.assertNotIn('Meta Honda', cards['Índice TSI (%)'].get_text())
            self.assertIn('60.0%', cards['Top2Box (%)'].get_text())
            self.assertIn('Abaixo da meta', cards['Top2Box (%)'].get_text())
            self.assertIn('#DC2626', str(cards['Top2Box (%)']))

    def test_manager_distribution_shows_top2box_in_html_and_pdf(self):
        metrics = {
            'tsi': 95, 'top2box': 50, 'total_respostas': 2, 'dimensoes': {},
            'distribuicao_lojas': [
                {'nome': 'Loja Teste', 'respostas': 2, 'tsi': 95, 'top2box': 50},
            ],
            'distribuicao_segmentos': [
                {'nome': 'Scooter', 'respostas': 2, 'tsi': 95, 'top2box': 50},
            ],
        }
        for pdf in (False, True):
            with self.subTest(pdf=pdf):
                html = DashboardComparativoScreen._render_tsi_html(
                    self.renderer(), metrics, [], [], is_pdf=pdf)
                soup = BeautifulSoup(html, 'html.parser')
                tables = [table for table in soup.select('table')
                          if table.find('thead', recursive=False)
                          and table.find('thead', recursive=False).find('th', string='Top2Box')
                          and table.find('tbody', recursive=False)
                          and table.find('tbody', recursive=False).find('td', string=lambda value: value in ('Loja Teste', 'Scooter'))]
                self.assertEqual(len(tables), 2)
                self.assertEqual(
                    [[cell.get_text(strip=True) for cell in row.find_all('td')]
                     for table in tables for row in table.select('tbody tr')],
                    [['Loja Teste', '2', '95.0%', '50.0%'],
                     ['Scooter', '2', '95.0%', '50.0%']],
                )

    def test_result_dashboard_gauge_bars_and_own_store_goals(self):
        frame = pd.concat([self.frame(meta=75), self.frame(9, meta=85)], ignore_index=True)
        frame['Loja_Nome'] = ['A', 'B']
        frame['Categoria Produto'] = ['Baixa', 'Alta']
        frame['Consultor_Nome'] = ['Ana', 'Bia']
        fake = SimpleNamespace(
            cb_mes=SimpleNamespace(currentText=lambda: '09/2026'),
            meses_historico=[], respostas_historico=[], tsi_historico=[],
            t2b_historico=[], pilares_historico={},
            engine=SimpleNamespace(calculate_metrics=self.metrics),
        )
        html = DashboardScreen.gerar_html_graficos(fake, self.metrics(frame), frame)
        self.assertIn("value: 50.0, name: 'Resultado Top2Box Atual'", html)
        self.assertIn('<span>85.00%</span>', html)  # TSI remains visible.
        self.assertIn('data: [75.0, 85.0]', html)
        self.assertIn("data: [50.0, 50.0, 50.0, 50.0, 50.0]", html)
        self.assertNotIn('Meta TSI', html)
        self.assertNotIn("name: 'Índice TSI (%)'", html)

    @patch('src.ui.screens.extraction_screen.QMessageBox')
    @patch('src.ui.screens.extraction_screen.record_event')
    def test_existing_timeout_cancels_batch_and_never_prepares_whatsapp(self, event, dialog):
        fake = SimpleNamespace(
            _active_ssi_generation=1, tentativas=10, modo_conversa_individual=False,
            _invalidate_ssi_lookup=MagicMock(), item_atual={'id': 'test', 'tipo': 'TSI'},
            nav_ssi_oculto=MagicMock(), on_whatsapp_message_sent=MagicMock(),
            sig_dispatch_whatsapp=MagicMock(),
        )
        ExtractionScreen.checar_ssi_ficha(fake)
        fake.on_whatsapp_message_sent.assert_called_once_with(False)
        fake.sig_dispatch_whatsapp.emit.assert_not_called()
        fake.nav_ssi_oculto.page.assert_not_called()
        self.assertIn('não carregou', fake.item_atual['_whatsapp_failure_reason'])
        dialog.warning.assert_not_called()

    @patch('src.ui.screens.extraction_screen.QMessageBox')
    @patch('src.ui.screens.extraction_screen.record_event')
    def test_timeout_login_expirado_orienta_sem_disparar(self, event, dialog):
        fake = SimpleNamespace(
            _active_ssi_generation=1, tentativas=10, modo_conversa_individual=False,
            _invalidate_ssi_lookup=MagicMock(), item_atual={'id': 'test', 'tipo': 'TSI'},
            nav_ssi_oculto=MagicMock(), on_whatsapp_message_sent=MagicMock(),
            sig_dispatch_whatsapp=MagicMock(),
        )
        fake.nav_ssi_oculto.url.return_value.toString.return_value = 'https://myhonda.my.site.com/login'
        ExtractionScreen.checar_ssi_ficha(fake)
        self.assertIn('Entre novamente', fake.item_atual['_whatsapp_failure_reason'])
        fake.on_whatsapp_message_sent.assert_called_once_with(False)
        fake.sig_dispatch_whatsapp.emit.assert_not_called()

    @patch('src.ui.screens.extraction_screen.QMessageBox')
    def test_timeout_individual_orienta_e_nao_dispara(self, dialog):
        fake = SimpleNamespace(
            _active_ssi_generation=1, tentativas=10, modo_conversa_individual=True,
            _invalidate_ssi_lookup=MagicMock(), nav_ssi_oculto=MagicMock(),
            status_honda=MagicMock(), on_whatsapp_message_sent=MagicMock(),
        )
        ExtractionScreen.checar_ssi_ficha(fake)
        dialog.warning.assert_called_once()
        self.assertIn('não carregou', dialog.warning.call_args.args[2])
        fake.on_whatsapp_message_sent.assert_not_called()


if __name__ == '__main__':
    unittest.main()
