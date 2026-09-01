from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class V2EdgeContractsTests(unittest.TestCase):
    def test_device_link_redemption_is_atomic_and_never_persists_plain_token(self):
        sql = (ROOT / "supabase/migrations/010_v2_device_link_redemption.sql").read_text("utf-8")
        self.assertIn("for update", sql.lower())
        self.assertIn("digest(v_token, 'sha256')", sql)
        self.assertNotIn("installation_token text", sql.lower())
        self.assertIn("COMPANY_MEMBERSHIP_REQUIRED", sql)

    def test_account_api_requires_mfa_for_mutations(self):
        source = (ROOT / "supabase/functions/account-api/index.ts").read_text("utf-8")
        self.assertIn("requireCompanyMember", source)
        self.assertIn("aal: payload.aal", source)
        self.assertIn("24 * 60 * 60 * 1000", source)
        self.assertIn("PRINCIPAL_TRANSFER_REQUIRED", source)

    def test_desktop_redeems_link_through_server_rpc(self):
        source = (ROOT / "supabase/functions/desktop-api/index.ts").read_text("utf-8")
        self.assertIn('action === "redeem_device_link_code"', source)
        self.assertIn('rpc("redeem_device_link_code_server"', source)
        self.assertIn("requireUser(req)", source)

    def test_trial_onboarding_is_atomic_and_requires_confirmed_email(self):
        sql = (ROOT / "supabase/migrations/011_v2_company_trial_onboarding.sql").read_text("utf-8")
        api = (ROOT / "supabase/functions/account-api/index.ts").read_text("utf-8")
        self.assertIn("email_confirmed_at is not null", sql.lower())
        self.assertIn("now() + interval '2 days'", sql.lower())
        self.assertIn("'principal', 'active'", sql)
        self.assertIn("digest(v_installation_token, 'sha256')", sql)
        self.assertIn("onboarding_attempts", sql)
        self.assertIn('action === "create_company_trial"', api)
        self.assertIn("validCnpj(cnpj)", api)
        self.assertIn("ONBOARDING_RATE_LIMITED", api)
        self.assertIn("sha256(hardwareId)", api)

    def test_v2_runtime_has_no_firebase_migration_endpoints(self):
        desktop = (ROOT / "supabase/functions/desktop-api/index.ts").read_text("utf-8")
        admin = (ROOT / "supabase/functions/admin-api/index.ts").read_text("utf-8")
        client = (ROOT / "src/core/supabase_desktop.py").read_text("utf-8")
        for removed in (
            "bootstrap_mode", "claim_legacy_installation",
            "register_new_installation", "import_legacy_snapshot",
            "issue_migration_claim",
        ):
            with self.subTest(removed=removed):
                self.assertNotIn(removed, desktop + admin + client)


if __name__ == "__main__":
    unittest.main()
