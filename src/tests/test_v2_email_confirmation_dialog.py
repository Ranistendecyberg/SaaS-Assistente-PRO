import os
import unittest
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from src.ui.screens.email_confirmation_dialog import EmailConfirmationDialog


class EmailConfirmationDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.auth = Mock()
        self.dialog = EmailConfirmationDialog(self.auth)

    def tearDown(self):
        self.dialog.close()

    def test_masks_email_and_prepares_numeric_code_field(self):
        self.assertEqual(
            self.dialog._masked_email("cliente@example.com"),
            "cl*****@example.com",
        )
        self.assertEqual(self.dialog.code.maxLength(), 24)
        self.assertFalse(self.dialog.code.isEnabled())

    def test_code_sent_enables_confirmation_without_exposing_full_email(self):
        self.dialog._code_sent("cliente@example.com")
        self.assertTrue(self.dialog.code.isEnabled())
        self.assertTrue(self.dialog.confirm.isEnabled())
        self.assertIn("cl*****@example.com", self.dialog.instructions.text())
        self.assertNotIn("cliente@example.com", self.dialog.instructions.text())

    def test_valid_code_is_forwarded_without_spaces(self):
        self.dialog._email = "cliente@example.com"
        self.dialog._requested = True
        self.dialog.code.setText("12 34 56 78")
        self.dialog._run = Mock()
        self.dialog._verify()
        operation, success = self.dialog._run.call_args.args
        self.auth.verify_operation_confirmation.return_value = "session"
        self.assertEqual(operation(), "session")
        self.auth.verify_operation_confirmation.assert_called_once_with(
            "cliente@example.com", "12345678",
        )
        self.assertEqual(success, self.dialog._verified)


if __name__ == "__main__":
    unittest.main()
