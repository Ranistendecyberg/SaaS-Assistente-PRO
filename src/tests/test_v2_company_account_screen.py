import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QSizePolicy
from PyQt6.QtWidgets import QMessageBox

from src.core.supabase_desktop import DesktopBackendError
from src.ui.screens.company_account_screen import CompanyAccountScreen


class CompanyAccountScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.auth = MagicMock()
        self.screen = CompanyAccountScreen(auth_client=self.auth)

    def tearDown(self):
        self.screen.close()

    @staticmethod
    def summary(role="owner"):
        return {
            "ok": True,
            "role": role,
            "company": {
                "id": "company-1", "name": "Grupo Teste",
                "manager_name": "Responsável", "phone": "86999999999",
            },
            "units": [{
                "id": "unit-1", "display_name": "Matriz", "unit_type": "headquarters",
                "cnpj": "27588108000101", "active": True,
            }],
            "installations": [
                {
                    "id": "pc-1", "business_unit_id": "unit-1", "hardware_id": "HARDWARE-PRINCIPAL-123",
                    "device_class": "principal", "billing_status": "active", "app_version": "2.0.0",
                },
                {
                    "id": "pc-2", "business_unit_id": "unit-1", "hardware_id": "HARDWARE-ADICIONAL-456",
                    "device_class": "additional", "billing_status": "active", "app_version": "2.0.0",
                },
            ],
            "subscription": {
                "status": "trial", "base_price": "300.00", "additional_seat_price": "50.00",
                "trial_expires_at": "2099-09-04T10:00:00+00:00",
            },
            "invoices": [],
        }

    def test_summary_renders_company_seats_units_and_consolidated_price(self):
        self.screen._render_summary(self.summary())
        self.assertEqual(self.screen.company_name.text(), "Grupo Teste")
        self.assertEqual(self.screen.status_value.text(), "Teste gratuito")
        self.assertEqual(self.screen.devices_value.text(), "2")
        self.assertEqual(self.screen.price_value.text(), "R$ 350,00")
        self.assertEqual(self.screen.units_table.rowCount(), 1)
        self.assertEqual(self.screen.devices_table.rowCount(), 2)
        self.assertTrue(self.screen.link_button.isEnabled())
        self.assertTrue(self.screen.billing_button.isEnabled())

    def test_banner_reserves_width_for_account_identity(self):
        self.screen._render_summary(self.summary())
        self.screen.resize(1100, 850)
        self.screen.show()
        self.app.processEvents()
        self.assertGreater(self.screen.company_name.width(), 200)
        self.assertGreater(self.screen.company_meta.width(), 200)

    def test_operator_can_view_but_cannot_mutate_company(self):
        self.screen._render_summary(self.summary(role="operator"))
        self.assertFalse(self.screen.link_button.isEnabled())
        self.assertFalse(self.screen.remove_button.isEnabled())
        self.assertEqual(self.screen.role_badge.text(), "Operador")

    def test_only_owner_can_transfer_principal(self):
        self.screen._render_summary(self.summary(role="admin"))
        self.assertTrue(self.screen.remove_button.isEnabled())
        self.assertFalse(self.screen.transfer_principal_button.isEnabled())

        self.screen._render_summary(self.summary(role="owner"))
        self.assertTrue(self.screen.transfer_principal_button.isEnabled())

    def test_company_banner_keeps_compact_height(self):
        self.assertEqual(self.screen.banner.height(), 112)
        self.assertEqual(
            self.screen.banner.sizePolicy().verticalPolicy(),
            QSizePolicy.Policy.Fixed,
        )
        self.assertEqual(
            self.screen.role_badge.sizePolicy().verticalPolicy(),
            QSizePolicy.Policy.Fixed,
        )
        self.assertTrue(self.screen.billing_button.isEnabled())

    def test_link_code_is_requested_for_selected_unit(self):
        self.screen._render_summary(self.summary())
        self.screen._run = MagicMock()
        self.screen.issue_link_code()
        operation = self.screen._run.call_args.args[0]
        operation()
        self.auth.issue_device_link_code.assert_called_once_with("company-1", "unit-1")

    def test_link_code_does_not_request_a_second_email_confirmation(self):
        self.screen._render_summary(self.summary())
        self.screen._run = MagicMock()
        self.screen._run_secured = MagicMock()
        self.screen.issue_link_code()
        self.screen._run.assert_called_once()
        self.screen._run_secured.assert_not_called()

    def test_expired_subscription_disables_new_computer_with_clear_reason(self):
        summary = self.summary()
        summary["subscription"]["trial_expires_at"] = "2026-09-04T10:00:00+00:00"
        self.screen._render_summary(summary)
        self.assertFalse(self.screen.link_button.isEnabled())
        self.assertEqual(self.screen.link_button.text(), "Assinatura vencida")
        self.assertIn("04/09/2026", self.screen.link_price_hint.text())
        self.assertEqual(self.screen.status_value.text(), "Teste vencido")

    def test_new_computer_price_is_explained_before_code_generation(self):
        self.screen._render_summary(self.summary())
        hint = self.screen.link_price_hint.text()
        self.assertIn("Valor atual: R$ 350,00/mês", hint)
        self.assertIn("Com o próximo computador: R$ 400,00/mês", hint)
        self.assertIn("+ R$ 50,00", hint)

    def test_small_window_exposes_vertical_page_scroll_without_horizontal_scroll(self):
        self.screen._render_summary(self.summary())
        self.screen.resize(900, 560)
        self.screen.show()
        self.app.processEvents()
        self.assertGreater(self.screen.scroll_area.verticalScrollBar().maximum(), 0)
        self.assertEqual(self.screen.scroll_area.horizontalScrollBar().maximum(), 0)

    def test_missing_session_opens_login_then_refreshes_account(self):
        self.auth.load_session.return_value = None
        self.screen.refresh_data = MagicMock()
        with patch("src.ui.screens.user_login_dialog.UserLoginDialog") as login_dialog:
            login_dialog.return_value.exec.return_value = 1
            self.screen._ensure_authenticated()
        login_dialog.assert_called_once_with(self.auth, self.screen)
        self.screen.refresh_data.assert_called_once_with()

    def test_user_without_company_can_switch_account(self):
        self.screen._ensure_authenticated = MagicMock()
        with patch(
            "src.ui.screens.company_account_screen.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ) as question, patch(
            "src.ui.screens.company_account_screen.QTimer.singleShot"
        ) as schedule:
            self.screen._handle_refresh_failure(DesktopBackendError("COMPANY_REQUIRED"))
        self.assertIn("não está cadastrado", question.call_args.args[2])
        self.assertIn("outro e-mail", question.call_args.args[2])
        self.auth.clear_session.assert_called_once_with()
        schedule.assert_called_once()


if __name__ == "__main__":
    unittest.main()
