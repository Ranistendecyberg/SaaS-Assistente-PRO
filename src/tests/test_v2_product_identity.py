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


if __name__ == "__main__":
    unittest.main()
