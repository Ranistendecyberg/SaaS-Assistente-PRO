from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class V2EdgeContractsTests(unittest.TestCase):
    def test_legacy_hardware_recovery_preserves_seat_and_requires_owner(self):
        sql = (ROOT / "supabase/migrations/030_v2_legacy_hardware_recovery.sql").read_text("utf-8")
        self.assertIn("m.role = 'owner'", sql)
        self.assertIn("v_candidate_count <> 1", sql)
        self.assertIn("i.hardware_id ~ '^[0-9]{12,20}$'", sql)
        self.assertIn("hardware_rebound", sql)
        self.assertNotIn("insert into public.licenses", sql.lower())
        self.assertNotIn("update public.licenses", sql.lower())
        self.assertIn("to service_role", sql)

    def test_device_link_redemption_is_atomic_and_never_persists_plain_token(self):
        sql = (ROOT / "supabase/migrations/010_v2_device_link_redemption.sql").read_text("utf-8")
        self.assertIn("for update", sql.lower())
        self.assertIn("digest(v_token, 'sha256')", sql)
        self.assertNotIn("installation_token text", sql.lower())
        self.assertIn("COMPANY_MEMBERSHIP_REQUIRED", sql)

    def test_additional_device_inherits_company_term_and_principal_report_links(self):
        sql = (ROOT / "supabase/migrations/013_v2_additional_device_license.sql").read_text("utf-8")
        self.assertIn("SUBSCRIPTION_NOT_ACTIVE", sql)
        self.assertIn("SUBSCRIPTION_EXPIRED", sql)
        self.assertIn("v_subscription.additional_seat_price", sql)
        self.assertIn("insert into public.licenses", sql.lower())
        self.assertIn("l.report_links", sql)
        self.assertIn("i.device_class = 'principal'", sql)

    def test_customer_mutations_require_recent_email_otp_except_device_activation(self):
        source = (ROOT / "supabase/functions/account-api/index.ts").read_text("utf-8")
        shared = (ROOT / "supabase/functions/_shared/v2.ts").read_text("utf-8")
        self.assertIn("requireCompanyMember", source)
        self.assertIn('requireRecentEmail: action !== "issue_device_link_code"', source)
        self.assertIn('method === "otp"', shared)
        self.assertIn("12 * 60 * 60", shared)
        self.assertIn("EMAIL_OTP_REQUIRED", source + shared)
        self.assertNotIn("MFA_REQUIRED", source + shared)
        self.assertIn("15 * 60 * 1000", source)
        self.assertIn("PRINCIPAL_TRANSFER_REQUIRED", source)
        self.assertIn("SUBSCRIPTION_NOT_ACTIVE", source)

    def test_billing_profile_uses_email_otp_but_payment_generation_does_not(self):
        source = (ROOT / "supabase/functions/billing-api/index.ts").read_text("utf-8")
        self.assertIn('const mutation = action === "save_billing_profile"', source)
        self.assertIn('"save_billing_profile", "create_payment", "refresh_payment_status",', source)
        self.assertIn('"cancel_test_payment",', source)
        self.assertIn("mutation, ownerOnly, payload", source)
        self.assertIn("EMAIL_OTP_REQUIRED", source)

    def test_desktop_redeems_link_through_server_rpc(self):
        source = (ROOT / "supabase/functions/desktop-api/index.ts").read_text("utf-8")
        self.assertIn('action === "redeem_device_link_code"', source)
        self.assertIn('rpc("redeem_device_link_code_server"', source)
        self.assertIn("serviceClient()", source)
        redeem_branch = source.split('action === "redeem_device_link_code"', 1)[1].split(
            "const { client, installation }", 1
        )[0]
        self.assertNotIn("requireUser(req)", redeem_branch)

    def test_simple_activation_is_one_time_hashed_and_rate_limited(self):
        sql = (ROOT / "supabase/migrations/018_v2_simple_device_activation.sql").read_text("utf-8")
        self.assertIn("device_link_attempts", sql)
        self.assertIn("interval '15 minutes'", sql)
        self.assertIn(") >= 5", sql)
        self.assertIn("for update", sql.lower())
        self.assertIn("v_code.status <> 'new'", sql)
        self.assertIn("digest(v_token, 'sha256')", sql)
        self.assertNotIn("p_user_id", sql)
        self.assertIn("v_code.created_by", sql)

    def test_messaging_limits_are_per_installation_and_server_enforced(self):
        sql = (ROOT / "supabase/migrations/016_v2_messaging_limits.sql").read_text("utf-8")
        desktop = (ROOT / "supabase/functions/desktop-api/index.ts").read_text("utf-8")
        admin = (ROOT / "supabase/functions/admin-api/index.ts").read_text("utf-8")
        self.assertIn("daily_message_limit", sql)
        self.assertIn("batch_limit", sql)
        self.assertIn("between 1 and 1000", sql.lower())
        self.assertIn("license.daily_message_limit ??", desktop)
        self.assertIn('rpc("consume_message_server"', desktop)
        self.assertIn('["daily_message_limit", "batch_limit"]', admin)
        self.assertIn("INVALID_MESSAGE_LIMIT", admin)

    def test_message_quota_uses_atomic_reservations(self):
        sql = (ROOT / "supabase/migrations/017_v2_message_send_reservations.sql").read_text("utf-8")
        desktop = (ROOT / "supabase/functions/desktop-api/index.ts").read_text("utf-8")
        client = (ROOT / "src/core/supabase_desktop.py").read_text("utf-8")
        extraction = (ROOT / "src/ui/screens/extraction_screen.py").read_text("utf-8")

        self.assertIn("message_send_reservations", sql)
        self.assertIn("for update", sql.lower())
        self.assertIn("reserve_message_send_server", sql)
        self.assertIn("confirm_message_send_server", sql)
        self.assertIn("release_message_send_server", sql)
        self.assertIn('"reserve_message"', desktop)
        self.assertIn('"confirm_message"', desktop)
        self.assertIn('"release_message"', desktop)
        self.assertIn('def reserve_message', client)
        self.assertIn('def confirm_message', client)
        self.assertIn('def release_message', client)
        self.assertIn('lm.reservar_envio()', extraction)
        self.assertIn('reservation_manager.confirmar_envio(reservation_id)', extraction)
        self.assertIn('reservation_manager.liberar_reserva_envio(reservation_id)', extraction)

    def test_trial_onboarding_is_atomic_and_requires_confirmed_email(self):
        sql = (ROOT / "supabase/migrations/011_v2_company_trial_onboarding.sql").read_text("utf-8")
        api = (ROOT / "supabase/functions/account-api/index.ts").read_text("utf-8")
        self.assertIn("email_confirmed_at is not null", sql.lower())
        self.assertIn("now() + interval '2 days'", sql.lower())
        self.assertIn("'principal', 'active'", sql)
        self.assertIn("digest(v_installation_token, 'sha256')", sql)
        self.assertIn("onboarding_attempts", sql)
        self.assertIn('action === "create_company_trial"', api)
        self.assertIn("validDocument(cnpj)", api)
        upgrade = (ROOT / "supabase/migrations/021_v2_cpf_cnpj_accounts.sql").read_text("utf-8")
        self.assertIn("not public.valid_tax_document(p_cnpj)", upgrade)
        self.assertIn("for update", upgrade)
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

    def test_enterprise_admin_updates_are_atomic_and_audited(self):
        sql = (ROOT / "supabase/migrations/014_v2_admin_enterprise_management.sql").read_text("utf-8")
        api = (ROOT / "supabase/functions/admin-api/index.ts").read_text("utf-8")
        self.assertIn("admin_update_company_subscription_server", sql)
        self.assertIn("admin_set_enterprise_device_status_server", sql)
        self.assertIn("enterprise.subscription_updated", sql)
        self.assertIn("enterprise.device_status_changed", sql)
        self.assertIn('"update_enterprise_subscription"', api)
        self.assertIn('"set_enterprise_device_status"', api)

    def test_consolidated_billing_uses_orders_webhook_and_server_rpcs(self):
        sql = (ROOT / "supabase/migrations/015_v2_consolidated_billing.sql").read_text("utf-8")
        api = (ROOT / "supabase/functions/billing-api/index.ts").read_text("utf-8")
        self.assertIn("prepare_company_invoice_server", sql)
        self.assertIn("prepare_billing_attempt_server", sql)
        self.assertIn("apply_mercado_pago_order_server", sql)
        self.assertIn("for update", sql.lower())
        self.assertIn("provider_order_id_hash", sql)
        self.assertIn("processed", sql)
        self.assertIn("accredited", sql)
        self.assertIn("MERCADO_PAGO_ACCESS_TOKEN", api)
        self.assertIn("MERCADO_PAGO_WEBHOOK_SECRET", api)
        self.assertIn("X-Idempotency-Key", api)
        self.assertIn("crypto.subtle.verify", api)
        self.assertIn('url.searchParams.get("data.id")', api)
        self.assertNotIn("saas-pix-api.onrender.com", api)

    def test_payment_test_environment_is_server_selected_and_expires(self):
        sql = (ROOT / "supabase/migrations/031_v2_payment_test_environment.sql").read_text("utf-8")
        api = (ROOT / "supabase/functions/billing-api/index.ts").read_text("utf-8")
        self.assertIn("billing_payment_test_companies", sql)
        self.assertIn("expires_at > clock_timestamp()", sql)
        self.assertIn("IMMUTABLE_PAYMENT_SNAPSHOT", sql)
        self.assertIn("provider_environment", sql)
        self.assertIn("provider_resource_type", sql)
        self.assertIn("MERCADO_PAGO_TEST_ACCESS_TOKEN", api)
        self.assertIn("MERCADO_PAGO_TEST_WEBHOOK_SECRET", api)
        self.assertIn("PAYMENT_ENVIRONMENT_MISMATCH", api)
        self.assertIn('first_name: "APRO"', api)
        self.assertIn('"test_user_br@testuser.com"', api)
        self.assertIn('identification: { type: "CPF", number: "99999999999" }', api)
        self.assertIn('street_name: "Av. das Nações Unidas"', api)
        self.assertIn('if (environment === "test")', api)
        self.assertIn('? {}\n          : { processing_mode: "automatic" }', api)
        desktop = (ROOT / "src/core/supabase_auth.py").read_text("utf-8")
        desktop += (ROOT / "src/core/supabase_desktop.py").read_text("utf-8")
        self.assertNotIn("MERCADO_PAGO_TEST_ACCESS_TOKEN", desktop)

    def test_billing_provider_failure_is_not_hidden_as_internal_error(self):
        api = (ROOT / "supabase/functions/billing-api/index.ts").read_text("utf-8")
        self.assertIn('code === "PAYMENT_PROVIDER_ERROR" ? 502', api)
        self.assertIn('status === 500 ? "INTERNAL_ERROR" : code', api)

    def test_orders_external_reference_respects_provider_contract(self):
        sql = (ROOT / "supabase/migrations/032_v2_orders_external_reference.sql").read_text("utf-8")
        self.assertIn("replace(p_invoice_id::text, '-', '')", sql)
        self.assertIn("encode(gen_random_bytes(12), 'hex')", sql)
        self.assertNotIn("'invoice:'", sql)

    def test_old_payment_cannot_activate_new_unpaid_computers(self):
        sql = (ROOT / "supabase/migrations/019_v2_invoice_seat_consistency.sql").read_text("utf-8")
        api = (ROOT / "supabase/functions/billing-api/index.ts").read_text("utf-8")
        self.assertIn("billing.invoice_repriced", sql)
        self.assertIn("invoice_seat_count_changed", sql)
        self.assertIn("SEAT_COUNT_MISMATCH", sql)
        self.assertIn("ATTEMPT_NOT_PAYABLE", sql)
        self.assertIn("p_provider_status = 'approved'", sql)
        self.assertIn("cancelSupersededAttempts", api)
        self.assertIn('body: JSON.stringify({ status: "cancelled" })', api)
        self.assertIn("PAYMENT_RECONCILIATION_REQUIRED", api)


if __name__ == "__main__":
    unittest.main()
