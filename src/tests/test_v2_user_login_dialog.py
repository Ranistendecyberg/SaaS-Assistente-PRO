import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QLineEdit

from src.core.supabase_desktop import DesktopBackendError
from src.ui.screens.user_login_dialog import UserLoginDialog


class UserLoginDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.auth = MagicMock()
        self.dialog = UserLoginDialog(self.auth)

    def tearDown(self):
        self.dialog.close()

    def test_password_is_masked(self):
        self.assertEqual(self.dialog.password.echoMode(), QLineEdit.EchoMode.Password)

    def test_incomplete_credentials_do_not_call_server(self):
        self.dialog.email.setText("invalido")
        self.dialog.password.setText("")
        with patch("src.ui.screens.user_login_dialog.QMessageBox.warning"):
            self.dialog._sign_in()
        self.auth.sign_in.assert_not_called()

    def test_supabase_invalid_credentials_has_clear_message(self):
        self.dialog.email.setText("usuario@empresa.com")
        self.dialog.password.setText("senha-invalida")
        self.auth.sign_in.side_effect = DesktopBackendError("INVALID_CREDENTIALS", 400)
        with patch("src.ui.screens.user_login_dialog.QMessageBox.warning") as warning:
            self.dialog._sign_in()
            while self.dialog._task is not None:
                self.app.processEvents()
        self.assertIn("E-mail ou senha incorretos", warning.call_args.args[2])


if __name__ == "__main__":
    unittest.main()
