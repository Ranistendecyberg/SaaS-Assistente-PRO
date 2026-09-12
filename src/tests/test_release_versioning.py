import tempfile
import unittest
from pathlib import Path

from update_version import update_release_version


class ReleaseVersioningTests(unittest.TestCase):
    def test_updates_desktop_and_installer_as_one_release(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "src").mkdir()
            (root / "src" / "version.py").write_text(
                '__version__ = "2.0.0-beta.1"\n', encoding="utf-8"
            )
            (root / "criador_instalador.iss").write_text(
                "[Setup]\n"
                "AppVersion=1.9.6\n"
                "OutputBaseFilename=Instalador_SaaS_Assistente_PRO_v1.9.6\n"
                "[Files]\n"
                'Source: "dist\\SaaS Assistente PRO v1.9.6.exe"; DestDir: "{app}"\n',
                encoding="utf-8",
            )

            update_release_version("2.0.0", root)

            self.assertEqual(
                (root / "src" / "version.py").read_text(encoding="utf-8"),
                '__version__ = "2.0.0"\n',
            )
            installer = (root / "criador_instalador.iss").read_text(encoding="utf-8")
            self.assertIn("AppVersion=2.0.0", installer)
            self.assertIn("Instalador_SaaS_Assistente_PRO_v2.0.0", installer)
            self.assertIn("SaaS Assistente PRO v2.0.0.exe", installer)

    def test_rejects_prerelease_for_official_installer(self):
        with self.assertRaisesRegex(ValueError, "formato 2.0.0"):
            update_release_version("2.0.0-beta.1", Path("."))


if __name__ == "__main__":
    unittest.main()
