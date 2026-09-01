import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from supabase_admin_app import SupabaseAdminApp, _parse_monthly_price


class Entry:
    def __init__(self, text):
        self.text = text

    def get(self):
        return self.text

    def delete(self, *_args):
        self.text = ""

    def insert(self, _position, text):
        self.text = text


class AdminPricingTests(unittest.TestCase):
    def make_app(self, text="300"):
        app = SimpleNamespace(
            system_entries={"default_monthly_price": Entry(text),
                            "installer_url": Entry("rascunho sem validade")},
            system={"default_monthly_price": 250, "current_version": "1.9.4"},
            price_save_button=Mock(), publish_button=Mock(), price_feedback=Mock(),
            _render_kpis=Mock(), _show_error=Mock(),
            _request=Mock(return_value={"ok": True, "system": {"default_monthly_price": 300}}),
        )

        def run(operation, success, _busy, on_error):
            try:
                result = operation()
            except Exception as error:
                on_error(error)
            else:
                success(result)

        app._run = run
        return app

    def test_formats(self):
        for text, expected in [("300", 300), ("300,00", 300), ("300.00", 300),
                               ("R$ 1.300,50", 1300.5), ("0", 0)]:
            with self.subTest(text=text):
                self.assertEqual(_parse_monthly_price(text), expected)

    def test_invalid_values(self):
        for text in ["", "-300", "NaN", "inf", "1e3", "300,001", "1.2.3,00", "100000000"]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                _parse_monthly_price(text)

    def test_saves_only_price_and_ignores_ota_drafts(self):
        app = self.make_app()
        SupabaseAdminApp.save_monthly_price(app)
        app._request.assert_called_once_with("update_system_config", default_monthly_price=300.0)
        self.assertEqual(app.system["default_monthly_price"], 300)
        self.assertEqual(app.system["current_version"], "1.9.4")
        self.assertEqual(app.system_entries["installer_url"].get(), "rascunho sem validade")
        self.assertEqual(app.system_entries["default_monthly_price"].get(), "300,00")
        app._render_kpis.assert_called_once()
        self.assertFalse(app._price_saving)

    def test_failure_preserves_input_and_reenables_button(self):
        app = self.make_app()
        app._request.side_effect = RuntimeError("offline")
        SupabaseAdminApp.save_monthly_price(app)
        self.assertEqual(app.system["default_monthly_price"], 250)
        self.assertEqual(app.system_entries["default_monthly_price"].get(), "300")
        self.assertFalse(app._price_saving)
        app.price_save_button.configure.assert_called_with(state="normal", text="Salvar mensalidade")
        app._show_error.assert_called_once()

    def test_does_not_report_success_for_wrong_server_value(self):
        app = self.make_app()
        app._request.return_value = {"ok": True, "system": {"default_monthly_price": 250}}
        SupabaseAdminApp.save_monthly_price(app)
        self.assertEqual(app.system["default_monthly_price"], 250)
        app._render_kpis.assert_not_called()
        app._show_error.assert_called_once()

    def test_invalid_price_does_not_send_request(self):
        app = self.make_app("NaN")
        with patch("supabase_admin_app.messagebox.showwarning") as warning:
            SupabaseAdminApp.save_monthly_price(app)
        warning.assert_called_once()
        app._request.assert_not_called()

    def test_duplicate_click_does_not_send_request(self):
        app = self.make_app()
        app._price_saving = True
        SupabaseAdminApp.save_monthly_price(app)
        app._request.assert_not_called()

    def test_edits_made_during_request_are_preserved(self):
        app = self.make_app()

        def request(*_args, **_kwargs):
            app.system_entries["default_monthly_price"].text = "350"
            return {"ok": True, "system": {"default_monthly_price": 300}}

        app._request.side_effect = request
        SupabaseAdminApp.save_monthly_price(app)
        self.assertEqual(app.system_entries["default_monthly_price"].get(), "350")
        self.assertEqual(app.system["default_monthly_price"], 300)

    def test_refresh_preserves_unsaved_price(self):
        app = self.make_app()
        app._last_rendered_price_text = "250"
        app.force_update = Mock()
        app.maintenance = Mock()
        app._update_release_readiness = Mock()
        SupabaseAdminApp._render_system(app)
        self.assertEqual(app.system_entries["default_monthly_price"].get(), "300")

    def test_render_keeps_zero_visible(self):
        app = self.make_app()
        app.system["default_monthly_price"] = 0
        app.force_update = Mock()
        app.maintenance = Mock()
        app._update_release_readiness = Mock()
        SupabaseAdminApp._render_system(app)
        self.assertEqual(app.system_entries["default_monthly_price"].get(), "0")


if __name__ == "__main__":
    unittest.main()
