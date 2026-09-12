from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class V2StorageIsolationTests(unittest.TestCase):
    def test_v2_never_reuses_v196_appdata_root(self):
        source = (ROOT / "src/core/paths.py").read_text("utf-8")
        self.assertIn('"SaasAssistentePRO-v2"', source)
        self.assertNotIn('os.path.join(appdata_path, "SaasAssistentePRO")', source)


if __name__ == "__main__":
    unittest.main()
