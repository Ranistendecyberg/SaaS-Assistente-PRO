import datetime
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox

from src.tests.test_license_supabase import FakeBackend, manager_with
from src.ui.screens.whatsapp_screen import WhatsAppScreen
from src.ui.screens.extraction_screen import ExtractionScreen


class FakeListItem:
    def __init__(self, index, checked=True):
        self.index = index
        self.checked = checked

    def data(self, _role):
        return self.index

    def checkState(self):
        return Qt.CheckState.Checked if self.checked else Qt.CheckState.Unchecked


class FakeList:
    def __init__(self, items):
        self.items = items

    def count(self):
        return len(self.items)

    def item(self, index):
        return self.items[index]


class MessagingTests(unittest.TestCase):
    def test_conversation_target_has_strong_visual_distinction(self):
        source = (Path(__file__).resolve().parents[1] / "ui" / "screens" / "extraction_screen.py").read_text("utf-8")
        self.assertIn("Conversar com o Destacado", source)
        self.assertIn("Linha azul: conversa", source)
        self.assertIn("QListWidget::item:selected:!active", source)
        self.assertIn("background: #2563EB", source)

    def test_conversation_status_always_uses_latest_client_name(self):
        screen = SimpleNamespace(status_honda=MagicMock())
        ExtractionScreen._mostrar_conversa_iniciada(screen, "JANETE VIEIRA")
        screen.status_honda.setText.assert_called_once_with(
            "💬 Conversa iniciada com JANETE VIEIRA"
        )

    def test_stale_ssi_conversation_callback_is_ignored(self):
        screen = SimpleNamespace(
            _active_ssi_generation=2,
            _ssi_extracting_generation=2,
        )
        ExtractionScreen.on_ssi_ficha_extraida(
            screen, {"celular": "5586999999999"}, ssi_generation=1
        )

    def test_only_current_ssi_probe_can_start_extraction(self):
        screen = SimpleNamespace(
            _active_ssi_generation=3,
            _ssi_extracting_generation=None,
            tentativas=1,
            timer_ssi_ficha=MagicMock(),
            item_atual={},
            nav_ssi_oculto=MagicMock(),
        )
        ExtractionScreen.callback_ssi_ficha_pronto(screen, True, generation=2)
        screen.nav_ssi_oculto.page.assert_not_called()

    def test_daily_and_batch_limits_from_server(self):
        for daily, batch in [(40, 1), (20, 5), (6, 1)]:
            backend = FakeBackend({
                'license': {'status': 'active', 'license_type': 'subscription',
                            'expires_at': (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)).isoformat(),
                            'batch_limit': batch},
                'usage': {'messages_used': 2, 'daily_limit': daily},
            })
            manager = manager_with(backend)
            manager._save_report_links = lambda _: None
            result = manager.validar_licenca()
            self.assertEqual(result['limite_diario'], daily)
            self.assertEqual(result['limite_lote'], batch)

    def test_switch_chat_stops_timer_and_navigates_to_new_number(self):
        screen = MagicMock()
        screen._navigation_generation = 0
        for number in ['5586991111111', '5586992222222']:
            WhatsAppScreen.abrir_conversa_cliente(screen, number, 'Cliente', '', '', {})
            self.assertEqual(screen.web_view.setUrl.call_args.args[0].toString(),
                             f'https://web.whatsapp.com/send?phone={number}')
        self.assertEqual(screen.click_timer.stop.call_count, 2)
        self.assertEqual(screen._navigation_generation, 2)
        screen.web_view.page.assert_not_called()

    def test_old_send_callback_is_discarded(self):
        screen = MagicMock()
        screen._navigation_generation = 2
        WhatsAppScreen._finish_click(screen, 1, 'SENT')
        screen.callback_click.assert_not_called()
        WhatsAppScreen._finish_click(screen, 2, 'SENT')
        screen.callback_click.assert_called_once_with('SENT')

    def test_custom_daily_limit_in_error_message(self):
        screen = manager_with(FakeBackend())
        screen.validar_licenca = lambda: {'status': 'ativa'}
        screen.obter_contagem_diaria = lambda _: (20, 20)
        allowed, message = screen.checar_limite_envio()
        self.assertFalse(allowed)
        self.assertIn('20', message)

    def test_multiple_items_remain_selected(self):
        screen = SimpleNamespace(
            fila_extraida=[{'selecionado': False}, {'selecionado': True}],
            _atualizar_resumo_selecao=MagicMock(),
        )
        ExtractionScreen.ao_alterar_selecao_unica(screen, FakeListItem(0))
        self.assertEqual([item['selecionado'] for item in screen.fila_extraida], [True, True])

    def test_selection_summary_distinguishes_chat_from_batch(self):
        screen = SimpleNamespace(
            fila_extraida=[
                {'selecionado': True, 'enviado': False},
                {'selecionado': True, 'enviado': True},
                {'selecionado': False, 'enviado': False},
            ],
            selection_hint=MagicMock(),
            btn_dispatch=MagicMock(),
        )
        screen.btn_dispatch.isEnabled.return_value = True
        ExtractionScreen._atualizar_resumo_selecao(screen)
        self.assertIn('1 marcado(s)', screen.selection_hint.setText.call_args.args[0])
        screen.btn_dispatch.setText.assert_called_once_with('▶ Enviar 1 pesquisa(s)')

    @patch('PyQt6.QtWidgets.QMessageBox.question', return_value=QMessageBox.StandardButton.Yes)
    @patch('PyQt6.QtWidgets.QMessageBox.warning')
    @patch('src.core.license_manager.LicenseManager')
    def test_batch_limit_allows_five_and_rejects_six(self, manager_class, warning, question):
        manager_class.return_value.validar_licenca.return_value = {
            'status': 'ativa', 'limite_lote': 5,
        }

        def make_screen(count):
            return SimpleNamespace(
                clientes_nao_enviados=[],
                list_widget=FakeList([FakeListItem(i) for i in range(count)]),
                fila_extraida=[{'selecionado': True, 'enviado': False} for _ in range(count)],
                fila_disparo=[],
                btn_dispatch=MagicMock(),
                sig_check_whatsapp_login=MagicMock(),
            )

        allowed = make_screen(5)
        allowed._atualizar_resumo_selecao = MagicMock()
        ExtractionScreen.iniciar_disparo(allowed)
        allowed.sig_check_whatsapp_login.emit.assert_called_once()
        self.assertFalse(warning.called)
        question.assert_called_once()

        rejected = make_screen(6)
        rejected._atualizar_resumo_selecao = MagicMock()
        ExtractionScreen.iniciar_disparo(rejected)
        rejected.sig_check_whatsapp_login.emit.assert_not_called()
        warning.assert_called_once()
        self.assertIn('5', warning.call_args.args[2])

    @patch('PyQt6.QtWidgets.QMessageBox.question', return_value=QMessageBox.StandardButton.No)
    @patch('src.core.license_manager.LicenseManager')
    def test_cancelled_batch_does_not_check_whatsapp(self, manager_class, question):
        manager_class.return_value.validar_licenca.return_value = {
            'status': 'ativa', 'limite_lote': 5,
        }
        screen = SimpleNamespace(
            clientes_nao_enviados=[],
            list_widget=FakeList([FakeListItem(0), FakeListItem(1)]),
            fila_extraida=[
                {'cliente': 'A', 'selecionado': True, 'enviado': False},
                {'cliente': 'B', 'selecionado': True, 'enviado': False},
            ],
            fila_disparo=[],
            btn_dispatch=MagicMock(),
            sig_check_whatsapp_login=MagicMock(),
            _atualizar_resumo_selecao=MagicMock(),
        )
        ExtractionScreen.iniciar_disparo(screen)
        self.assertEqual(screen.fila_disparo, [])
        screen.sig_check_whatsapp_login.emit.assert_not_called()


if __name__ == '__main__':
    unittest.main()
