import { jsonResponse, readJson, cleanText } from "../_shared/http.ts";
import {
  requireInstallation, requireUser, sha256,
} from "../_shared/security.ts";

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return jsonResponse({ ok: true });
  if (req.method !== "POST") return jsonResponse({ error: "METHOD_NOT_ALLOWED" }, 405);
  try {
    const body = await readJson(req);
    const action = cleanText(body.action, 80);
    const hardwareId = cleanText(body.hardware_id, 128);

    if (action === "redeem_device_link_code") {
      const code = cleanText(body.link_code, 160).toUpperCase();
      if (code.length < 20) return jsonResponse({ error: "INVALID_LINK_CODE" }, 400);
      const { client, user } = await requireUser(req);
      const { data, error } = await client.rpc("redeem_device_link_code_server", {
        p_code_hash: await sha256(code),
        p_hardware_id: hardwareId,
        p_user_id: user.id,
        p_app_version: cleanText(body.app_version, 40) || null,
      });
      if (error) throw error;
      return jsonResponse(data, data?.ok ? 201 : 409);
    }

    const { client, installation } = await requireInstallation(req, hardwareId);

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
        .select("status, license_type, expires_at, offline_grace_hours, extra_messages, monthly_price, report_links, adjustment_notice, detailed_diagnostics_until")
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
      const dailyLimit = license.license_type === "trial" ? 6 : 30;
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
        .select("license_type").eq("installation_id", installation.id).single();
      if (licenseError) throw licenseError;
      const dailyLimit = license.license_type === "trial" ? 6 : 30;
      const { data, error } = await client.rpc("consume_message_server", {
        p_installation_id: installation.id, p_daily_limit: dailyLimit,
      });
      if (error) throw error;
      return jsonResponse(data);
    }

    if (action === "create_pix") {
      const { data: license, error: licenseError } = await client.from("licenses")
        .select("monthly_price").eq("installation_id", installation.id).single();
      if (licenseError) throw licenseError;
      const { data: config, error: configError } = await client.from("system_config")
        .select("default_monthly_price").eq("singleton", true).single();
      if (configError) throw configError;
      const amount = Number(license.monthly_price ?? config.default_monthly_price ?? 250);
      if (!Number.isFinite(amount) || amount <= 0) throw new Error("INVALID_PAYMENT_AMOUNT");
      const providerResponse = await fetch("https://saas-pix-api.onrender.com/gerar_pix", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          valor: Math.round(amount * 100) / 100,
          descricao: "Assinatura Mensal (30 dias) - SaaS Assistente PRO",
          email: "cliente@software.com.br",
        }),
        signal: AbortSignal.timeout(65000),
      });
      if (!providerResponse.ok) throw new Error("PAYMENT_PROVIDER_ERROR");
      const providerData = await providerResponse.json();
      const paymentId = cleanText(providerData.payment_id, 160);
      const qrCode = cleanText(providerData.qr_code_str, 8000);
      if (!providerData.sucesso || !paymentId || !qrCode) throw new Error("PAYMENT_PROVIDER_ERROR");
      const { error: sessionError } = await client.from("payment_sessions").insert({
        provider_payment_id: paymentId,
        installation_id: installation.id,
        amount,
        status: "pending",
        expires_at: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(),
      });
      if (sessionError) throw sessionError;
      return jsonResponse({ ok: true, sucesso: true, payment_id: paymentId, qr_code_str: qrCode, amount });
    }

    if (action === "check_pix") {
      const paymentId = cleanText(body.payment_id, 160);
      const { data: payment, error: paymentError } = await client.from("payment_sessions")
        .select("provider_payment_id, status, expires_at")
        .eq("provider_payment_id", paymentId)
        .eq("installation_id", installation.id).maybeSingle();
      if (paymentError) throw paymentError;
      if (!payment) return jsonResponse({ error: "PAYMENT_NOT_FOUND" }, 404);
      if (payment.status === "applied") {
        const { data: currentLicense } = await client.from("licenses")
          .select("expires_at").eq("installation_id", installation.id).single();
        return jsonResponse({ ok: true, aprovado: true, already_applied: true, expires_at: currentLicense?.expires_at });
      }
      if (payment.status !== "pending" || Date.parse(payment.expires_at) < Date.now()) {
        return jsonResponse({ ok: true, aprovado: false, error: "PAYMENT_SESSION_EXPIRED" });
      }
      const verification = await fetch(
        `https://saas-pix-api.onrender.com/verificar_pagamento/${encodeURIComponent(paymentId)}`,
        { method: "GET", signal: AbortSignal.timeout(30000) },
      );
      if (!verification.ok) throw new Error("PAYMENT_PROVIDER_ERROR");
      const providerData = await verification.json();
      if (!providerData.aprovado) return jsonResponse({ ok: true, aprovado: false });
      const { data, error } = await client.rpc("apply_approved_payment_server", {
        p_installation_id: installation.id,
        p_provider_payment_id: paymentId,
      });
      if (error) throw error;
      return jsonResponse({ ...data, aprovado: Boolean(data?.ok) });
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
