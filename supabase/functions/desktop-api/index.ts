import { jsonResponse, readJson, cleanText } from "../_shared/http.ts";
import {
  requireInstallation, serviceClient, sha256,
} from "../_shared/security.ts";

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return jsonResponse({ ok: true });
  if (req.method !== "POST") return jsonResponse({ error: "METHOD_NOT_ALLOWED" }, 405);
  try {
    const body = await readJson(req);
    const action = cleanText(body.action, 80);
    const hardwareId = cleanText(body.hardware_id, 128);

    if (action === "redeem_device_link_code") {
      const code = cleanText(body.link_code, 24).toUpperCase().replace(/\s/g, "");
      if (!/^PC-[A-HJ-NP-Z2-9]{4}-[A-HJ-NP-Z2-9]{4}$/.test(code)) {
        return jsonResponse({ error: "INVALID_LINK_CODE" }, 400);
      }
      const client = serviceClient();
      const { data, error } = await client.rpc("redeem_device_link_code_server", {
        p_code_hash: await sha256(code),
        p_hardware_id: hardwareId,
        p_app_version: cleanText(body.app_version, 40) || null,
      });
      if (error) throw error;
      if (data?.ok) {
        const {data: license,error: licenseError}=await client.from("licenses").select("status")
          .eq("installation_id",data.installation_id).single();
        if (licenseError) throw licenseError;
        data.payment_required=license.status === "blocked";
      }
      return jsonResponse(data, data?.ok ? 201 : 409);
    }

    const { client, installation } = await requireInstallation(req, hardwareId);

    if (["create_pix", "check_pix"].includes(action)) {
      return jsonResponse({error:"USE_COMPANY_BILLING"},410);
    }

    if (action === "heartbeat") {
      const { error } = await client.from("installations").update({
        online: Boolean(body.online),
        last_seen_at: new Date().toISOString(),
        app_version: cleanText(body.app_version, 40) || null,
      }).eq("id", installation.id);
      if (error) throw error;
      return jsonResponse({ ok: true });
    }

    if (action === "license_status") {
      const { data: license, error } = await client.from("licenses")
        .select("status, license_type, expires_at, offline_grace_hours, extra_messages, monthly_price, report_links, adjustment_notice, detailed_diagnostics_until, daily_message_limit, batch_limit")
        .eq("installation_id", installation.id).single();
      if (error) throw error;
      const { data: config } = await client.from("system_config")
        .select("current_version, minimum_version, update_required, installer_url, installer_sha256, global_notice, maintenance_mode, maintenance_message")
        .eq("singleton", true).single();
      const { data: company } = await client.from("companies")
        .select("name, manager_name, phone")
        .eq("id", installation.company_id).maybeSingle();
      const today = new Date().toISOString().slice(0, 10);
      const { data: dailyUsage } = await client.from("daily_usage")
        .select("sent_count")
        .eq("installation_id", installation.id)
        .eq("usage_date", today).maybeSingle();
      const dailyLimit = license.daily_message_limit ?? (license.license_type === "trial" ? 6 : 30);
      await client.from("installations").update({
        online: true, last_seen_at: new Date().toISOString(),
        app_version: cleanText(body.app_version, 40) || null,
      }).eq("id", installation.id);
      return jsonResponse({
        ok: true,
        license,
        company: company || {},
        usage: { messages_used: dailyUsage?.sent_count || 0, daily_limit: dailyLimit },
        system: config,
        server_time: new Date().toISOString(),
      });
    }

    if (action === "redeem_key") {
      const code = cleanText(body.code, 128).toUpperCase();
      if (code.length < 10) return jsonResponse({ error: "INVALID_KEY" }, 400);
      const { data, error } = await client.rpc("redeem_license_key_server", {
        p_installation_id: installation.id, p_code_hash: await sha256(code),
      });
      if (error) throw error;
      return jsonResponse(data);
    }

    if (action === "consume_message") {
      const { data: license, error: licenseError } = await client.from("licenses")
        .select("license_type, daily_message_limit").eq("installation_id", installation.id).single();
      if (licenseError) throw licenseError;
      const dailyLimit = license.daily_message_limit ?? (license.license_type === "trial" ? 6 : 30);
      const { data, error } = await client.rpc("consume_message_server", {
        p_installation_id: installation.id, p_daily_limit: dailyLimit,
      });
      if (error) throw error;
      return jsonResponse(data);
    }

    if (["reserve_message", "confirm_message", "release_message"].includes(action)) {
      const reservationId = cleanText(body.reservation_id, 36);
      if (!/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(reservationId)) {
        return jsonResponse({ error: "INVALID_RESERVATION_ID" }, 400);
      }
      if (action === "reserve_message") {
        const { data: license, error: licenseError } = await client.from("licenses")
          .select("license_type, daily_message_limit").eq("installation_id", installation.id).single();
        if (licenseError) throw licenseError;
        const dailyLimit = license.daily_message_limit ?? (license.license_type === "trial" ? 6 : 30);
        const { data, error } = await client.rpc("reserve_message_send_server", {
          p_installation_id: installation.id,
          p_daily_limit: dailyLimit,
          p_reservation_id: reservationId,
        });
        if (error) throw error;
        return jsonResponse(data);
      }
      const rpcName = action === "confirm_message"
        ? "confirm_message_send_server"
        : "release_message_send_server";
      const { data, error } = await client.rpc(rpcName, {
        p_installation_id: installation.id,
        p_reservation_id: reservationId,
      });
      if (error) throw error;
      return jsonResponse(data);
    }


    if (action === "telemetry") {
      const events = Array.isArray(body.events) ? body.events.slice(0, 100) : [];
      const now = Date.now();
      const rows = events.map((item: any) => ({
        installation_id: installation.id,
        occurred_at: cleanText(item.occurred_at, 64) || new Date().toISOString(),
        level: ["INFO", "WARN", "ERROR"].includes(item.level) ? item.level : "INFO",
        component: cleanText(item.component, 60) || "application",
        event_name: cleanText(item.event, 80) || "UNKNOWN",
        session_id: cleanText(item.session_id, 64) || null,
        app_version: cleanText(item.app_version, 40) || null,
        diagnostic_mode: Boolean(item.diagnostic_mode),
        environment: typeof item.environment === "object" ? item.environment : {},
        details: typeof item.details === "object" ? item.details : {},
        expires_at: new Date(now + (item.diagnostic_mode ? 30 : 7) * 86400000).toISOString(),
      }));
      if (rows.length) {
        const { error } = await client.from("telemetry_events").insert(rows);
        if (error) throw error;
      }
      return jsonResponse({ ok: true, accepted: rows.length });
    }

    if (action === "suggestion") {
      const suggestion = cleanText(body.suggestion, 4000);
      if (suggestion.length < 3) return jsonResponse({ error: "INVALID_SUGGESTION" }, 400);
      const { error } = await client.from("suggestions").insert({
        installation_id: installation.id, suggestion_text: suggestion,
      });
      if (error) throw error;
      return jsonResponse({ ok: true }, 201);
    }

    return jsonResponse({ error: "UNKNOWN_ACTION" }, 400);
  } catch (error) {
    const code = error instanceof Error ? error.message : "INTERNAL_ERROR";
    const status = code === "UNAUTHORIZED" ? 401
      : code === "INSTALLATION_ALREADY_EXISTS" ? 409
      : 500;
    return jsonResponse({ error: status === 500 ? "INTERNAL_ERROR" : code }, status);
  }
});
