import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from admin_supabase import SupabaseAuthError, friendly_auth_error
from supabase_admin_app import SupabaseAdminApp


class AdminLicenseActionsTests(unittest.TestCase):
    def _app(self, status):
        key_id = "2c6a63d9-43ce-4e60-a0df-e4fd209e05f2"
        app = SimpleNamespace(
            key_tree=SimpleNamespace(selection=lambda: (key_id,)),
            keys={key_id: {"status": status}},
            _request=Mock(return_value={"ok": True}),
            refresh_all=Mock(),
        )
        app._run = Mock()
        return app, key_id

    @patch("supabase_admin_app.messagebox.showinfo")
    def test_used_key_explains_manual_license_correction(self, showinfo):
        app, _key_id = self._app("used")

        SupabaseAdminApp.revoke_key(app)

        app._run.assert_not_called()
        self.assertIn("já foi utilizada", showinfo.call_args.args[1])
        self.assertIn("Licença e envios", showinfo.call_args.args[1])

    @patch("supabase_admin_app.messagebox.askyesno", return_value=True)
    def test_new_key_sends_internal_id_to_server(self, _askyesno):
        app, key_id = self._app("new")

        SupabaseAdminApp.revoke_key(app)

        app._run.assert_called_once()
        operation = app._run.call_args.args[0]
        operation()
        app._request.assert_called_once_with("revoke_key", key_id=key_id)

    def test_server_key_errors_are_translated(self):
        error = SupabaseAuthError("KEY_ALREADY_USED", status=409)
        self.assertIn("já foi utilizada", friendly_auth_error(error))


if __name__ == "__main__":
    unittest.main()
