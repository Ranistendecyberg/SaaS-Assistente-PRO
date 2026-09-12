import { cleanText, jsonResponse, readJson } from "../_shared/http.ts";
import { requireUser, sha256 } from "../_shared/security.ts";
import { normalizeCnpj, requireCompanyMember, validDocument, hasRecentEmailConfirmation } from "../_shared/v2.ts";

const MUTATIONS = new Set([
  "create_business_unit",
  "issue_device_link_code",
  "schedule_device_removal",
  "cancel_device_removal",
  "transfer_principal",
]);

function activationCode(): string {
  const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  const random = crypto.getRandomValues(new Uint8Array(8));
  const value = [...random].map((byte) => alphabet[byte & 31]).join("");
  return `PC-${value.slice(0, 4)}-${value.slice(4)}`;
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return jsonResponse({ ok: true });
  if (req.method !== "POST") return jsonResponse({ error: "METHOD_NOT_ALLOWED" }, 405);
  try {
    const body = await readJson(req);
    const action = cleanText(body.action, 80);
    const companyId = cleanText(body.company_id, 64);
    const { client, user, payload } = await requireUser(req);

    if (action === "recover_principal_access") {
      if (!user.email_confirmed_at || !hasRecentEmailConfirmation(payload, 600)) {
        return jsonResponse({ error: "EMAIL_OTP_REQUIRED" }, 428);
      }
      const hardwareId = cleanText(body.hardware_id, 129);
      if (hardwareId.length < 8 || hardwareId.length > 128) {
        return jsonResponse({ error: "RECOVERY_NOT_ALLOWED" }, 403);
      }
      const { data, error } = await client.rpc("recover_principal_access_server", {
        p_user_id: user.id, p_hardware_id: hardwareId,
      });
      if (error) throw error;
      if (!data?.ok) return jsonResponse({ error: data?.error || "RECOVERY_NOT_ALLOWED" },
        data?.error === "RECOVERY_RATE_LIMITED" ? 429 : 403);
      return jsonResponse(data);
    }

    if (action === "list_companies") {
      const { data, error } = await client.from("company_members")
        .select("company_id, role, active, companies(id, name, manager_name, phone, active)")
        .eq("user_id", user.id).eq("active", true).order("created_at");
      if (error) throw error;
      return jsonResponse({ ok: true, memberships: data || [] });
    }

    if (action === "create_company_trial") {
      const companyName = cleanText(body.company_name, 160);
      const ownerName = cleanText(body.owner_name, 160);
      const phone = cleanText(body.phone, 40).replace(/\D/g, "");
      const cnpj = normalizeCnpj(body.cnpj);
      const hardwareId = cleanText(body.hardware_id, 128);
      const appVersion = cleanText(body.app_version, 40);
      if (!user.email_confirmed_at) {
        return jsonResponse({ error: "EMAIL_CONFIRMATION_REQUIRED" }, 403);
      }
      if (companyName.length < 2 || ownerName.length < 2 || phone.length < 10 ||
          phone.length > 15 || !validDocument(cnpj) || hardwareId.length < 8) {
        return jsonResponse({ error: "INVALID_ONBOARDING" }, 400);
      }
      const oneHourAgo = new Date(Date.now() - 60 * 60 * 1000).toISOString();
      const { count: recentAttempts, error: rateError } = await client
        .from("onboarding_attempts")
        .select("id", { count: "exact", head: true })
        .eq("user_id", user.id)
        .gte("attempted_at", oneHourAgo);
      if (rateError) throw rateError;
      if ((recentAttempts || 0) >= 5) {
        return jsonResponse({ error: "ONBOARDING_RATE_LIMITED" }, 429);
      }
      const { data: attempt, error: attemptError } = await client
        .from("onboarding_attempts")
        .insert({ user_id: user.id, hardware_hash: await sha256(hardwareId) })
        .select("id").single();
      if (attemptError) throw attemptError;
      const { data, error } = await client.rpc("create_company_trial_server", {
        p_user_id: user.id,
        p_company_name: companyName,
        p_owner_name: ownerName,
        p_phone: phone,
        p_cnpj: cnpj,
        p_hardware_id: hardwareId,
        p_app_version: appVersion || null,
      });
      if (error) throw error;
      if (data?.ok) {
        await client.from("onboarding_attempts").update({ succeeded: true })
          .eq("id", attempt.id);
      }
      if (!data?.ok) {
        const conflict = [
          "USER_ALREADY_HAS_COMPANY", "CNPJ_ALREADY_REGISTERED",
          "INSTALLATION_ALREADY_EXISTS", "ONBOARDING_ALREADY_USED",
        ].includes(data?.error);
        return jsonResponse(data, conflict ? 409 : 400);
      }
      return jsonResponse(data, 201);
    }

    const member = await requireCompanyMember(client, user.id, companyId, {
      mutation: MUTATIONS.has(action),
      ownerOnly: action === "transfer_principal",
      requireRecentEmail: action !== "issue_device_link_code",
      payload,
    });

    if (action === "account_summary") {
      const [company, units, installations, subscription, invoices] = await Promise.all([
        client.from("companies").select("id, name, manager_name, phone, active").eq("id", companyId).single(),
        client.from("business_units").select("id, unit_type, display_name, cnpj, active").eq("company_id", companyId).order("created_at"),
        client.from("installations").select("id, business_unit_id, hardware_id, device_class, billing_status, status, app_version, online, last_seen_at, removal_scheduled_for").eq("company_id", companyId).order("created_at"),
        client.from("company_subscriptions").select("status, pricing_origin, base_price, additional_seat_price, trial_expires_at, current_period_start, current_period_end").eq("company_id", companyId).maybeSingle(),
        client.from("billing_invoices").select("id, period_start, period_end, due_at, principal_seats, additional_seats, total_amount, status, paid_at").eq("company_id", companyId).order("created_at", { ascending: false }).limit(24),
      ]);
      for (const result of [company, units, installations, subscription, invoices]) {
        if (result.error) throw result.error;
      }
      return jsonResponse({
        ok: true, role: member.role, company: company.data,
        units: units.data || [], installations: installations.data || [],
        subscription: subscription.data, invoices: invoices.data || [],
      });
    }

    if (action === "create_business_unit") {
      const displayName = cleanText(body.display_name, 160);
      const cnpj = normalizeCnpj(body.cnpj);
      const unitType = cleanText(body.unit_type, 20) || "branch";
      if (displayName.length < 2 || !validDocument(cnpj)) {
        return jsonResponse({ error: "INVALID_BUSINESS_UNIT" }, 400);
      }
      if (!["headquarters", "branch"].includes(unitType)) {
        return jsonResponse({ error: "INVALID_UNIT_TYPE" }, 400);
      }
      const { data, error } = await client.from("business_units").insert({
        company_id: companyId, display_name: displayName, cnpj, unit_type: unitType,
      }).select("id, unit_type, display_name, cnpj, active").single();
      if (error) throw error;
      await audit(client, user.id, "business_unit.created", "business_unit", data.id, { company_id: companyId });
      return jsonResponse({ ok: true, unit: data }, 201);
    }

    if (action === "issue_device_link_code") {
      const businessUnitId = cleanText(body.business_unit_id, 64);
      const { data: subscription, error: subscriptionError } = await client
        .from("company_subscriptions")
        .select("status, trial_expires_at, current_period_end")
        .eq("company_id", companyId).maybeSingle();
      if (subscriptionError) throw subscriptionError;
      const subscriptionExpiry = subscription?.current_period_end || subscription?.trial_expires_at;
      if (!subscription || !["trial", "active"].includes(subscription.status) ||
          !subscriptionExpiry || Date.parse(subscriptionExpiry) <= Date.now()) {
        return jsonResponse({ error: "SUBSCRIPTION_NOT_ACTIVE" }, 409);
      }
      if (businessUnitId) {
        const { data: unit, error } = await client.from("business_units")
          .select("id").eq("id", businessUnitId).eq("company_id", companyId).eq("active", true).maybeSingle();
        if (error) throw error;
        if (!unit) return jsonResponse({ error: "BUSINESS_UNIT_NOT_FOUND" }, 404);
      }
      const tenMinutesAgo = new Date(Date.now() - 10 * 60 * 1000).toISOString();
      const { count: recentCodes, error: rateError } = await client
        .from("device_link_codes")
        .select("id", { count: "exact", head: true })
        .eq("created_by", user.id)
        .gte("created_at", tenMinutesAgo);
      if (rateError) throw rateError;
      if ((recentCodes || 0) >= 5) {
        return jsonResponse({ error: "LINK_CODE_RATE_LIMITED" }, 429);
      }
      const code = activationCode();
      const expiresAt = new Date(Date.now() + 15 * 60 * 1000).toISOString();
      const { data, error } = await client.from("device_link_codes").insert({
        company_id: companyId,
        business_unit_id: businessUnitId || null,
        code_hash: await sha256(code),
        code_prefix: code.slice(0, 7),
        expires_at: expiresAt,
        created_by: user.id,
      }).select("id, code_prefix, status, expires_at").single();
      if (error) throw error;
      await audit(client, user.id, "device_link_code.created", "device_link_code", data.id, { company_id: companyId });
      return jsonResponse({ ok: true, link_code: code, code: data }, 201);
    }

    if (action === "schedule_device_removal") {
      const installationId = cleanText(body.installation_id, 64);
      const { data: installation, error: lookupError } = await client.from("installations")
        .select("id, device_class, billing_status").eq("id", installationId)
        .eq("company_id", companyId).maybeSingle();
      if (lookupError) throw lookupError;
      if (!installation) return jsonResponse({ error: "INSTALLATION_NOT_FOUND" }, 404);
      if (installation.device_class === "principal") {
        return jsonResponse({ error: "PRINCIPAL_TRANSFER_REQUIRED" }, 409);
      }
      if (installation.billing_status === "removed") {
        return jsonResponse({ error: "INSTALLATION_ALREADY_REMOVED" }, 409);
      }
      const { data: subscription, error: subscriptionError } = await client.from("company_subscriptions")
        .select("current_period_end, trial_expires_at").eq("company_id", companyId).maybeSingle();
      if (subscriptionError) throw subscriptionError;
      const candidate = subscription?.current_period_end || subscription?.trial_expires_at;
      const effectiveAt = candidate && Date.parse(candidate) > Date.now()
        ? candidate : new Date().toISOString();
      const { data, error } = await client.from("installations").update({
        billing_status: "pending_removal", removal_scheduled_for: effectiveAt,
      }).eq("id", installationId).eq("company_id", companyId)
        .select("id, billing_status, removal_scheduled_for").single();
      if (error) throw error;
      await audit(client, user.id, "installation.removal_scheduled", "installation", installationId, { effective_at: effectiveAt });
      return jsonResponse({ ok: true, installation: data });
    }

    if (action === "cancel_device_removal") {
      const installationId = cleanText(body.installation_id, 64);
      const { data, error } = await client.from("installations").update({
        billing_status: "active", removal_scheduled_for: null,
      }).eq("id", installationId).eq("company_id", companyId)
        .eq("billing_status", "pending_removal")
        .select("id, billing_status, removal_scheduled_for").maybeSingle();
      if (error) throw error;
      if (!data) return jsonResponse({ error: "REMOVAL_NOT_PENDING" }, 409);
      await audit(client, user.id, "installation.removal_cancelled", "installation", installationId, {});
      return jsonResponse({ ok: true, installation: data });
    }

    
    if (action === "transfer_principal") {
      const newPrincipalId = cleanText(body.installation_id, 64);
      const { data, error } = await client.rpc("transfer_principal_server", {
        p_company_id: companyId,
        p_new_principal_installation_id: newPrincipalId,
      });
      if (error) throw error;
      return jsonResponse(data, data?.ok ? 200 : 400);
    }

    return jsonResponse({ error: "UNKNOWN_ACTION" }, 400);
  } catch (error) {
    const code = error instanceof Error ? error.message : "INTERNAL_ERROR";
    const status = code === "UNAUTHORIZED" ? 401
      : ["FORBIDDEN", "OWNER_REQUIRED"].includes(code) ? 403
      : code === "EMAIL_OTP_REQUIRED" ? 428
      : code === "COMPANY_REQUIRED" ? 400
      : 500;
    return jsonResponse({ error: status === 500 ? "INTERNAL_ERROR" : code }, status);
  }
});

async function audit(client: any, userId: string, action: string, type: string, id: string, metadata: unknown) {
  await client.from("audit_events").insert({
    actor_user_id: userId, action, target_type: type, target_id: id, metadata,
  });
}
