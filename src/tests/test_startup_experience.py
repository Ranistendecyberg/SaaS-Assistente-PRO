"""Abertura com confirmação de acesso embutida na tela de ativação."""

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtWebEngineWidgets
from PyQt6.QtWidgets import QApplication, QDialog

from src.version import __version__
from src.ui.screens.license_screen import LicenseScreen
from src.ui.screens.terms_dialog import TermsDialog


class StartupExperienceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def test_version_is_visible_on_first_windows(self):
        terms = TermsDialog(apenas_leitura=True)
        try:
            self.assertIn(__version__, terms.windowTitle())
        finally:
            terms.close()

    def test_valid_license_confirms_on_activation_screen(self):
        with patch("src.ui.screens.license_screen.LicenseManager"), \
                patch.object(LicenseScreen, "execute_async"):
            screen = LicenseScreen()
        try:
            screen.show()
            self.qt.processEvents()
            with patch("src.ui.screens.license_screen.QMessageBox.information") as info:
                screen._apply_initial_status({"status": "ativa", "dias_restantes": 129})
            info.assert_not_called()
            self.assertTrue(screen.isVisible())
            self.assertEqual(screen.result(), QDialog.DialogCode.Rejected)
            self.assertEqual(screen.lbl_loading_title.text(), "Acesso liberado!")
            self.assertEqual(screen.lbl_loading_description.text(), "Dias restantes: 129")
            self.assertTrue(screen.btn_continue.isVisible())
            self.assertIn(__version__, screen.windowTitle())
            self.assertEqual(screen.height(), 500)
            screen.btn_continue.click()
            self.assertEqual(screen.result(), QDialog.DialogCode.Accepted)
        finally:
            screen.close()

    def test_expired_license_shows_action_with_version_without_new_query(self):
        with patch("src.ui.screens.license_screen.LicenseManager"), \
                patch.object(LicenseScreen, "execute_async") as query, \
                patch("src.ui.screens.license_screen.QTimer.singleShot") as schedule:
            screen = LicenseScreen(initial_status={"status": "vencida"})
        try:
            schedule.assert_called_once()
            screen._apply_initial_status({"status": "vencida"})
            self.assertEqual(screen.stack.currentIndex(), 1)
            self.assertEqual(screen.height(), 600)
            self.assertIn(__version__, screen.windowTitle())
            query.assert_not_called()
        finally:
            screen.modo_startup = False
            screen.close()

    def test_startup_opens_activation_over_first_license_result(self):
        import src.main as entrypoint

        license_data = {"status": "ativa", "dias_restantes": 129, "system": {}}
        with patch.object(entrypoint.BackupManager, "criar_backup"), \
                patch.object(entrypoint, "QApplication") as app_type, \
                patch.object(entrypoint, "MainWindow") as main_window, \
                patch("src.ui.screens.terms_dialog.TermsDialog.verificar_aceite_previo", return_value=True), \
                patch("src.core.license_manager.LicenseManager") as manager_type, \
                patch("src.ui.screens.license_screen.LicenseScreen") as license_type, \
                patch("src.core.updater.Updater"), \
                patch("PyQt6.QtCore.QTimer.singleShot"):
            app_type.return_value.exec.return_value = 0
            license_type.return_value.exec.return_value = QDialog.DialogCode.Accepted
            manager_type.get_instance.return_value.precisa_configurar_primeiro_acesso.return_value = False
            manager_type.get_instance.return_value.validar_licenca.return_value = license_data
            self.assertEqual(entrypoint.main(), 0)

        manager_type.get_instance.return_value.validar_licenca.assert_called_once()
        license_type.assert_called_once_with(initial_status=license_data)
        license_type.return_value.exec.assert_called_once()
        main_window.return_value.show.assert_called_once()


if __name__ == "__main__":
    unittest.main()
