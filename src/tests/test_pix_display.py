"""Testes de interface sem rede: nenhum pagamento real é criado."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
from decimal import Decimal
from unittest.mock import Mock, patch

from PyQt6.QtWidgets import QApplication
from src.ui.screens.license_screen import LicenseScreen, _confirmed_pix_amount, _pix_currency


class PixDisplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def setUp(self):
        with patch("src.ui.screens.license_screen.LicenseManager"), \
                patch.object(LicenseScreen, "execute_async"):
            self.screen = LicenseScreen(modo="chave")
        self.screen.manager = Mock()
        self.screen.execute_async = lambda task, callback: callback(task())
        self.error_patch = patch("src.ui.screens.license_screen.QMessageBox.critical")
        self.error = self.error_patch.start()

    def tearDown(self):
        self.screen.timer_pix.stop()
        self.screen.close()
        self.screen.deleteLater()
        self.qt.processEvents()
        self.error_patch.stop()

    def response(self, amount=300):
        return {"sucesso": True, "amount": amount, "payment_id": "TEST-LOCAL",
                "qr_code_str": "CODIGO-FICTICIO-SEM-VALOR"}

    def test_displays_server_amount_not_old_price(self):
        self.screen.valor_pix = 250
        self.screen.manager.gerar_pix.return_value = self.response(300)
        self.screen.gerar_pix()
        self.screen.manager.gerar_pix.assert_called_once_with()
        self.assertEqual(self.screen.lbl_pix_amount.text(), "Pagamento Mensalidade: R$ 300,00")
        self.assertEqual(self.screen.valor_pix, Decimal("300"))
        self.assertTrue(self.screen.timer_pix.isActive())
        self.error.assert_not_called()

    def test_individual_price_is_preserved(self):
        self.screen.manager.gerar_pix.return_value = self.response("100.50")
        self.screen.gerar_pix()
        self.assertIn("R$ 100,50", self.screen.lbl_pix_amount.text())

    def test_invalid_amount_does_not_expose_payment(self):
        for value in [None, "", "NaN", "Infinity", -1, 0, True, "300.001", "100000000"]:
            with self.subTest(value=value):
                self.screen.payment_id = "OLD"
                self.screen.str_copia_cola = "OLD-QR"
                self.screen.manager.gerar_pix.return_value = self.response(value)
                self.screen.gerar_pix()
                self.assertIsNone(self.screen.payment_id)
                self.assertEqual(self.screen.str_copia_cola, "")
                self.assertFalse(self.screen.timer_pix.isActive())
                self.assertEqual(self.screen.lbl_pix_amount.text(), "Valor não confirmado")
                self.assertTrue(self.screen.btn_pix.isEnabled())

    def test_failure_clears_previous_qr_and_value(self):
        self.screen.manager.gerar_pix.return_value = self.response()
        self.screen.gerar_pix()
        self.screen.manager.gerar_pix.return_value = {"sucesso": False, "mensagem": "Sem conexão"}
        self.screen.gerar_pix()
        self.assertTrue(self.screen.lbl_qr.pixmap().isNull())
        self.assertIsNone(self.screen.valor_pix)
        self.assertIsNone(self.screen.payment_id)
        self.assertEqual(self.screen.str_copia_cola, "")
        self.assertFalse(self.screen.timer_pix.isActive())

    def test_loading_has_no_cached_price_and_prevents_duplicates(self):
        self.screen.execute_async = Mock()
        self.screen.valor_pix = 250
        self.screen.gerar_pix()
        self.screen.gerar_pix()
        self.screen.execute_async.assert_called_once()
        self.assertEqual(self.screen.lbl_pix_amount.text(), "Consultando valor atualizado…")
        self.assertFalse(self.screen.btn_pix.isEnabled())

    def test_old_license_status_does_not_advertise_stale_price(self):
        self.screen.manager.validar_licenca.return_value = {
            "status": "vencida", "dias_restantes": 0, "valor_mensalidade": 250,
        }
        self.screen.buscar_status_silencioso()
        self.assertEqual(self.screen.btn_pix.text(), "Consultar valor e gerar PIX")
        self.screen.verificar_status_inicial()
        self.assertEqual(self.screen.btn_pix.text(), "Consultar valor e gerar PIX")

    def test_brazilian_currency_two_decimals(self):
        self.assertEqual(_pix_currency(_confirmed_pix_amount("1300.5")), "R$ 1.300,50")


if __name__ == "__main__":
    unittest.main()
