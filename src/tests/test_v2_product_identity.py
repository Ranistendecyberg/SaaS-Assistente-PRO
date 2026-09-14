from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class V2ProductIdentityTests(unittest.TestCase):
    def test_version_matches_installer(self):
        namespace = {}
        exec((ROOT / "src/version.py").read_text("utf-8"), namespace)
        version = namespace["__version__"]
        self.assertRegex(version, r"^2\.\d+\.\d+$")
        self.assertIn(f"AppVersion={version}\n", (ROOT / "criador_instalador.iss").read_text("utf-8"))

    def test_legacy_pix_store_is_not_in_sidebar(self):
        source = (ROOT / "src/ui/components/sidebar.py").read_text("utf-8")
        self.assertNotIn("Loja PIX (Recarga)", source)
        self.assertIn("Conta Empresarial", source)

    def test_consolidated_billing_replaces_legacy_tutorial_text(self):
        source = (ROOT / "src/ui/screens/tutorial_screen.py").read_text("utf-8")
        self.assertIn("Cobrança consolidada", source)
        self.assertNotIn("Loja PIX (Recarga)", source)

    def test_client_search_has_explicit_readable_text_colors(self):
        source = (ROOT / "src/ui/screens/extraction_screen.py").read_text("utf-8")
        search_style = source.split("self.search_box.setStyleSheet", 1)[1].split(
            "self.search_box.textChanged", 1
        )[0]
        self.assertIn("background-color: #FFFFFF", search_style)
        self.assertIn("color: #0F172A", search_style)
        self.assertIn("selection-background-color: #2563EB", search_style)
        self.assertIn("selection-color: #FFFFFF", search_style)

    def test_client_search_accepts_text_signal_and_normalizes_names(self):
        source = (ROOT / "src/ui/screens/extraction_screen.py").read_text("utf-8")
        self.assertIn("def filtrar_lista(self, _texto=None):", source)
        self.assertIn("texto_busca = _normalizar_texto_busca(self.search_box.text())", source)
        self.assertIn("texto_busca not in _normalizar_texto_busca(cliente)", source)


if __name__ == "__main__":
    unittest.main()
