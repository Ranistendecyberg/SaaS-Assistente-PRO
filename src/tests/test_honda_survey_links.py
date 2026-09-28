import base64
import os
import unittest
from types import MethodType, SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlsplit

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QTWEBENGINE_CHROMIUM_FLAGS', '--disable-gpu')
from src.core.medallia_builder import MedalliaBuilder as Builder
from src.core.honda_contact_extractor import CONTACT_EXTRACTOR_JS
from src.core.salesforce_utils import salesforce_15_to_18
from src.ui.screens.extraction_screen import ExtractionScreen

SSI = 'a0R000000000001'
TSI = 'a0O000000000001'
EMAIL = 'Cliente+teste@example.invalid'


class LinkTests(unittest.TestCase):
    def test_ssi_roundtrip_and_commercial_displacement(self):
        for model, expected in [('POP110I ES', '110'), ('BIZ125EX', '125'),
                                ('CG160 FAN', '160'), ('XRE 190 ADV', '190'), ('CB 1000R', '1000')]:
            with self.subTest(model=model):
                url = urlsplit(Builder.build_ssi_link(SSI, model, email=EMAIL))
                self.assertEqual(url.netloc, 'cloud.motos.myhonda.com.br')
                self.assertEqual(url.path, '/ssi2w')
                query = parse_qs(url.query)
                self.assertEqual(set(query), {'e', 'Q1', 'Q2', 'Q3'})
                self.assertEqual(base64.b64decode(query['e'][0]).decode(), EMAIL)
                self.assertEqual(base64.b64decode(query['Q1'][0]).decode(), salesforce_15_to_18(SSI))
                self.assertEqual(base64.b64decode(query['Q2'][0]).decode(), ''.join(model.split()).upper())
                self.assertEqual(query['Q3'], [expected])

    def test_tsi_only_email_and_id(self):
        url = Builder.build_tsi_link(TSI, EMAIL)
        query = parse_qs(urlsplit(url).query)
        self.assertEqual(set(query), {'e', 'Q1'})
        self.assertEqual(base64.b64decode(query['e'][0]).decode(), EMAIL)
        self.assertEqual(base64.b64decode(query['Q1'][0]).decode(), salesforce_15_to_18(TSI))
        self.assertIn('%3D', url)
        self.assertEqual(url, Builder.build_tsi_link(salesforce_15_to_18(TSI), EMAIL))

    def test_invalid_inputs_block_generation(self):
        for email in ['', 'unknown', 'a@example.invalid;b@example.invalid', 'a @example.invalid']:
            with self.subTest(email=email), self.assertRaises(ValueError):
                Builder.build_tsi_link(TSI, email)
        for model in ['', 'HONDA', 'CG160 2026', '160.5', 'CG1 FAN']:
            with self.subTest(model=model), self.assertRaises(ValueError):
                Builder.build_ssi_link(SSI, model, email=EMAIL)
        for identifier in ['', SSI, 'a0O000000000001ZZZ']:
            with self.subTest(identifier=identifier), self.assertRaises(ValueError):
                Builder.build_tsi_link(identifier, EMAIL)


class DispatchTests(unittest.TestCase):
    def screen(self, tipo, individual=False):
        item = {'id': SSI if tipo == 'SSI' else TSI, 'tipo': tipo,
                'telefone': '86999999999', 'cliente': 'CLIENTE FICTÍCIO'}
        screen = SimpleNamespace(item_atual=item, item_conversa_individual=item,
            modo_conversa_individual=individual, _active_ssi_generation=1,
            _ssi_extracting_generation=1, _diagnostic_lookup=False,
            sig_dispatch_whatsapp=MagicMock(), sig_iniciar_conversa_individual=MagicMock(),
            sig_request_tab_change=MagicMock(), editor_mensagem=MagicMock(),
            status_honda=MagicMock(), db_manager=MagicMock(), atualizar_lista_ui=MagicMock(),
            _mostrar_conversa_iniciada=MagicMock(), on_whatsapp_message_sent=MagicMock())
        screen.db_manager.is_whatsapp_unavailable.return_value = False
        screen.editor_mensagem.toPlainText.return_value = 'Olá [NOME] [LINK]'
        screen._survey_lookup_failed = MethodType(ExtractionScreen._survey_lookup_failed, screen)
        return screen

    def data(self, tipo):
        return {'record_id': SSI if tipo == 'SSI' else TSI, 'email': EMAIL,
                'modelo': 'POP110I ES', 'celular': '86111111111'}

    def test_individual_and_batch_share_new_builder(self):
        for tipo in ['SSI', 'TSI']:
            for individual in [False, True]:
                with self.subTest(tipo=tipo, individual=individual):
                    screen = self.screen(tipo, individual)
                    ExtractionScreen.on_ssi_ficha_extraida(screen, self.data(tipo), 1)
                    signal = screen.sig_iniciar_conversa_individual if individual else screen.sig_dispatch_whatsapp
                    signal.emit.assert_called_once()
                    self.assertEqual(signal.emit.call_args.args[0], '5586999999999')
                    self.assertIn('/ssi2w?' if tipo == 'SSI' else '/tsi2w?', str(signal.emit.call_args.args))
                    screen.on_whatsapp_message_sent.assert_not_called()
                    # Duplicated callback cannot prepare a second message.
                    ExtractionScreen.on_ssi_ficha_extraida(screen, self.data(tipo), 1)
                    self.assertEqual(signal.emit.call_count, 1)

    def test_missing_or_wrong_ficha_releases_batch_without_send(self):
        for changes in [{'email': ''}, {'record_id': TSI}, {'modelo': ''}, {'error': 'E-mails divergentes.'}]:
            with self.subTest(changes=changes):
                screen = self.screen('SSI')
                data = self.data('SSI') | changes
                ExtractionScreen.on_ssi_ficha_extraida(screen, data, 1)
                screen.sig_dispatch_whatsapp.emit.assert_not_called()
                screen.on_whatsapp_message_sent.assert_called_once_with(False)
                self.assertTrue(screen.item_atual['_whatsapp_failure_reason'])

    @patch('src.ui.screens.extraction_screen.QMessageBox')
    @patch('src.ui.screens.extraction_screen.DeveloperAccessGuard.authorization_status', return_value=(True, ''))
    def test_diagnostic_displays_without_whatsapp_or_quota(self, authorization, dialog):
        screen = self.screen('TSI', True)
        screen._diagnostic_lookup = True
        screen.item_atual['telefone'] = ''  # Read-only link test does not require a phone.
        ExtractionScreen.on_ssi_ficha_extraida(screen, self.data('TSI'), 1)
        dialog.return_value.exec.assert_called_once()
        self.assertIn('/tsi2w?', dialog.return_value.setText.call_args.args[0])
        screen.sig_dispatch_whatsapp.emit.assert_not_called()
        screen.sig_iniciar_conversa_individual.emit.assert_not_called()
        screen.on_whatsapp_message_sent.assert_not_called()

    def test_both_types_open_ficha_even_if_phone_is_cached(self):
        for tipo in ['SSI', 'TSI']:
            screen = self.screen(tipo)
            screen._invalidate_ssi_lookup = MagicMock()
            screen._begin_ssi_lookup = MagicMock()
            screen.nav_ssi_oculto = MagicMock()
            screen.timer_ssi_ficha = MagicMock()
            screen.item_atual['url_ficha'] = '/concessionaria/' + screen.item_atual['id']
            ExtractionScreen._open_survey_contact(screen, screen.item_atual)
            screen.nav_ssi_oculto.setUrl.assert_called_once()
            screen.timer_ssi_ficha.start.assert_called_once_with(2000)


class FichaDOMTests(unittest.TestCase):
    def extract(self, html, record=SSI):
        # Execute the production JavaScript with a DOM fixture parsed from HTML.
        # No live browser, network, survey access or contact data is involved.
        import json
        import subprocess
        from bs4 import BeautifulSoup, Tag
        soup = BeautifulSoup(html, 'html.parser')
        elements = list(soup.find_all(True))
        positions = {id(el): index for index, el in enumerate(elements)}
        nodes = []
        for el in elements:
            sibling = el.find_next_sibling()
            parent = el.parent
            nodes.append({'tag': el.name, 'text': el.get_text(), 'classes': el.get('class', []),
                          'next': positions.get(id(sibling)), 'parent': positions.get(id(parent))})
        harness = r"""
        const fs = require('fs'), vm = require('vm');
        const input = JSON.parse(fs.readFileSync(0, 'utf8'));
        const nodes = input.nodes.map(x => ({...x, innerText:x.text, textContent:x.text}));
        const match = (el, selector) => selector.startsWith('.')
            ? el.classes.includes(selector.slice(1)) : el.tag === selector;
        for (const node of nodes) {
            node.nextElementSibling = nodes[node.next] || null;
            node.parentElement = nodes[node.parent] || null;
            node.closest = selector => {
                for (let el=node; el; el=el.parentElement) if (match(el,selector)) return el;
                return null;
            };
            node.contains = target => {
                for (let el=target; el; el=el.parentElement) if (el === node) return true;
                return false;
            };
        }
        const document = {querySelectorAll: selector => nodes.filter(
            el => selector.split(',').some(s => match(el, s.trim())))};
        const result = vm.runInNewContext(input.script, {document, location:{pathname:input.path}});
        process.stdout.write(JSON.stringify(result));
        """
        data = {'nodes': nodes, 'script': CONTACT_EXTRACTOR_JS, 'path': '/concessionaria/' + record}
        completed = subprocess.run(['node', '-e', harness], input=json.dumps(data),
                                   text=True, capture_output=True, timeout=10, check=True)
        return json.loads(completed.stdout)

    def test_ssi_contact_section_and_not_seller_email(self):
        html = '<div class="pbSubheader"><h3>Dados para Contato</h3></div><div><table>'
        html += '<tr><td>Email</td><td>' + EMAIL + '</td></tr>' * 2
        html += '</table></div><h3>Vendedor</h3><table><tr><td>Email</td><td>seller@example.invalid</td></tr>'
        html += '<tr><td>Modelo</td><td>POP110I ES</td></tr></table>'
        result = self.extract(html)
        self.assertEqual(result['email'], EMAIL)
        self.assertEqual(result['modelo'], 'POP110I ES')
        self.assertEqual(result['record_id'], SSI)
        self.assertEqual(result['error'], '')

    def test_tsi_explicit_email_and_no_arbitrary_phone(self):
        result = self.extract('<table><tr><td>E-mail do Cliente</td><td>' + EMAIL +
            '</td></tr></table><p>Contato do vendedor: (86) 99999-9999</p>', TSI)
        self.assertEqual(result['email'], EMAIL)
        self.assertEqual(result['celular'], '')
        self.assertEqual(result['record_id'], TSI)

    def test_conflicting_emails_do_not_choose_one(self):
        result = self.extract('<h3>Dados para Contato</h3><table>' +
            '<tr><td>Email</td><td>a@example.invalid</td></tr>' +
            '<tr><td>Email</td><td>b@example.invalid</td></tr></table>')
        self.assertTrue(result['error'])
        self.assertEqual(result['email'], '')


if __name__ == '__main__':
    unittest.main()
