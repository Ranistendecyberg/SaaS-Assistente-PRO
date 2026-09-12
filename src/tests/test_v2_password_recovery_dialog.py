import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from src.ui.screens.password_recovery_dialog import PasswordRecoveryDialog
from src.core.supabase_desktop import DesktopBackendError
from src.core.supabase_auth import PasswordRecoverySession


class PasswordRecoveryDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.auth = MagicMock()
        self.dialog = PasswordRecoveryDialog("Cliente@Example.com", auth=self.auth)

    def tearDown(self):
        self.dialog.close()

    def test_prefills_normalized_email(self):
        self.assertEqual(self.dialog.email.text(), "cliente@example.com")

    def test_update_validates_code_then_changes_password_with_temporary_token(self):
        self.dialog.code.setText("12345678")
        self.dialog.password.setText("NovaSenha123")
        self.dialog.confirmation.setText("NovaSenha123")
        with patch.object(self.dialog, "_run") as run:
            self.dialog._update_password()
        operation = run.call_args.args[0]
        self.auth.verify_password_recovery.return_value = PasswordRecoverySession(
            "temporary-token", "user-123", [],
        )
        self.assertEqual(operation(), {"changed": True})
        self.auth.verify_password_recovery.assert_called_once_with(
            "cliente@example.com", "12345678"
        )
        self.auth.update_recovered_password.assert_called_once_with(
            "temporary-token", "NovaSenha123"
        )

    def test_mfa_recovery_requires_authenticator_before_password_update(self):
        factor_id = "34e770dd-9ff9-416c-87fa-43b31d7ef225"
        recovery = PasswordRecoverySession(
            "aal1-token", "user-123", [{"id": factor_id}],
        )
        self.dialog.code.setText("12345678")
        self.dialog.password.setText("NovaSenha123")
        self.dialog.confirmation.setText("NovaSenha123")
        self.auth.verify_password_recovery.return_value = recovery
        with patch.object(self.dialog, "_run") as run:
            self.dialog._update_password()
        result = run.call_args.args[0]()
        self.dialog._recovery_verified(result)
        self.assertFalse(self.dialog.mfa_code.isHidden())
        self.assertFalse(self.dialog.code.isEnabled())

        self.dialog.mfa_code.setText("123456")
        self.auth.verify_recovery_totp.return_value = "aal2-token"
        with patch.object(self.dialog, "_run") as run:
            self.dialog._update_password()
        self.assertEqual(run.call_args.args[0](), {"changed": True})
        self.auth.verify_recovery_totp.assert_called_once_with(
            recovery, factor_id, "123456"
        )
        self.auth.update_recovered_password.assert_called_once_with(
            "aal2-token", "NovaSenha123"
        )

    def test_success_clears_sensitive_fields(self):
        self.dialog.code.setText("123456")
        self.dialog.password.setText("NovaSenha123")
        self.dialog.confirmation.setText("NovaSenha123")
        with patch("src.ui.screens.password_recovery_dialog.QMessageBox.information"):
            self.dialog._password_changed(None)
        self.assertEqual(self.dialog.code.text(), "")
        self.assertEqual(self.dialog.password.text(), "")
        self.assertEqual(self.dialog.confirmation.text(), "")

    @patch("src.ui.screens.password_recovery_dialog.record_event")
    @patch("src.ui.screens.password_recovery_dialog.QMessageBox.warning")
    def test_unknown_backend_error_exposes_only_safe_reference(self, warning, record):
        error = DesktopBackendError("UNEXPECTED_AUTH_STATE", 400)
        self.dialog._show_error(error)
        message = warning.call_args.args[2]
        self.assertIn("Referência técnica: UNEXPECTED_AUTH_STATE", message)
        record.assert_called_once_with(
            "authentication", "PASSWORD_RECOVERY_FAILED", "WARNING",
            error_code="UNEXPECTED_AUTH_STATE", http_status=400,
        )


if __name__ == "__main__":
    unittest.main()
