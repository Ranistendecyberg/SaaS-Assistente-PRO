import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from src.ui.screens.new_installation_screen import NewInstallationScreen


class V2OnboardingScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.manager = MagicMock()
        self.manager.get_hardware_id.return_value = "HARDWARE-123456"
        self.auth = MagicMock()
        with patch("src.ui.screens.new_installation_screen.LicenseManager", return_value=self.manager), \
             patch("src.ui.screens.new_installation_screen.SupabaseUserClient", return_value=self.auth):
            self.screen = NewInstallationScreen()

    def tearDown(self):
        self.screen.close()

    def test_default_mode_is_new_company_and_additional_mode_is_available(self):
        self.assertFalse(self.new_form_is_hidden())
        self.screen._show_mode("link")
        self.assertFalse(self.screen.link_form.isHidden())
        self.assertTrue(self.screen.new_form.isHidden())

    def new_form_is_hidden(self):
        return self.screen.new_form.isHidden()

    @patch("src.ui.screens.new_installation_screen.QMessageBox.information")
    def test_trial_result_saves_only_server_installation_token(self, _info):
        self.screen._trial_created({"installation_token": "t" * 64})
        self.manager.secure_backend.save_installation_token.assert_called_once_with("t" * 64)

    def test_new_company_validation_rejects_invalid_cnpj(self):
        self.screen.company.setText("Grupo Teste")
        self.screen.owner.setText("Responsável")
        self.screen.phone.setText("86999999999")
        self.screen.email.setText("cliente@example.com")
        self.screen.password.setText("SenhaSegura123")
        self.screen.password_confirmation.setText("SenhaSegura123")
        self.screen.cnpj.setText("11.111.111/1111-11")
        with self.assertRaisesRegex(ValueError, "CNPJ válido"):
            self.screen._validate_new_company()


if __name__ == "__main__":
    unittest.main()
