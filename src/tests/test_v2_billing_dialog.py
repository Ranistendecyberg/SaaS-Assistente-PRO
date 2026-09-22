import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from src.core.supabase_desktop import DesktopBackendError
from src.ui.screens.billing_dialog import BillingDialog


class BillingDialogTests(unittest.TestCase):
    def test_provider_check_uses_attempt_then_reloads_summary(self):
        dialog = self.create_dialog()
        dialog._status_attempt_id = "attempt-1"
        dialog.auth.refresh_company_payment.return_value = {"result": {"invoice_status": "paid"}}
        dialog.auth.billing_summary.return_value = {
            "payment_environment": "production", "invoices": [],
        }
        with patch.object(dialog, "_run", side_effect=lambda operation, done: done(operation())), \
                patch("src.ui.screens.billing_dialog.QMessageBox.information") as information:
            dialog._check_provider_status()
        dialog.auth.refresh_company_payment.assert_called_once_with("company-1", "attempt-1")
        self.assertIn("Pagamento confirmado", dialog.result.text())
        self.assertIn("Pagamento confirmado", information.call_args.args[2])

    def test_provider_check_reports_pending_result(self):
        dialog = self.create_dialog()
        dialog._status_attempt_id = "attempt-1"
        dialog.auth.refresh_company_payment.return_value = {
            "result": {"invoice_status": "open", "attempt_status": "pending"},
        }
        dialog.auth.billing_summary.return_value = {
            "payment_environment": "test",
            "invoices": [{
                "status": "open", "total_amount": "50.00",
                "billing_payment_attempts": [{
                    "id": "attempt-1", "payment_method": "pix",
                    "provider_environment": "test", "status": "pending",
                    "payable": True, "pix_copy_paste": "000201TESTE",
                }],
            }],
        }
        with patch.object(dialog, "_run", side_effect=lambda operation, done: done(operation())), \
                patch("src.ui.screens.billing_dialog.QMessageBox.information") as information:
            dialog._check_provider_status()
        self.assertIn("ainda aguarda confirmação", dialog.result.text())
        self.assertIn("Não gere outro PIX", dialog.result.text())
        self.assertIn("ainda aguarda confirmação", information.call_args.args[2])

    def test_provider_check_names_pending_boleto_correctly(self):
        dialog = self.create_dialog()
        dialog._status_attempt_id = "attempt-1"
        dialog.auth.refresh_company_payment.return_value = {
            "result": {"invoice_status": "open", "attempt_status": "pending"},
        }
        dialog.auth.billing_summary.return_value = {
            "payment_environment": "test",
            "invoices": [{
                "status": "open", "total_amount": "50.00",
                "billing_payment_attempts": [{
                    "id": "attempt-1", "payment_method": "boleto",
                    "provider_environment": "test", "status": "pending",
                    "payable": True, "boleto_barcode": "23790000000000000000000000000000000000000000000",
                    "payment_url": "https://example.test/boleto",
                }],
            }],
        }
        with patch.object(dialog, "_run", side_effect=lambda operation, done: done(operation())), \
                patch("src.ui.screens.billing_dialog.QMessageBox.information") as information:
            dialog._check_provider_status()
        message = information.call_args.args[2]
        self.assertIn("Não gere outro boleto", message)
        self.assertNotIn("outro PIX", message)

    def test_non_owner_cannot_query_provider(self):
        dialog = self.create_dialog("member")
        dialog._status_attempt_id = "attempt-1"
        dialog._set_busy(False)
        self.assertFalse(dialog.check_status_button.isEnabled())
        dialog._check_provider_status()
        dialog.auth.refresh_company_payment.assert_not_called()

    def test_nonpayable_pending_still_allows_status_check(self):
        dialog = self.create_dialog()
        dialog._loaded({"payment_environment": "production", "invoices": [{"status": "open", "total_amount": "350.00",
            "billing_payment_attempts": [{"id": "pending-1", "status": "pending",
                "provider_environment": "production", "payable": False}]}]})
        dialog._set_busy(False)
        self.assertTrue(dialog.check_status_button.isEnabled())
        self.assertFalse(dialog.copy_button.isEnabled())

    def test_nonpayable_legacy_message_does_not_claim_provider_cancellation(self):
        message = BillingDialog._unavailable_payment_message({"status": "open"}, {"status": "pending", "payable": False})
        self.assertIn("não está confirmado", message)

    def test_payment_messages_distinguish_local_states(self):
        for status, expected in (("cancelled", "cancelada no sistema"), ("expired", "expirada"), ("refunded", "devolvido"), ("rejected", "recusada")):
            with self.subTest(status=status):
                self.assertIn(expected, BillingDialog._unavailable_payment_message({"status": "open"}, {"status": status}))

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def create_dialog(self, role="owner"):
        with patch.object(BillingDialog, "_load"):
            dialog = BillingDialog(MagicMock(), "company-1", role)
        self.addCleanup(dialog.close)
        return dialog

    def test_owner_can_edit_profile_and_choose_pix_or_boleto(self):
        dialog = self.create_dialog("owner")
        self.assertTrue(dialog.save_button.isEnabled())
        self.assertTrue(dialog.pix_button.isEnabled())
        self.assertTrue(dialog.boleto_button.isEnabled())
        self.assertEqual(set(dialog.fields), {
            "legal_name", "billing_cnpj", "billing_email", "postal_code",
            "street", "street_number", "address_extra", "neighborhood",
            "city", "state",
        })

    def test_non_owner_has_read_only_billing_actions(self):
        dialog = self.create_dialog("admin")
        self.assertFalse(dialog.save_button.isEnabled())
        self.assertFalse(dialog.pix_button.isEnabled())
        self.assertFalse(dialog.boleto_button.isEnabled())

    def test_pending_attempt_exposes_only_provider_payment_data(self):
        dialog = self.create_dialog("owner")
        dialog._show_attempt(
            {"total_amount": "350.00"},
            {
                "payment_method": "pix",
                "pix_copy_paste": "000201TESTE",
                "payment_url": "https://example.invalid/payment",
            },
            reused=True,
        )
        dialog._set_busy(False)
        self.assertIn("R$ 350,00", dialog.result.text())
        self.assertIn("reaproveitada", dialog.result.text())
        self.assertTrue(dialog.copy_button.isEnabled())
        self.assertTrue(dialog.open_button.isEnabled())
        self.assertFalse(dialog.qr_label.isHidden())
        self.assertFalse(dialog.qr_label.pixmap().isNull())

    def test_boleto_does_not_show_pix_qr_code(self):
        dialog = self.create_dialog("owner")
        dialog._show_attempt(
            {"total_amount": "350.00"},
            {
                "payment_method": "boleto",
                "boleto_barcode": "00190000090000000000000000000000000000000000",
            },
        )
        self.assertTrue(dialog.qr_label.isHidden())
        self.assertTrue(dialog.qr_label.pixmap().isNull())

    def test_test_environment_is_clearly_identified(self):
        dialog = self.create_dialog("owner")
        dialog._loaded({"payment_environment": "test", "invoices": []})
        self.assertIn("AMBIENTE DE TESTE", dialog.environment_banner.text())
        self.assertIn("não movimentam dinheiro real", dialog.environment_banner.text())
        dialog._show_attempt(
            {"total_amount": "1.00"},
            {
                "payment_method": "pix",
                "provider_environment": "test",
                "pix_copy_paste": "000201TESTE",
            },
        )
        self.assertIn("AMBIENTE DE TESTE", dialog.result.text())
        self.assertIn("não movimenta dinheiro real", dialog.result.text())

    def test_test_boleto_explains_sandbox_and_labels_actions(self):
        dialog = self.create_dialog("owner")
        dialog._loaded({"payment_environment": "test", "invoices": []})
        dialog._show_attempt(
            {"id": "invoice-1", "status": "open", "total_amount": "50.00"},
            {
                "id": "attempt-1", "payment_method": "boleto",
                "provider_environment": "test", "status": "pending",
                "payable": True,
                "boleto_barcode": "23790000000000000000000000000000000000000000000",
                "payment_url": "https://example.test/boleto",
            },
        )
        self.assertIn("linha digitável foi recebida", dialog.result.text())
        self.assertIn("sandbox", dialog.result.text())
        self.assertEqual(dialog.copy_button.text(), "Copiar linha digitável")
        self.assertEqual(dialog.open_button.text(), "Abrir boleto no Mercado Pago")

    def test_production_environment_warns_that_charge_is_real(self):
        dialog = self.create_dialog("owner")
        dialog._loaded({"payment_environment": "production", "invoices": []})
        self.assertIn("AMBIENTE DE PRODUÇÃO", dialog.environment_banner.text())
        self.assertIn("cobranças reais", dialog.environment_banner.text())

    def test_provider_error_displays_safe_support_codes(self):
        dialog = self.create_dialog("owner")
        error = DesktopBackendError("PAYMENT_PROVIDER_ERROR", 502, {
            "provider_code": "payer_email_invalid",
            "support_code": "request-123",
        })
        with patch("src.ui.screens.billing_dialog.QMessageBox.warning") as warning:
            dialog._show_error(error)
        message = warning.call_args.args[2]
        self.assertIn("payer_email_invalid", message)
        self.assertIn("request-123", message)

    def test_changed_device_total_hides_old_pix_and_requests_new_charge(self):
        with patch.object(BillingDialog, "_load"):
            dialog = BillingDialog(
                MagicMock(), "company-1", "owner", estimated_amount="400.00",
            )
        self.addCleanup(dialog.close)
        dialog._loaded({
            "payment_environment": "production",
            "profile": None,
            "invoices": [{
                "total_amount": "350.00",
                "billing_payment_attempts": [{
                    "payment_method": "pix",
                    "status": "pending",
                    "pix_copy_paste": "000201PIX-ANTIGO",
                }],
            }],
        })
        self.assertEqual(dialog._payment_code(), "")
        self.assertTrue(dialog.qr_label.isHidden())
        self.assertIn("R$ 350,00", dialog.result.text())
        self.assertIn("R$ 400,00", dialog.result.text())
        self.assertEqual(dialog.pix_button.text(), "Gerar PIX com valor atualizado")

    def test_expired_or_cancelled_payment_cannot_be_copied(self):
        for attempt in (
            {"status": "cancelled"},
            {"status": "pending", "expires_at": "2020-01-01T00:00:00Z"},
            {"status": "pending", "expires_at": "not-a-date"},
            {"status": "pending", "payable": False},
        ):
            with self.subTest(attempt=attempt):
                dialog = self.create_dialog()
                dialog._show_attempt({"total_amount": "300.00"},
                    {**attempt, "payment_method": "pix", "pix_copy_paste": "OLD-QR"})
                dialog._set_busy(False)
                self.assertEqual(dialog._payment_code(), "")
                self.assertFalse(dialog.copy_button.isEnabled())
                self.assertTrue(dialog.qr_label.isHidden())

    def test_invalid_amount_clears_previous_qr(self):
        dialog = self.create_dialog()
        dialog._show_attempt({"total_amount": "300"}, {"payment_method": "pix", "pix_copy_paste": "QR"})
        for amount in ("NaN", "Infinity", "-1", "0", "300.001"):
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                dialog._show_attempt({"total_amount": amount}, {"pix_copy_paste": "UNSAFE"})
            self.assertEqual(dialog._payment_code(), "")
            self.assertTrue(dialog.qr_label.isHidden())

    def test_server_reconciliation_disables_new_payments(self):
        dialog = self.create_dialog()
        dialog._loaded({"payment_environment": "production", "reconciliation_required": True})
        dialog._set_busy(False)
        self.assertFalse(dialog.pix_button.isEnabled())
        self.assertFalse(dialog.boleto_button.isEnabled())
        self.assertIn("Não pague novamente", dialog.result.text())

    def test_payment_link_rejects_local_and_unencrypted_urls(self):
        dialog = self.create_dialog()
        for url in ("file:///C:/Windows/cmd.exe", "javascript:alert(1)", "http://example.com"):
            dialog._last_attempt = {"payment_url": url}
            self.assertEqual(dialog._payment_url(), "")

    def test_company_defaults_and_estimated_amount_are_visible_before_payment(self):
        with patch.object(BillingDialog, "_load"):
            dialog = BillingDialog(
                MagicMock(), "company-1", "owner",
                defaults={
                    "legal_name": "Grupo Ipe Motos",
                    "billing_cnpj": "27.588.108/0001-01",
                },
                estimated_amount="300.00",
            )
        self.addCleanup(dialog.close)
        dialog._loaded({"payment_environment": "production", "profile": None, "invoices": []})
        self.assertEqual(dialog.fields["legal_name"].text(), "Grupo Ipe Motos")
        self.assertEqual(dialog.fields["billing_cnpj"].text(), "27.588.108/0001-01")
        self.assertEqual(dialog.amount_value.text(), "R$ 300,00")
        self.assertFalse(dialog.copy_button.isEnabled())
        self.assertFalse(dialog.open_button.isEnabled())


if __name__ == "__main__":
    unittest.main()
