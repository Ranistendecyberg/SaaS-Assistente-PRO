import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from src.core.supabase_desktop import DesktopBackendError
from src.version import __version__
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
    def test_recovery_saves_returned_token_without_creating_trial(self, _info):
        self.screen._principal_recovered({"ok": True, "installation_token": "a" * 64})
        self.manager.secure_backend.save_installation_token.assert_called_once_with("a" * 64)
        self.auth.create_company_trial.assert_not_called()

    @patch("src.ui.screens.new_installation_screen.QMessageBox.warning")
    def test_invalid_recovery_does_not_save_token(self, _warning):
        self.screen._principal_recovered({"ok": True, "installation_token": "short"})
        self.manager.secure_backend.save_installation_token.assert_not_called()

    @patch("src.ui.screens.email_confirmation_dialog.EmailConfirmationDialog")
    @patch("src.ui.screens.user_login_dialog.UserLoginDialog")
    def test_cancel_login_never_recovers(self, login, confirmation):
        login.return_value.exec.return_value = 0
        self.screen._login_existing_account()
        confirmation.assert_not_called()
        self.auth.recover_principal_access.assert_not_called()

    @patch("src.ui.screens.email_confirmation_dialog.EmailConfirmationDialog")
    @patch("src.ui.screens.user_login_dialog.UserLoginDialog")
    def test_recovery_requires_login_and_email_confirmation(self, login, confirmation):
        login.return_value.exec.return_value = 1
        confirmation.return_value.exec.return_value = 1
        with patch.object(self.screen, "_run") as run:
            self.screen._login_existing_account()
        run.call_args.args[0]()
        self.auth.recover_principal_access.assert_called_once_with("HARDWARE-123456")

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

    def test_personal_account_accepts_valid_cpf(self):
        self.screen.company.setText("Titular Teste")
        self.screen.owner.setText("Titular Teste")
        self.screen.phone.setText("86999999999")
        self.screen.email.setText("teste@example.com")
        self.screen.password.setText("SenhaSegura123")
        self.screen.password_confirmation.setText("SenhaSegura123")
        self.screen.cnpj.setText("529.982.247-25")
        self.screen._validate_new_company()

    def test_email_link_confirmation_signs_in_before_creating_trial(self):
        self.screen._pending_email = "cliente@example.com"
        self.screen.password.setText("SenhaSegura123")
        with patch.object(self.screen, "_run") as run:
            self.screen._confirm_from_email_link()
        operation = run.call_args.args[0]
        operation()
        self.auth.sign_in.assert_called_once_with(
            "cliente@example.com", "SenhaSegura123"
        )

    def test_existing_confirmed_email_signs_in_instead_of_waiting_for_email(self):
        self.screen.company.setText("Grupo Teste")
        self.screen.owner.setText("Responsável")
        self.screen.phone.setText("86999999999")
        self.screen.email.setText("cliente@example.com")
        self.screen.password.setText("SenhaSegura123")
        self.screen.password_confirmation.setText("SenhaSegura123")
        self.screen.cnpj.setText("11.222.333/0001-81")
        self.auth.sign_up.return_value = {"user": {"id": "opaque"}}
        with patch.object(self.screen, "_run") as run:
            self.screen._start_signup()
        operation = run.call_args.args[0]
        self.assertEqual(operation(), {"authenticated": True})
        self.auth.sign_in.assert_called_once_with(
            "cliente@example.com", "SenhaSegura123"
        )

    def test_new_unconfirmed_email_still_opens_confirmation_step(self):
        self.screen.company.setText("Grupo Novo")
        self.screen.owner.setText("Responsável")
        self.screen.phone.setText("86999999999")
        self.screen.email.setText("novo@example.com")
        self.screen.password.setText("SenhaSegura123")
        self.screen.password_confirmation.setText("SenhaSegura123")
        self.screen.cnpj.setText("11.222.333/0001-81")
        self.auth.sign_up.return_value = {"user": {"id": "new"}}
        self.auth.sign_in.side_effect = DesktopBackendError("EMAIL_NOT_CONFIRMED", 400)
        with patch.object(self.screen, "_run") as run:
            self.screen._start_signup()
        self.assertEqual(run.call_args.args[0](), {"confirmation_required": True})

    def test_email_confirmation_accepts_eight_digit_otp(self):
        self.screen._pending_email = "cliente@example.com"
        self.screen.email_code.setText("12345678")
        with patch.object(self.screen, "_run") as run:
            self.screen._verify_email()
        operation = run.call_args.args[0]
        operation()
        self.auth.verify_signup.assert_called_once_with(
            "cliente@example.com", "12345678"
        )

    def test_additional_computer_requires_only_activation_code(self):
        self.screen._show_mode("link")
        self.assertFalse(hasattr(self.screen, "link_email"))
        self.assertFalse(hasattr(self.screen, "link_password"))
        self.assertEqual(self.screen.link_button.text(), "Ativar este computador")

    def test_additional_computer_normalizes_and_redeems_short_code(self):
        self.screen.link_code.setText("abcd 2345")
        with patch.object(self.screen, "_run") as run:
            self.screen._link_existing_company()
        operation = run.call_args.args[0]
        operation()
        self.manager.secure_backend.redeem_device_link_code.assert_called_once_with(
            "PC-ABCD-2345", __version__
        )
        self.auth.sign_in.assert_not_called()


if __name__ == "__main__":
    unittest.main()
