import os
import unittest
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from src.ui.screens.mfa_dialog import MfaDialog


class MfaDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.dialog = MfaDialog(MagicMock())

    def tearDown(self):
        self.dialog.close()

    def test_new_totp_qr_is_rendered_from_png_memory(self):
        self.dialog._enrollment_ready({
            "id": "factor-1",
            "totp": {
                "uri": "otpauth://totp/SaaS:test@example.com?secret=JBSWY3DPEHPK3PXP",
                "secret": "JBSWY3DPEHPK3PXP",
            },
        })
        self.assertFalse(self.dialog.qr_label.pixmap().isNull())
        self.assertTrue(self.dialog.qr_label.isVisibleTo(self.dialog))
        self.assertIn("Chave manual", self.dialog.secret_label.text())
        self.assertTrue(self.dialog.code.isEnabled())


if __name__ == "__main__":
    unittest.main()
