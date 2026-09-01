import { jsonResponse, readJson, cleanText } from "../_shared/http.ts";
import { randomToken, requireAdmin, sha256 } from "../_shared/security.ts";

const MUTATIONS = new Set([
  "create_company", "create_installation", "create_key", "revoke_key",
  "update_license", "set_installation_status", "update_system_config",
  "delete_installation",
]);

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return jsonResponse({ ok: true });
  if (req.method !== "POST") return jsonResponse({ error: "METHOD_NOT_ALLOWED" }, 405);
  try {
    const body = await readJson(req);
    const action = cleanText(body.action, 80);
    const { client, user, admin } = await requireAdmin(req, MUTATIONS.has(action));

    if (action === "list_installations") {
      const { data, error } = await client.from("installations")
        .select("id, hardware_id, status, app_version, online, last_seen_at, created_at, companies(name, manager_name, phone), licenses(status, license_type, expires_at, extra_messages, monthly_price, report_links, adjustment_notice, detailed_diagnostics_until)")
        .order("created_at", { ascending: false }).limit(500);
      if (error) throw error;
      return jsonResponse({ ok: true, installations: data });
    }

    if (action === "list_keys") {
      const { data, error } = await client.from("license_keys")
        .select("id, code_prefix, key_type, days_to_add, messages_to_add, fixed_expiry, status, intended_company, usable_until, redeemed_at, created_at")
        .order("created_at", { ascending: false }).limit(500);
      if (error) throw error;
      return jsonResponse({ ok: true, keys: data });
    }

    if (action === "get_system_config") {
      const { data, error } = await client.from("system_config").select("*")
        .eq("singleton", true).single();
      if (error) throw error;
      return jsonResponse({ ok: true, system: data });
    }

    if (action === "list_suggestions") {
      const { data, error } = await client.from("suggestions")
        .select("id, suggestion_text, status, admin_notes, created_at, installations(hardware_id, companies(name))")
        .order("created_at", { ascending: false }).limit(300);
      if (error) throw error;
      return jsonResponse({ ok: true, suggestions: data });
    }

    if (action === "list_telemetry") {
      const hardwareId = cleanText(body.hardware_id, 128);
      let query = client.from("telemetry_events")
        .select("id, occurred_at, level, component, event_name, diagnostic_mode, environment, details, installations(hardware_id, companies(name))")
        .order("occurred_at", { ascending: false }).limit(500);
      if (hardwareId) {
        const { data: selected } = await client.from("installations")
          .select("id").eq("hardware_id", hardwareId).maybeSingle();
        if (!selected) return jsonResponse({ ok: true, events: [] });
        query = query.eq("installation_id", selected.id);
      }
      const { data, error } = await query;
      if (error) throw error;
      return jsonResponse({ ok: true, events: data });
    }

    if (action === "update_license") {
      const hardwareId = cleanText(body.hardware_id, 128);
      const { data: installation, error: findError } = await client.from("installations")
        .select("id").eq("hardware_id", hardwareId).maybeSingle();
      if (findError) throw findError;
      if (!installation) return jsonResponse({ error: "INSTALLATION_NOT_FOUND" }, 404);
      const changes: Record<string, unknown> = {};
      if (body.expires_at != null) {
        const expiresAt = cleanText(body.expires_at, 64);
        if (Number.isNaN(Date.parse(expiresAt))) return jsonResponse({ error: "INVALID_EXPIRY" }, 400);
        changes.expires_at = expiresAt;
      }
      if (body.status != null) {
        const status = cleanText(body.status, 20);
        if (!["trial", "active", "expired", "blocked", "cancelled"].includes(status)) {
          return jsonResponse({ error: "INVALID_LICENSE_STATUS" }, 400);
        }
        changes.status = status;
      }
      if (body.license_type != null) {
        const licenseType = cleanText(body.license_type, 30);
        if (!["trial", "subscription", "courtesy"].includes(licenseType)) {
          return jsonResponse({ error: "INVALID_LICENSE_TYPE" }, 400);
        }
        changes.license_type = licenseType;
      }
      if (body.extra_messages != null) {
        const extra = Number(body.extra_messages);
        if (!Number.isInteger(extra) || extra < 0 || extra > 1000000) {
          return jsonResponse({ error: "INVALID_MESSAGES" }, 400);
        }
        changes.extra_messages = extra;
      }
      if (body.monthly_price !== undefined) {
        if (body.monthly_price === null || body.monthly_price === "") changes.monthly_price = null;
        else {
          const price = Number(body.monthly_price);
          if (!Number.isFinite(price) || price < 0) return jsonResponse({ error: "INVALID_PRICE" }, 400);
          changes.monthly_price = price;
        }
      }
      if (body.report_links != null) {
        changes.report_links = typeof body.report_links === "object" ? body.report_links : {};
      }
      if (body.adjustment_notice !== undefined) {
        changes.adjustment_notice = cleanText(body.adjustment_notice, 2000) || null;
      }
      if (body.detailed_diagnostics_until !== undefined) {
        const diagnosticUntil = cleanText(body.detailed_diagnostics_until, 64);
        if (diagnosticUntil && Number.isNaN(Date.parse(diagnosticUntil))) {
          return jsonResponse({ error: "INVALID_DIAGNOSTIC_EXPIRY" }, 400);
        }
        changes.detailed_diagnostics_until = diagnosticUntil || null;
      }
      if (!Object.keys(changes).length) return jsonResponse({ error: "EMPTY_UPDATE" }, 400);
      changes.updated_at = new Date().toISOString();
      const { data, error } = await client.from("licenses").update(changes)
        .eq("installation_id", installation.id)
        .select("status, license_type, expires_at, extra_messages, monthly_price, report_links, adjustment_notice, detailed_diagnostics_until")
        .single();
      if (error) throw error;
      await audit(client, user.id, "license.updated", "installation", installation.id, {
        fields: Object.keys(changes).filter((field) => field !== "updated_at"),
      });
      return jsonResponse({ ok: true, license: data });
    }

    if (action === "set_installation_status") {
      const hardwareId = cleanText(body.hardware_id, 128);
      const status = cleanText(body.status, 20);
      if (!["pending", "active", "blocked", "revoked"].includes(status)) {
        return jsonResponse({ error: "INVALID_INSTALLATION_STATUS" }, 400);
      }
      const { data, error } = await client.from("installations").update({
        status, token_revoked_at: status === "revoked" ? new Date().toISOString() : null,
      }).eq("hardware_id", hardwareId).select("id, hardware_id, status").single();
      if (error) throw error;
      await audit(client, user.id, "installation.status_changed", "installation", data.id, { status });
      return jsonResponse({ ok: true, installation: data });
    }

    if (action === "delete_installation") {
      if (admin.role !== "owner") {
        return jsonResponse({ error: "OWNER_REQUIRED" }, 403);
      }
      const hardwareId = cleanText(body.hardware_id, 128);
      const confirmation = cleanText(body.confirmation, 128);
      if (!hardwareId || confirmation !== hardwareId) {
        return jsonResponse({ error: "CONFIRMATION_REQUIRED" }, 400);
      }
      const { data: installation, error: findError } = await client.from("installations")
        .select("id, hardware_id").eq("hardware_id", hardwareId).maybeSingle();
      if (findError) throw findError;
      if (!installation) return jsonResponse({ error: "INSTALLATION_NOT_FOUND" }, 404);
      await audit(client, user.id, "installation.deleted", "installation", installation.id, {
        hardware_id_hash: await sha256(hardwareId),
      });
      const { error } = await client.from("installations").delete().eq("id", installation.id);
      if (error) throw error;
      return jsonResponse({ ok: true });
    }

    if (action === "update_system_config") {
      const changes: Record<string, unknown> = { updated_by: user.id, updated_at: new Date().toISOString() };
      if (body.current_version != null) changes.current_version = cleanText(body.current_version, 40);
      if (body.minimum_version != null) changes.minimum_version = cleanText(body.minimum_version, 40);
      if (body.update_required != null) changes.update_required = Boolean(body.update_required);
      if (body.installer_url !== undefined) changes.installer_url = cleanText(body.installer_url, 2000) || null;
      if (body.installer_sha256 !== undefined) {
        const checksum = cleanText(body.installer_sha256, 64).toLowerCase();
        if (checksum && !/^[a-f0-9]{64}$/.test(checksum)) {
          return jsonResponse({ error: "INVALID_INSTALLER_SHA256" }, 400);
        }
        changes.installer_sha256 = checksum || null;
      }
      if (body.default_monthly_price != null) {
        const price = Number(body.default_monthly_price);
        if (!Number.isFinite(price) || price < 0) return jsonResponse({ error: "INVALID_PRICE" }, 400);
        changes.default_monthly_price = price;
      }
      if (body.global_notice !== undefined) changes.global_notice = cleanText(body.global_notice, 2000) || null;
      if (body.maintenance_mode != null) changes.maintenance_mode = Boolean(body.maintenance_mode);
      if (body.maintenance_message !== undefined) changes.maintenance_message = cleanText(body.maintenance_message, 2000) || null;
      const { data, error } = await client.from("system_config").update(changes)
        .eq("singleton", true).select("*").single();
      if (error) throw error;
      await audit(client, user.id, "system_config.updated", "system", "singleton", {
        fields: Object.keys(changes).filter((field) => !["updated_by", "updated_at"].includes(field)),
      });
      return jsonResponse({ ok: true, system: data });
    }

    if (action === "revoke_key") {
      const keyId = cleanText(body.key_id, 64);
      if (!keyId) return jsonResponse({ error: "INVALID_KEY_ID" }, 400);
      const { data: current, error: lookupError } = await client.from("license_keys")
        .select("id, status, redeemed_at").eq("id", keyId).maybeSingle();
      if (lookupError) throw lookupError;
      if (!current) return jsonResponse({ error: "KEY_NOT_FOUND" }, 404);
      if (current.status === "used" || current.redeemed_at) {
        return jsonResponse({ error: "KEY_ALREADY_USED" }, 409);
      }
      if (current.status === "revoked") {
        return jsonResponse({ error: "KEY_ALREADY_REVOKED" }, 409);
      }
      if (current.status === "expired") {
        return jsonResponse({ error: "KEY_EXPIRED" }, 409);
      }
      if (current.status !== "new") {
        return jsonResponse({ error: "KEY_NOT_REVOCABLE" }, 409);
      }
      const { data, error } = await client.from("license_keys").update({ status: "revoked" })
        .eq("id", keyId).select("id, status").single();
      if (error) throw error;
      await audit(client, user.id, "license_key.revoked", "license_key", data.id, {});
      return jsonResponse({ ok: true, key: data });
    }

    if (action === "create_company") {
      const name = cleanText(body.name, 160);
      if (name.length < 2) return jsonResponse({ error: "INVALID_COMPANY" }, 400);
      const { data, error } = await client.from("companies").insert({
        name, manager_name: cleanText(body.manager_name, 160) || null,
        phone: cleanText(body.phone, 40) || null,
      }).select("id, name").single();
      if (error) throw error;
      await audit(client, user.id, "company.created", "company", data.id, { name });
      return jsonResponse({ ok: true, company: data }, 201);
    }

    if (action === "create_installation") {
      const hardwareId = cleanText(body.hardware_id, 128);
      const companyId = cleanText(body.company_id, 64);
      const expiresAt = cleanText(body.expires_at, 64);
      if (hardwareId.length < 8 || !companyId || !expiresAt) {
        return jsonResponse({ error: "INVALID_INSTALLATION" }, 400);
      }
      const token = randomToken();
      const tokenHash = await sha256(token);
      const { data: installation, error: installationError } = await client
        .from("installations").insert({
          company_id: companyId, hardware_id: hardwareId, token_hash: tokenHash,
          token_issued_at: new Date().toISOString(), status: "active",
        }).select("id, hardware_id, status").single();
      if (installationError) throw installationError;
      const { error: licenseError } = await client.from("licenses").insert({
        installation_id: installation.id, status: "active",
        license_type: "subscription", expires_at: expiresAt,
      });
      if (licenseError) throw licenseError;
      await audit(client, user.id, "installation.created", "installation", installation.id, {});
      return jsonResponse({ ok: true, installation, installation_token: token }, 201);
    }

    if (action === "create_key") {
      const keyType = cleanText(body.key_type, 30);
      if (!["days", "messages", "fixed_expiry"].includes(keyType)) {
        return jsonResponse({ error: "INVALID_KEY_TYPE" }, 400);
      }
      const prefix = keyType === "messages" ? "MSG" : keyType === "fixed_expiry" ? "VCT" : "PRO";
      const code = `${prefix}-${randomToken(12).toUpperCase()}`;
      const row: Record<string, unknown> = {
        code_hash: await sha256(code), code_prefix: `${prefix}-${code.slice(-6)}`,
        key_type: keyType, status: "new", created_by: user.id,
        intended_company: cleanText(body.intended_company, 160) || null,
        usable_until: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(),
      };
      if (keyType === "days") {
        const days = Number(body.days_to_add);
        if (!Number.isInteger(days) || days < 1 || days > 3650) {
          return jsonResponse({ error: "INVALID_DAYS" }, 400);
        }
        row.days_to_add = days;
      }
      if (keyType === "messages") {
        const messages = Number(body.messages_to_add);
        if (!Number.isInteger(messages) || messages < 1 || messages > 100000) {
          return jsonResponse({ error: "INVALID_MESSAGES" }, 400);
        }
        row.messages_to_add = messages;
      }
      if (keyType === "fixed_expiry") {
        const fixedExpiry = cleanText(body.fixed_expiry, 64);
        if (!fixedExpiry || Number.isNaN(Date.parse(fixedExpiry))) {
          return jsonResponse({ error: "INVALID_EXPIRY" }, 400);
        }
        row.fixed_expiry = fixedExpiry;
      }
      const { data, error } = await client.from("license_keys").insert(row)
        .select("id, code_prefix, key_type, usable_until").single();
      if (error) throw error;
      await audit(client, user.id, "license_key.created", "license_key", data.id, { key_type: keyType });
      return jsonResponse({ ok: true, key: data, code }, 201);
    }

    return jsonResponse({ error: "UNKNOWN_ACTION" }, 400);
  } catch (error) {
    const code = error instanceof Error ? error.message : "INTERNAL_ERROR";
    const status = code === "UNAUTHORIZED" ? 401 : code === "FORBIDDEN" ? 403 : code === "MFA_REQUIRED" ? 428 : 500;
    return jsonResponse({ error: status === 500 ? "INTERNAL_ERROR" : code }, status);
  }
});

async function audit(client: any, userId: string, action: string, type: string, id: string, metadata: unknown) {
  await client.from("audit_events").insert({
    actor_user_id: userId, action, target_type: type, target_id: id, metadata,
  });
}
