import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from src.core.database import DatabaseManager
from src.ui.main_window import MainWindow


class _Signal:
    def __init__(self):
        self.connections = []

    def connect(self, callback):
        self.connections.append(callback)


class _Lazy:
    def __init__(self, value):
        self.value = value

    def screen(self):
        return self.value


class ScalabilityRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _database(self):
        database = DatabaseManager.__new__(DatabaseManager)
        database.app_data_dir = self.temp_dir.name
        database.db_path = os.path.join(self.temp_dir.name, "historico_tsi.json")
        database.ssi_db_path = os.path.join(self.temp_dir.name, "historico_ssi.json")
        database.sent_path = os.path.join(self.temp_dir.name, "sent_surveys.json")
        return database

    def test_history_cache_observes_writes_from_another_manager(self):
        first = self._database()
        second = self._database()
        DatabaseManager._atomic_write_json(first.db_path, [
            {"Ordens de Serviço: OS": "100", "Cliente": "Primeiro"},
        ])

        self.assertEqual(len(first.load_all_records()), 1)
        second.save_records([
            {"Ordens de Serviço: OS": "200", "Cliente": "Segundo registro"},
        ])

        self.assertEqual(len(first.load_all_records()), 2)

    def test_lead_index_is_rebuilt_after_mapping_save(self):
        database = self._database()
        database.save_leads_mapping([{
            "cliente": "Cliente antigo", "telefone": "111", "os": "12345",
            "os_full": "12345", "tipo": "TSI", "id": "lead-1",
        }])
        self.assertEqual(database.find_lead("12345", tipo="TSI")["cliente"], "Cliente antigo")

        database.save_leads_mapping([{
            "cliente": "Cliente atualizado", "telefone": "222", "os": "12345",
            "os_full": "12345", "tipo": "TSI", "id": "lead-1",
        }])

        self.assertEqual(database.find_lead("12345", tipo="TSI")["cliente"], "Cliente atualizado")

    def test_lazy_runtime_signals_are_connected_once(self):
        extraction = SimpleNamespace(
            sig_dispatch_whatsapp=_Signal(),
            sig_request_tab_change=_Signal(),
            sig_check_whatsapp_login=_Signal(),
            sig_iniciar_conversa_individual=_Signal(),
            on_whatsapp_message_sent=lambda: None,
            on_whatsapp_phone_unavailable=lambda: None,
            on_login_status_result=lambda: None,
            on_link_individual_enviado=lambda: None,
        )
        whatsapp = SimpleNamespace(
            sig_message_sent=_Signal(),
            sig_phone_unavailable=_Signal(),
            sig_login_status_result=_Signal(),
            sig_link_individual_enviado=_Signal(),
            send_message=lambda: None,
            check_login_status=lambda: None,
            abrir_conversa_cliente=lambda: None,
        )
        host = SimpleNamespace(
            _runtime_screens_connected=False,
            _lazy_extraction=_Lazy(extraction),
            _lazy_whatsapp=_Lazy(whatsapp),
            force_tab_change=lambda: None,
        )

        self.assertTrue(MainWindow._connect_runtime_screens_if_ready(host))
        self.assertFalse(MainWindow._connect_runtime_screens_if_ready(host))
        signals = [
            extraction.sig_dispatch_whatsapp,
            extraction.sig_request_tab_change,
            extraction.sig_check_whatsapp_login,
            extraction.sig_iniciar_conversa_individual,
            whatsapp.sig_message_sent,
            whatsapp.sig_phone_unavailable,
            whatsapp.sig_login_status_result,
            whatsapp.sig_link_individual_enviado,
        ]
        self.assertTrue(all(len(signal.connections) == 1 for signal in signals))

    def test_backend_maintenance_is_batched_and_service_only(self):
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        migration = Path(root, "supabase", "migrations", "028_v2_telemetry_cleanup.sql").read_text(
            encoding="utf-8"
        )
        worker = Path(root, "supabase", "functions", "cron-worker", "index.ts").read_text(
            encoding="utf-8"
        )

        self.assertIn("public.telemetry_events", migration)
        self.assertIn("for update skip locked", migration.lower())
        self.assertIn("installations_due_removal_idx", migration)
        self.assertIn("to service_role", migration.lower())
        self.assertIn('client.rpc("cleanup_expired_telemetry"', worker)
        self.assertIn('client.rpc("cleanup_completed_message_reservations"', worker)
        self.assertIn('client.rpc("process_due_device_removals_server"', worker)
        self.assertIn('Deno.env.get("CRON_SECRET")', worker)
        self.assertNotIn("Deno.cron(", worker)
        self.assertNotIn("console.log(Processando", worker)
        self.assertIn("cron.schedule", migration)

        lock_order = Path(
            root, "supabase", "migrations", "029_v2_installation_lock_order.sql"
        ).read_text(encoding="utf-8")
        update_branch = lock_order.split("if TG_OP = 'UPDATE' then", 1)[1].split(
            "if TG_OP = 'DELETE' then", 1
        )[0]
        self.assertNotIn("for update", update_branch.lower())
        self.assertIn("COMPANY_TRANSFER_NOT_ALLOWED", update_branch)

        config = Path(root, "supabase", "config.toml").read_text(encoding="utf-8")
        self.assertIn("[functions.cron-worker]", config)

        account_api = Path(root, "supabase", "functions", "account-api", "index.ts").read_text(
            encoding="utf-8"
        )
        screen = Path(root, "src", "ui", "screens", "company_account_screen.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('ownerOnly: action === "transfer_principal"', account_api)
        self.assertIn("can_transfer_principal(self._role)", screen)


if __name__ == "__main__":
    unittest.main()
