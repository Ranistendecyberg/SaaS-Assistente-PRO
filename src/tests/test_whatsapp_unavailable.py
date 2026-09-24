import json
import os
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from src.core.database import DatabaseManager
from src.ui.screens.whatsapp_screen import WhatsAppScreen
from src.ui.screens.extraction_screen import ExtractionScreen
from src.tests import test_extraction_search as search_tests


class UnavailablePhoneTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = self.database()
        self.item = {'id': 'survey-1', 'tipo': 'SSI', 'telefone': '(86) 99999-1111'}

    def database(self):
        db = DatabaseManager.__new__(DatabaseManager)
        db.app_data_dir = self.tmp.name
        db.sent_path = os.path.join(self.tmp.name, 'sent_surveys.json')
        return db

    def test_persists_across_restart_without_marking_sent_or_mutating_source(self):
        original = dict(self.item)
        self.assertTrue(self.db.mark_whatsapp_unavailable('5586999991111', self.item))
        self.assertTrue(self.database().is_whatsapp_unavailable(self.item))
        self.assertEqual(self.db.load_sent_surveys(), set())
        self.assertEqual(self.item, original)
        self.assertTrue(self.db.clear_sent_history())
        self.assertTrue(self.db.is_whatsapp_unavailable(self.item))

    def test_same_phone_other_survey_is_hidden_but_new_myhonda_phone_is_allowed(self):
        self.db.mark_whatsapp_unavailable(self.item['telefone'], self.item)
        self.assertTrue(self.db.is_whatsapp_unavailable(dict(self.item, id='other', tipo='TSI')))
        self.assertFalse(self.db.is_whatsapp_unavailable(dict(self.item, telefone='86999992222')))
        self.assertTrue(self.db.is_whatsapp_unavailable(dict(self.item, telefone='S/N')))
        self.assertFalse(self.db.is_whatsapp_unavailable(dict(self.item, id='unknown', telefone='S/N')))
        self.assertFalse(self.db.is_whatsapp_unavailable(dict(self.item, tipo='TSI', telefone='S/N')))

    def test_cache_observes_another_database_instance(self):
        other = self.database()
        self.assertFalse(other.is_whatsapp_unavailable(self.item))
        self.db.mark_whatsapp_unavailable(self.item['telefone'], self.item)
        self.assertTrue(other.is_whatsapp_unavailable(self.item))

    def test_corrupt_file_is_preserved(self):
        path = os.path.join(self.tmp.name, 'unavailable_whatsapp.json')
        with open(path, 'w') as stream:
            stream.write('{invalid')
        self.assertFalse(self.db.mark_whatsapp_unavailable(self.item['telefone'], self.item))
        with open(path) as stream:
            self.assertEqual(stream.read(), '{invalid')

    def test_brazilian_ddd55_is_not_confused_with_country_code(self):
        self.assertEqual(self.db.whatsapp_phone_key('(55) 99999-1111'), '5555999991111')
        self.assertEqual(self.db.whatsapp_phone_key('+55 55 99999-1111'), '5555999991111')
        self.assertEqual(self.db.whatsapp_phone_key('S/N'), '')

    @patch('src.ui.screens.whatsapp_screen.record_event')
    def test_only_explicit_invalid_phone_emits_persistence_signal(self, _record):
        for mode in ('LOTE', 'INDIVIDUAL', 'DIAGNOSTICO'):
            screen = MagicMock()
            screen.modo_envio = mode
            screen._send_phone = '5586999991111'
            WhatsAppScreen.callback_click(screen, {'status': 'NOT_FOUND', 'reason': 'COMPOSER_NOT_FOUND'})
            screen.sig_phone_unavailable.emit.assert_not_called()
            WhatsAppScreen.callback_click(screen, {'status': 'INVALID_PHONE'})
            if mode == 'DIAGNOSTICO':
                screen.sig_phone_unavailable.emit.assert_not_called()
            else:
                screen.sig_phone_unavailable.emit.assert_called_once_with('5586999991111', mode)
            if mode == 'LOTE':
                screen.sig_message_sent.emit.assert_called_once_with(False)
            else:
                screen.sig_message_sent.emit.assert_not_called()

    @patch('src.ui.screens.whatsapp_screen.record_event')
    def test_timeout_does_not_emit_unavailable_phone(self, _record):
        screen = MagicMock()
        screen._click_pending = False
        screen.tentativas_click = 20
        screen.modo_envio = 'LOTE'
        WhatsAppScreen.tentar_clicar_enviar(screen)
        screen.sig_phone_unavailable.emit.assert_not_called()
        screen.sig_message_sent.emit.assert_called_once_with(False)

    @patch('src.core.license_manager.LicenseManager')
    def test_duplicate_in_running_batch_is_skipped_before_reserving_quota(self, manager):
        self.db.mark_whatsapp_unavailable(self.item['telefone'], self.item)
        screen = SimpleNamespace(db_manager=self.db, fila_extraida=[dict(self.item, selecionado=True)],
                                 fila_disparo=[0], btn_dispatch=MagicMock(),
                                 status_honda=MagicMock(), atualizar_lista_ui=MagicMock())
        ExtractionScreen.processar_proximo_disparo(screen)
        self.assertEqual(screen.fila_disparo, [])
        manager.assert_not_called()

    @patch('src.ui.screens.extraction_screen.QTimer.singleShot')
    @patch('src.core.license_manager.LicenseManager')
    @patch('src.ui.screens.extraction_screen.record_event')
    def test_failed_batch_releases_reservation_without_confirming_or_marking_sent(self, _record, manager, _timer):
        manager.return_value.liberar_reserva_envio.return_value = (True, '')
        item = dict(self.item)
        screen = SimpleNamespace(db_manager=self.db, item_atual=item, reserva_envio_atual='reservation',
                                 status_honda=MagicMock(), atualizar_lista_ui=MagicMock(), processar_proximo_disparo=MagicMock())
        ExtractionScreen.on_whatsapp_phone_unavailable(screen, '5586999991111', 'LOTE')
        ExtractionScreen.on_whatsapp_message_sent(screen, False)
        manager.return_value.liberar_reserva_envio.assert_called_once_with('reservation')
        manager.return_value.confirmar_envio.assert_not_called()
        self.assertFalse(item.get('enviado', False))
        self.assertIn('Sem WhatsApp', screen.clientes_nao_enviados[0]['motivo'])

    def test_individual_confirmation_and_stale_phone_guard(self):
        screen = SimpleNamespace(db_manager=self.db, item_conversa_individual=self.item,
                                 status_honda=MagicMock(), atualizar_lista_ui=MagicMock())
        ExtractionScreen.on_whatsapp_phone_unavailable(screen, '5586999992222', 'INDIVIDUAL')
        self.assertFalse(self.db.is_whatsapp_unavailable(self.item))
        ExtractionScreen.on_whatsapp_phone_unavailable(screen, '5586999991111', 'INDIVIDUAL')
        self.assertTrue(self.db.is_whatsapp_unavailable(self.item))

    def test_refreshed_list_hides_blocked_phone_and_keeps_corrected_phone(self):
        search_tests.ExtractionSearchTests.setUpClass()
        screen = search_tests.ExtractionSearchTests()._screen('')
        screen.db_manager = self.db
        screen.fila_extraida = [dict(self.item, cliente='A', selecionado=True),
                               dict(self.item, cliente='B', telefone='86999992222')]
        self.db.mark_whatsapp_unavailable(self.item['telefone'], self.item)
        ExtractionScreen.atualizar_lista_ui(screen)
        self.assertEqual(screen.list_widget.count(), 1)
        self.assertIn('B', screen.list_widget.item(0).text())
        self.assertFalse(screen.fila_extraida[0]['selecionado'])

    def test_dialog_is_detected_without_composer_and_generic_errors_are_not_blocked(self):
        screen = MagicMock()
        screen._click_pending = False
        screen._send_loading = False
        screen._awaiting_confirmation = False
        screen.tentativas_click = 0
        screen._expected_message = 'test'
        WhatsAppScreen.tentar_clicar_enviar(screen)
        script = screen.web_view.page().runJavaScript.call_args.args[0]
        harness = '''
const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));
global.document = {querySelector: () => null, querySelectorAll: () => [{innerText:input.text,querySelector:()=>null}]};
console.log(JSON.stringify(eval(input.script)));
'''
        for text, expected in [
            ('O número de telefone compartilhado por url é inválido.', 'INVALID_PHONE'),
            ('Phone number shared via url is invalid.', 'INVALID_PHONE'),
            ("This phone number isn't on WhatsApp", 'INVALID_PHONE'),
            ('Este número não está no WhatsApp.', 'INVALID_PHONE'),
            ('Código de segurança inválido.', 'NOT_FOUND'),
            ('Sem conexão com a internet.', 'NOT_FOUND'),
        ]:
            result = subprocess.run(['node', '-e', harness], input=json.dumps({'text': text, 'script': script}),
                                    capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(result.stdout)['status'], expected)


if __name__ == '__main__':
    unittest.main()
