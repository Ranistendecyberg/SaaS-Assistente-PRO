"""Regressões dos sinais Qt usados por filtros e exportação de relatórios."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu")

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PyQt6.QtWidgets import QApplication, QWidget, QComboBox, QPushButton

from src.ui.dashboard_error_guard import protect_dashboard_action
from src.ui.screens.dashboard_tabs_screen import DashboardTabsScreen
from src.core.pdf_report_generator import PDFReportGenerator
from src.core.dashboard_engine import DashboardEngine
from src.ui.screens.dashboard_screen import DashboardScreen
import pandas as pd


class DashboardQtActionsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(["dashboard-tests"])

    def test_qt_signals_discard_unused_arguments_and_preserve_used_values(self):
        class Receiver:
            def __init__(self):
                self.calls = []

            @protect_dashboard_action("filter")
            def refresh(self):
                self.calls.append("refresh")

            @protect_dashboard_action("export")
            def export(self):
                self.calls.append("pdf")

            @protect_dashboard_action("context")
            def context(self, value=None):
                self.calls.append(value)

        receiver = Receiver()
        combo = QComboBox()
        combo.addItems(["Todas", "Loja A", "Loja B"])
        combo.currentTextChanged.connect(receiver.refresh)
        combo.currentTextChanged.connect(receiver.context)
        button = QPushButton()
        button.clicked.connect(receiver.export)
        with patch("src.ui.dashboard_error_guard.record_dashboard_error") as errors:
            combo.setCurrentIndex(1)
            combo.setCurrentIndex(2)
            button.click()
        errors.assert_not_called()
        self.assertEqual(receiver.calls, ["refresh", "Loja A", "refresh", "Loja B", "pdf"])

    def test_tab_construction_reentrancy_creates_only_one_panel(self):
        tabs = DashboardTabsScreen()
        calls = []

        class Panel(QWidget):
            def __init__(self):
                super().__init__()
                calls.append("create")
                tabs.on_tab_changed(0)

            def carregar_dados(self):
                calls.append("refresh")

        with patch("src.ui.screens.dashboard_tabs_screen.DashboardScreen", Panel):
            tabs.on_tab_changed(0)
            tabs.on_tab_changed(0)
        self.assertEqual(calls, ["create", "refresh"])
        self.assertEqual(tabs.layout_tsi.count(), 1)
        tabs.deleteLater()

    def test_retry_replaces_error_instead_of_appending_panel(self):
        tabs = DashboardTabsScreen()
        with patch("src.ui.screens.dashboard_tabs_screen.DashboardScreen", side_effect=ValueError), patch("src.ui.screens.dashboard_tabs_screen.record_dashboard_error", return_value="test"):
            tabs.on_tab_changed(0)
        self.assertEqual(tabs.layout_tsi.count(), 1)
        with patch("src.ui.screens.dashboard_tabs_screen.DashboardScreen", QWidget):
            tabs.on_tab_changed(0)
        self.assertEqual(tabs.layout_tsi.count(), 1)
        self.assertIs(tabs.layout_tsi.itemAt(0).widget(), tabs.dashboard_tsi)
        tabs.deleteLater()

    def test_tsi_filters_render_selected_store_and_pdf_click_reaches_dialog(self):
        class WebView(QWidget):
            def setHtml(self, html):
                self.html = html

        frame = pd.DataFrame({
            "Loja_Nome": ["Loja A", "Loja B"],
            "Consultor_Nome": ["Ana", "Bia"],
            "Mes": ["10/2026", "10/2026"],
            "Categoria Produto": ["Baixa", "Baixa"],
            "Loja_Meta": [95.0, 95.0],
            "Avaliação satisfação geral": [10, 8],
            "Avaliação satisfação instalações e infra": [10, 8],
        })
        with patch.object(DashboardEngine, "__init__", return_value=None), patch.object(DashboardEngine, "load_data", return_value=frame), patch("src.ui.screens.dashboard_screen.QWebEngineView", WebView), patch("src.ui.dashboard_error_guard.record_dashboard_error") as errors:
            screen = DashboardScreen()
            for store, score in (("Loja A", "100.00%"), ("Loja B", "80.00%")):
                screen.cb_loja.setCurrentText(store)
                self.assertIn("TSI " + score + " · 1 respostas", screen.web_view.html)
                self.assertNotIn("Não foi possível", screen.web_view.html)
            with patch("src.ui.screens.dashboard_screen.QFileDialog.getSaveFileName", return_value=("", "")) as dialog:
                next(b for b in screen.findChildren(QPushButton) if "PDF" in b.text()).click()
                dialog.assert_called_once()
            errors.assert_not_called()
            screen.deleteLater()

    @unittest.skipUnless(os.environ.get("SAAS_TEST_REAL_PDF") == "1", "Teste Chromium separado: SAAS_TEST_REAL_PDF=1")
    def test_real_chromium_pdf_exports(self):
        with tempfile.TemporaryDirectory(dir="tmp") as directory:
            metrics = {"total_respostas": 2, "top2box": 50.0, "ssi": 50.0, "nps": 0.0}
            for kind in ("tsi", "ssi", "comparativo"):
                with self.subTest(kind=kind):
                    path = str(Path(directory, kind + ".pdf").resolve())
                    if kind == "comparativo":
                        success = PDFReportGenerator.generate_comparativo_pdf(path, "<html><body><h1>Relatório Gerencial Geral</h1><p>Top2Box 50%</p></body></html>")
                    else:
                        success = getattr(PDFReportGenerator, "generate_" + kind + "_report")(path, "Loja Teste", "10/2026", metrics, [], [])
                    self.assertTrue(success)
                    self.assertTrue(Path(path).read_bytes().startswith(b"%PDF-"))
