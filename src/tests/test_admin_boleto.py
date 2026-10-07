import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from admin_supabase import AdminSupabaseClient
from supabase_admin_app import SupabaseAdminApp


class AdminBoletoTests(unittest.TestCase):
    def test_admin_client_only_calls_supported_billing_routes(self):
        client = AdminSupabaseClient()
        with patch.object(client, '_request', return_value={}) as request:
            client.billing_request('session-token', 'admin_create_boleto', company_id='company-1')
            request.assert_called_once_with('POST', '/functions/v1/billing-api',
                {'action': 'admin_create_boleto', 'company_id': 'company-1'}, token='session-token')
            with self.assertRaises(ValueError):
                client.billing_request('session-token', 'create_payment')

    def test_boleto_dialog_uses_selected_company_and_provider_code(self):
        widgets = []
        buttons = {}
        def widget(*args, **kwargs):
            item = MagicMock()
            item.winfo_exists.return_value = True
            widgets.append(item)
            return item
        def button(parent, text, command, *args):
            item = MagicMock()
            item.command = command
            buttons[text] = item
            return item

        summary = {'profile': {'legal_name': 'Fixture Company'},
                   'payment_environment': 'test', 'invoices': []}
        charge = {'invoice': {'status': 'open', 'total_amount': '300.00'},
                  'attempt': {'id': 'attempt-1', 'payment_method': 'boleto',
                              'provider_environment': 'test', 'status': 'pending',
                              'boleto_barcode': 'provider-line', 'payment_url': 'https://example.test/boleto'}}
        client = MagicMock()
        client.billing_request.side_effect = [summary, charge, {'ok': True}, summary]
        fake = SimpleNamespace(
            _selected_enterprise=lambda: ({'id': 'company-1', 'name': 'Fixture Company'}, None),
            client=client, session=SimpleNamespace(access_token='session-token'),
            _toolbar_button=button, _show_error=MagicMock(),
            clipboard_clear=MagicMock(), clipboard_append=MagicMock(),
        )
        entries = []
        def entry(*args, **kwargs):
            field = MagicMock()
            field.get.return_value = ''
            entries.append(field)
            return field
        fake._run = lambda operation, accepted, *args, **kwargs: accepted(operation())
        with patch('supabase_admin_app.ctk.CTkToplevel', side_effect=widget), \
                patch('supabase_admin_app.ctk.CTkLabel', side_effect=widget), \
                patch('supabase_admin_app.ctk.CTkTextbox', side_effect=widget), \
                patch('supabase_admin_app.ctk.CTkFrame', side_effect=widget), \
                patch('supabase_admin_app.ctk.CTkScrollableFrame', side_effect=widget), \
                patch('supabase_admin_app.ctk.CTkEntry', side_effect=entry), \
                patch('supabase_admin_app.ctk.CTkFont', return_value=None), \
                patch('supabase_admin_app.center_window') as center, \
                patch('supabase_admin_app.webbrowser.open') as browser:
            SupabaseAdminApp.show_enterprise_boleto(fake)
            center.assert_called_once_with(widgets[0], 680, 540, parent=fake)
            buttons['Gerar boleto'].command()
            client.billing_request.assert_called_with('session-token', 'admin_create_boleto', company_id='company-1')
            buttons['Copiar linha'].command()
            fake.clipboard_append.assert_called_once_with('provider-line')
            buttons['Abrir boleto'].command()
            browser.assert_called_once_with('https://example.test/boleto')
            buttons['Dados de cobrança'].command()
            self.assertEqual(len(entries), 10)
            values = ['Fixture Payer', '11144477735', 'fixture@example.test', '64000000',
                      'Rua fictícia', '10', '', 'Centro', 'Teresina', 'PI']
            for field, value in zip(entries, values):
                field.get.return_value = value
            buttons['Salvar dados de cobrança'].command()
            call = client.billing_request.call_args_list[-2]
            self.assertEqual(call.args, ('session-token', 'admin_save_billing_profile'))
            self.assertEqual(call.kwargs['company_id'], 'company-1')
            self.assertEqual(call.kwargs['billing_cnpj'], '11144477735')
            client.billing_request.assert_called_with('session-token', 'admin_billing_summary', company_id='company-1')


if __name__ == '__main__':
    unittest.main()
