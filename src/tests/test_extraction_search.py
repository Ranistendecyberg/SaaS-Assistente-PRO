import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu")

from PyQt6.QtWidgets import QApplication, QComboBox, QLabel, QLineEdit, QListWidget

from src.ui.screens.extraction_screen import ExtractionScreen, _normalizar_texto_busca


class ExtractionSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _screen(self, query):
        combo = QComboBox()
        combo.addItems(["SSI", "TSI"])
        search = QLineEdit()
        search.setText(query)
        return SimpleNamespace(
            list_widget=QListWidget(),
            search_box=search,
            combo_tipo=combo,
            fila_extraida=[
                {"tipo": "SSI", "cliente": "JOSÉ DA SILVA", "os": "100"},
                {"tipo": "SSI", "cliente": "MARIA SOUZA", "os": "200"},
                {"tipo": "TSI", "cliente": "JOSEFA LIMA", "os": "300"},
            ],
            os_respondidas_tsi=set(),
            lbl_fila=QLabel(),
            _atualizar_resumo_selecao=lambda: None,
        )

    def test_normalization_ignores_case_accents_and_extra_spaces(self):
        self.assertEqual(_normalizar_texto_busca("  José   DA Silva "), "jose da silva")

    def test_list_filters_the_active_survey_by_client_name(self):
        screen = self._screen("jose")
        ExtractionScreen.atualizar_lista_ui(screen)

        self.assertEqual(screen.list_widget.count(), 1)
        self.assertIn("JOSÉ DA SILVA", screen.list_widget.item(0).text())
        self.assertEqual(screen.lbl_fila.text(), "  Fila de Disparo (1 Registros)")


if __name__ == "__main__":
    unittest.main()
