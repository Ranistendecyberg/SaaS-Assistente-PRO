import json
import os
import tempfile
import unittest

from src.core.database import DatabaseManager


class DatabaseResilienceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = DatabaseManager.__new__(DatabaseManager)
        self.database.app_data_dir = self.temp_dir.name
        self.database.db_path = os.path.join(self.temp_dir.name, "historico_tsi.json")
        self.database.ssi_db_path = os.path.join(self.temp_dir.name, "historico_ssi.json")
        self.database.sent_path = os.path.join(self.temp_dir.name, "sent_surveys.json")

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def _write(path, text):
        with open(path, "w", encoding="utf-8") as stream:
            stream.write(text)

    def test_atomic_write_produces_valid_json_without_temporary_file(self):
        DatabaseManager._atomic_write_json(self.database.db_path, [{"os": "123"}])
        with open(self.database.db_path, "r", encoding="utf-8") as stream:
            self.assertEqual(json.load(stream), [{"os": "123"}])
        self.assertFalse(os.path.exists(f"{self.database.db_path}.tmp"))

    def test_corrupt_tsi_history_is_never_overwritten(self):
        original = '{"arquivo": '
        self._write(self.database.db_path, original)
        result = self.database.save_records([{"Ordens de Serviço: OS": "123"}])
        self.assertEqual(result, 0)
        with open(self.database.db_path, "r", encoding="utf-8") as stream:
            self.assertEqual(stream.read(), original)

    def test_corrupt_ssi_history_is_never_overwritten(self):
        original = "[conteudo interrompido"
        self._write(self.database.ssi_db_path, original)
        self.assertFalse(self.database.save_ssi_records([{"Ação": "/001234567890123"}]))
        with open(self.database.ssi_db_path, "r", encoding="utf-8") as stream:
            self.assertEqual(stream.read(), original)

    def test_corrupt_sent_history_is_never_overwritten(self):
        original = "dados inválidos"
        self._write(self.database.sent_path, original)
        self.assertFalse(self.database.mark_survey_as_sent("survey-1"))
        with open(self.database.sent_path, "r", encoding="utf-8") as stream:
            self.assertEqual(stream.read(), original)

    def test_tsi_deduplication_is_preserved_with_atomic_save(self):
        DatabaseManager._atomic_write_json(
            self.database.db_path,
            [{"Ordens de Serviço: OS": "00123", "Cliente": "Anterior"}],
        )
        added = self.database.save_records([
            {"Ordens de Serviço: OS": "123", "Cliente": "Atualizado"},
            {"Ordens de Serviço: OS": "456", "Cliente": "Novo"},
        ])
        self.assertEqual(added, 1)
        records = self.database.load_all_records()
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["Cliente"], "Atualizado")


if __name__ == "__main__":
    unittest.main()
