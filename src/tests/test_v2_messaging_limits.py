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
from src.core.developer_access import DeveloperAccessGuard


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

    def test_phone_normalization_for_diagnostic_test(self):
        self.assertEqual(
            WhatsAppScreen._normalize_test_phone('(85) 99999-9999'),
            '5585999999999',
        )
        self.assertEqual(
            WhatsAppScreen._normalize_test_phone('+55 85 99999-9999'),
            '5585999999999',
        )
        self.assertEqual(WhatsAppScreen._normalize_test_phone('123'), '')

    @patch('src.ui.screens.whatsapp_screen.record_event')
    def test_click_attempt_does_not_confirm_batch_until_composer_clears(self, _record):
        screen = SimpleNamespace(
            _last_probe_status='',
            _awaiting_confirmation=False,
            modo_envio='LOTE',
            _telemetry_contact_ref='anon',
            tentativas_click=2,
            sig_message_sent=MagicMock(),
            click_timer=MagicMock(),
        )
        WhatsAppScreen.callback_click(
            screen, {'status': 'CLICKED', 'selector': 'DATA_ICON_SEND'}
        )
        self.assertTrue(screen._awaiting_confirmation)
        screen.sig_message_sent.emit.assert_not_called()

        WhatsAppScreen.callback_click(
            screen,
            {'status': 'CONFIRMED', 'composer_cleared': True, 'outgoing_match': True},
        )
        screen.sig_message_sent.emit.assert_called_once_with(True)
        screen.click_timer.stop.assert_called_once()

    @patch('src.ui.screens.whatsapp_screen.record_event')
    def test_diagnostic_confirmation_never_emits_batch_success(self, _record):
        screen = SimpleNamespace(
            _last_probe_status='',
            _awaiting_confirmation=True,
            modo_envio='DIAGNOSTICO',
            _telemetry_contact_ref='anon',
            tentativas_click=3,
            sig_message_sent=MagicMock(),
            click_timer=MagicMock(),
            diagnostic_status=MagicMock(),
            btn_diagnostic_send=MagicMock(),
        )
        WhatsAppScreen.callback_click(
            screen,
            {'status': 'CONFIRMED', 'composer_cleared': True, 'outgoing_match': True},
        )
        screen.sig_message_sent.emit.assert_not_called()
        screen.btn_diagnostic_send.setEnabled.assert_called_once_with(True)

    @patch('src.core.developer_access.record_event')
    def test_developer_password_uses_hardened_verifier(self, _record):
        original = (
            DeveloperAccessGuard._failures,
            DeveloperAccessGuard._blocked_until,
        )
        try:
            DeveloperAccessGuard._failures = 0
            DeveloperAccessGuard._blocked_until = 0
            self.assertEqual(
                DeveloperAccessGuard.verify_password('@1234'),
                (True, 'OK'),
            )
            self.assertEqual(
                DeveloperAccessGuard.verify_password('incorreta'),
                (False, 'INVALID:4'),
            )
        finally:
            DeveloperAccessGuard._failures, DeveloperAccessGuard._blocked_until = original

    @patch('src.core.license_manager.LicenseManager.get_instance')
    def test_missing_diagnostic_authorization_is_not_reported_as_connection_error(self, get_manager):
        get_manager.return_value.validar_licenca.return_value = {
            'status': 'ativa',
            'diagnostico_detalhado_ate': None,
        }

        self.assertEqual(
            DeveloperAccessGuard.authorization_status(force=True),
            (False, 'DIAGNOSTIC_AUTHORIZATION_REQUIRED'),
        )

    @patch('src.core.license_manager.LicenseManager.get_instance')
    def test_diagnostic_connection_failure_remains_unavailable(self, get_manager):
        get_manager.return_value.validar_licenca.side_effect = OSError('offline')

        self.assertEqual(
            DeveloperAccessGuard.authorization_status(force=True),
            (False, 'DIAGNOSTIC_AUTHORIZATION_UNAVAILABLE'),
        )

    @patch('src.ui.screens.whatsapp_screen.QInputDialog.getText', return_value=('@1234', True))
    @patch.object(DeveloperAccessGuard, 'verify_password', return_value=(True, 'OK'))
    @patch.object(DeveloperAccessGuard, 'authorization_status', return_value=(True, ''))
    def test_diagnostic_panel_requires_temporary_authorization_and_password(
        self, _authorization, _password, _prompt,
    ):
        screen = SimpleNamespace(
            diagnostic_panel=MagicMock(),
            btn_diagnostic_send=MagicMock(),
            diagnostic_status=MagicMock(),
        )
        screen.diagnostic_panel.isVisible.return_value = False
        WhatsAppScreen.toggle_diagnostic_panel(screen)
        screen.diagnostic_panel.setVisible.assert_called_once_with(True)
        screen.btn_diagnostic_send.setEnabled.assert_called_once_with(True)

    @patch.object(DeveloperAccessGuard, 'authorization_status', return_value=(False, 'DIAGNOSTIC_AUTHORIZATION_REQUIRED'))
    @patch('src.ui.screens.whatsapp_screen.QMessageBox.warning')
    def test_diagnostic_panel_stays_hidden_without_server_authorization(
        self, warning, _authorization,
    ):
        screen = SimpleNamespace(
            diagnostic_panel=MagicMock(),
            btn_diagnostic_send=MagicMock(),
        )
        screen.diagnostic_panel.isVisible.return_value = False
        WhatsAppScreen.toggle_diagnostic_panel(screen)
        screen.diagnostic_panel.setVisible.assert_not_called()
        warning.assert_called_once()

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
                db_manager=SimpleNamespace(is_whatsapp_unavailable=lambda item: False),
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
            db_manager=SimpleNamespace(is_whatsapp_unavailable=lambda item: False),
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
