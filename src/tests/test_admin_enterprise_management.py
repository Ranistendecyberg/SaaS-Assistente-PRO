from pathlib import Path
import unittest

from admin_supabase import (
    SupabaseAuthError, enterprise_monthly_total, friendly_auth_error,
)


ROOT = Path(__file__).resolve().parents[2]


class AdminEnterpriseManagementTests(unittest.TestCase):
    def test_consolidated_total_counts_principal_and_each_billable_additional(self):
        subscription = {"base_price": 300, "additional_seat_price": 50}
        installations = [
            {"device_class": "principal", "billing_status": "active"},
            {"device_class": "additional", "billing_status": "active"},
            {"device_class": "additional", "billing_status": "pending_removal"},
            {"device_class": "additional", "billing_status": "removed"},
        ]
        self.assertEqual(enterprise_monthly_total(subscription, installations), 400)

    def test_blocked_device_remains_billable_until_removed(self):
        subscription = {"base_price": 300, "additional_seat_price": 50}
        installations = [
            {"device_class": "principal", "billing_status": "active"},
            {"device_class": "additional", "billing_status": "blocked"},
        ]
        self.assertEqual(enterprise_monthly_total(subscription, installations), 350)

    def test_admin_api_uses_mfa_protected_mutations_and_server_rpcs(self):
        source = (ROOT / "supabase/functions/admin-api/index.ts").read_text("utf-8")
        self.assertIn('"update_enterprise_subscription"', source)
        self.assertIn('"set_enterprise_device_status"', source)
        self.assertIn('rpc("admin_update_company_subscription_server"', source)
        self.assertIn('rpc("admin_set_enterprise_device_status_server"', source)

    def test_database_functions_are_service_role_only_and_audited(self):
        sql = (ROOT / "supabase/migrations/014_v2_admin_enterprise_management.sql").read_text("utf-8")
        self.assertIn("enterprise.subscription_updated", sql)
        self.assertIn("enterprise.device_status_changed", sql)
        self.assertIn("from public, anon, authenticated", sql)
        self.assertIn("to service_role", sql)
        self.assertIn("billing_status = 'pending_removal' then 'pending_removal'", sql)
        self.assertIn("p_current_period_end <= now()", sql)
        self.assertNotIn("token_hash =", sql)

    def test_inactive_subscription_error_has_clear_message(self):
        message = friendly_auth_error(SupabaseAuthError("SUBSCRIPTION_NOT_ACTIVE", status=409))
        self.assertIn("Ative ou renove", message)


if __name__ == "__main__":
    unittest.main()
