import { cleanText, jsonResponse, readJson } from "../_shared/http.ts";
import { requireUser, serviceClient } from "../_shared/security.ts";
import { normalizeCnpj, requireCompanyMember, validDocument, validEmail } from "../_shared/v2.ts";

const MP_ORDERS_URL = "https://api.mercadopago.com/v1/orders";
const MP_PAYMENTS_URL = "https://api.mercadopago.com/v1/payments";

function env(name: string): string {
  const value = Deno.env.get(name) || "";
  if (!value) throw new Error("SERVER_CONFIGURATION_ERROR");
  return value;
}

function safeAmount(value: unknown): string {
  const amount = Number(value);
  if (!Number.isFinite(amount) || amount <= 0 || amount > 99999999.99) {
    throw new Error("INVALID_INVOICE_AMOUNT");
  }
  return amount.toFixed(2);
}

function splitName(value: unknown): [string, string] {
  const parts = cleanText(value, 180).split(/\s+/).filter(Boolean);
  return [parts.shift() || "Cliente", parts.join(" ") || "Empresa"];
}

function mercadoPagoErrorSummary(payload: unknown): Record<string, unknown> {
  if (!payload || typeof payload !== "object") return { message: "unknown" };
  const source = payload as Record<string, unknown>;
  const summary: Record<string, unknown> = {};
  for (const key of ["error", "message", "status"]) {
    const value = source[key];
    if (["string", "number", "boolean"].includes(typeof value)) {
      summary[key] = cleanText(value, 500);
    }
  }
  for (const key of ["cause", "errors"]) {
    const entries = Array.isArray(source[key]) ? source[key] as unknown[] : [];
    summary[key] = entries.slice(0, 8).map((entry) => {
      if (!entry || typeof entry !== "object") return cleanText(entry, 300);
      const item = entry as Record<string, unknown>;
      return {
        code: cleanText(item.code, 160),
        message: cleanText(item.message ?? item.description, 500),
      };
    });
  }
  return Object.keys(summary).length ? summary : { message: "unknown" };
}

function mercadoPagoErrorCode(payload: unknown): string {
  if (!payload || typeof payload !== "object") return "";
  const source = payload as Record<string, unknown>;
  for (const key of ["errors", "cause"]) {
    const entries = Array.isArray(source[key]) ? source[key] as unknown[] : [];
    for (const entry of entries) {
      if (!entry || typeof entry !== "object") continue;
      const code = cleanText((entry as Record<string, unknown>).code, 160);
      if (code) return code;
    }
  }
  return cleanText(source.error, 160);
}

class MercadoPagoRequestError extends Error {
  constructor(
    public readonly status: number,
    public readonly providerCode: string,
    public readonly requestId: string,
    public readonly providerSummary: Record<string, unknown>,
  ) {
    super(status === 429 ? "PAYMENT_RATE_LIMITED" : "PAYMENT_PROVIDER_ERROR");
    this.name = "MercadoPagoRequestError";
  }
}

async function mercadoPago(baseUrl: string, path: string, init: RequestInit = {}) {
  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers: {
      "Accept": "application/json",
      "Content-Type": "application/json",
      "Authorization": `Bearer ${env("MERCADO_PAGO_ACCESS_TOKEN")}`,
      ...(init.headers || {}),
    },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const requestId = cleanText(response.headers.get("x-request-id"), 180);
    const providerSummary = mercadoPagoErrorSummary(payload);
    console.error("Mercado Pago request failed", JSON.stringify({
      status: response.status,
      request_id: requestId,
      provider: providerSummary,
    }));
    throw new MercadoPagoRequestError(
      response.status,
      mercadoPagoErrorCode(payload),
      requestId,
      providerSummary,
    );
  }
  return payload;
}

async function rejectKnownAttempt(client: any, attemptId: string, error: MercadoPagoRequestError) {
  if (error.status < 400 || error.status >= 500 || [408, 409, 429].includes(error.status)
      || error.providerCode === "idempotency_key_already_used") return;
  const { error: updateError } = await client.from("billing_payment_attempts")
    .update({
      status: "rejected",
      provider_payload: {
        status: error.status,
        request_id: error.requestId,
        provider_code: error.providerCode,
        provider: error.providerSummary,
      },
    })
    .eq("id", attemptId)
    .is("provider_order_id", null);
  if (updateError) console.error("Unable to reject billing attempt", cleanText(updateError.code, 120));
}

async function cancelSupersededAttempts(client: any, attempts: unknown) {
  const rows = Array.isArray(attempts) ? attempts : [];
  for (const value of rows) {
    if (!value || typeof value !== "object") continue;
    const attempt = value as Record<string, unknown>;
    const attemptId = cleanText(attempt.id, 80);
    const method = cleanText(attempt.payment_method, 20);
    const providerId = cleanText(
      attempt.provider_payment_id || attempt.provider_order_id,
      180,
    );
    if (!attemptId || !providerId || method !== "pix") {
      // Boleto/Order requer conferência; nunca ignorar uma cobrança ainda pagável.
      throw new Error("PAYMENT_RECONCILIATION_REQUIRED");
    }

    const providerPayment = await mercadoPago(
      MP_PAYMENTS_URL,
      `/${encodeURIComponent(providerId)}`,
      { method: "GET" },
    );
    let providerStatus = cleanText(providerPayment.status, 80).toLowerCase();
    if (["pending", "in_process", "authorized"].includes(providerStatus)) {
      const cancelled = await mercadoPago(
        MP_PAYMENTS_URL,
        `/${encodeURIComponent(providerId)}`,
        { method: "PUT", body: JSON.stringify({ status: "cancelled" }) },
      );
      providerStatus = cleanText(cancelled.status, 80).toLowerCase();
    }
    if (providerStatus === "approved") {
      throw new Error("PAYMENT_RECONCILIATION_REQUIRED");
    }
    if (!["cancelled", "canceled", "expired", "rejected", "refunded"].includes(providerStatus)) {
      throw new Error("PAYMENT_REPRICE_CANCELLATION_FAILED");
    }
    const { error } = await client.from("billing_payment_attempts").update({
      provider_status: providerStatus,
      provider_status_detail: "invoice_seat_count_changed_cancelled",
    }).eq("id", attemptId).eq("status", "cancelled");
    if (error) throw error;
  }
}

async function validWebhook(req: Request, dataId: string): Promise<boolean> {
  const signature = req.headers.get("x-signature") || "";
  const requestId = req.headers.get("x-request-id") || "";
  const pieces = Object.fromEntries(signature.split(",").map((part) => {
    const [key, ...rest] = part.trim().split("=");
    return [key, rest.join("=")];
  }));
  const timestamp = pieces.ts || "";
  const received = pieces.v1 || "";
  if (!timestamp || !received || !requestId || !dataId) return false;
  const manifest = `id:${dataId.toLowerCase()};request-id:${requestId};ts:${timestamp};`;
  const key = await crypto.subtle.importKey(
    "raw", new TextEncoder().encode(env("MERCADO_PAGO_WEBHOOK_SECRET")),
    { name: "HMAC", hash: "SHA-256" }, false, ["verify"],
  );
  if (!/^[0-9a-f]{64}$/i.test(received)) return false;
  const bytes = new Uint8Array(received.match(/.{2}/g)!.map((hex) => parseInt(hex, 16)));
  return crypto.subtle.verify("HMAC", key, bytes, new TextEncoder().encode(manifest));
}

function paymentInfo(order: any) {
  const payment = order?.transactions?.payments?.[0] || order || {};
  const method = payment?.payment_method || {};
  const transactionData = payment?.point_of_interaction?.transaction_data || {};
  return {
    provider_payment_id: cleanText(payment.id, 180),
    payment_url: cleanText(method.ticket_url || transactionData.ticket_url, 2000),
    pix_copy_paste: cleanText(method.qr_code || transactionData.qr_code, 8000),
    boleto_barcode: cleanText(method.digitable_line || method.barcode_content, 400),
  };
}

async function reconcileProvider(providerId: string, providerType: string, expectedReference?: string) {
  const isPayment = providerType === "payment";
  const providerData = await mercadoPago(
    isPayment ? MP_PAYMENTS_URL : MP_ORDERS_URL,
    `/${encodeURIComponent(providerId)}`,
    { method: "GET" },
  );
  if (expectedReference !== undefined && (
    String(providerData.id) !== providerId || providerData.external_reference !== expectedReference
  )) throw new Error("PAYMENT_PROVIDER_IDENTITY_MISMATCH");
  const client = serviceClient();
  const { data, error } = await client.rpc("apply_mercado_pago_order_server", {
    p_provider_order_id: cleanText(providerData.id, 180),
    p_external_reference: cleanText(providerData.external_reference, 240),
    p_total_amount: safeAmount(providerData.transaction_amount ?? providerData.total_amount),
    p_provider_status: cleanText(providerData.status, 80),
    p_provider_status_detail: cleanText(providerData.status_detail, 120),
  });
  if (error) throw error;
  if (!data?.ok) throw new Error(data?.error || "PAYMENT_RECONCILIATION_FAILED");
  return data;
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return jsonResponse({ ok: true });
  const url = new URL(req.url);

  if (req.method === "POST" && url.searchParams.get("webhook") === "mercado_pago") {
    try {
      const dataId = cleanText(url.searchParams.get("data.id") || url.searchParams.get("data_id"), 180);
      if (!await validWebhook(req, dataId)) return jsonResponse({ error: "INVALID_SIGNATURE" }, 401);
      const providerType = cleanText(url.searchParams.get("type") || url.searchParams.get("topic"), 40);
      await reconcileProvider(dataId, providerType === "payment" ? "payment" : "order");
      return jsonResponse({ ok: true });
    } catch (error) {
      const code = error instanceof Error ? error.message : "INTERNAL_ERROR";
      console.error("Billing webhook failed", code);
      return jsonResponse({ error: "WEBHOOK_PROCESSING_FAILED" }, 500);
    }
  }

  if (req.method !== "POST") return jsonResponse({ error: "METHOD_NOT_ALLOWED" }, 405);
  try {
    const body = await readJson(req);
    const action = cleanText(body.action, 80);
    const companyId = cleanText(body.company_id, 64);
    const { client, user, payload } = await requireUser(req);
    const mutation = action === "save_billing_profile";
    const ownerOnly = ["save_billing_profile", "create_payment", "refresh_payment_status"].includes(action);
    await requireCompanyMember(client, user.id, companyId, {
      mutation, ownerOnly, payload,
    });

    if (action === "refresh_payment_status") {
      const attemptId = cleanText(body.attempt_id, 64);
      if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(attemptId)) {
        return jsonResponse({ error: "INVALID_ATTEMPT_ID" }, 400);
      }
      const { data: claim, error } = await client.rpc("claim_payment_status_check_server", {
        p_user_id: user.id, p_company_id: companyId, p_attempt_id: attemptId,
      });
      if (error) throw error;
      if (!claim?.ok) {
        const code = claim?.error || "PAYMENT_NOT_RECORDED";
        return jsonResponse({ error: code }, code === "PAYMENT_RATE_LIMITED" ? 429
          : code === "OWNER_REQUIRED" ? 403 : code === "PAYMENT_NOT_FOUND" ? 404 : 409);
      }
      if (!["pix", "boleto"].includes(claim.payment_method)) throw new Error("INVALID_PAYMENT_METHOD");
      const result = await reconcileProvider(claim.provider_id,
        claim.payment_method === "pix" ? "payment" : "order", claim.external_reference);
      return jsonResponse({ ok: true, result });
    }

    if (action === "billing_summary") {
      const [profile, invoices, installations, cases, subscription] = await Promise.all([
        client.from("billing_profiles").select("*").eq("company_id", companyId).maybeSingle(),
        client.from("billing_invoices")
          .select("id, period_start, period_end, due_at, principal_seats, additional_seats, installation_ids, base_price, additional_seat_price, total_amount, status, paid_at, billing_payment_attempts(id, payment_method, status, invoice_snapshot, payment_url, pix_copy_paste, boleto_barcode, expires_at)")
          .eq("company_id", companyId).order("created_at", { ascending: false }).limit(24),
        client.from("installations").select("id").eq("company_id",companyId).neq("billing_status","removed"),
        client.from("billing_reconciliation_cases").select("attempt_id").eq("company_id",companyId).is("resolved_at",null).limit(1),
        client.from("company_subscriptions").select("base_price,additional_seat_price,status").eq("company_id",companyId).single(),
      ]);
      if (profile.error) throw profile.error;
      if (invoices.error) throw invoices.error;
      if (installations.error) throw installations.error;
      if (cases.error) throw cases.error;
      if (subscription.error) throw subscription.error;
      const ids = JSON.stringify((installations.data || []).map((row: any) => row.id).sort());
      for (const invoice of invoices.data || []) {
        for (const attempt of invoice.billing_payment_attempts || []) {
          const snapshot = attempt.invoice_snapshot as any;
          const payable = invoice.status === "open" && attempt.status === "pending" && !!snapshot
            && JSON.stringify([...(snapshot.installation_ids || [])].sort()) === ids
            && Number(snapshot.total_amount) === Number(invoice.total_amount)
            && Number(invoice.base_price) === Number(subscription.data.base_price)
            && Number(invoice.additional_seat_price) === Number(subscription.data.additional_seat_price)
            && !["suspended","cancelled"].includes(subscription.data.status)
            && (!attempt.expires_at || Date.parse(attempt.expires_at) > Date.now())
            && !(cases.data || []).length;
          Object.assign(attempt, { payable, invoice_snapshot: undefined });
          if (!payable) Object.assign(attempt,{payment_url:null,pix_copy_paste:null,boleto_barcode:null});
        }
      }
      return jsonResponse({ ok: true, profile: profile.data, invoices: invoices.data || [],
        reconciliation_required: !!(cases.data || []).length });
    }

    if (action === "save_billing_profile") {
      const profile = {
        company_id: companyId,
        legal_name: cleanText(body.legal_name, 180),
        billing_cnpj: normalizeCnpj(body.billing_cnpj),
        billing_email: cleanText(body.billing_email, 254).toLowerCase(),
        postal_code: cleanText(body.postal_code, 16).replace(/\D/g, ""),
        street: cleanText(body.street, 180),
        street_number: cleanText(body.street_number, 40),
        address_extra: cleanText(body.address_extra, 120) || null,
        neighborhood: cleanText(body.neighborhood, 120),
        city: cleanText(body.city, 120),
        state: cleanText(body.state, 2).toUpperCase(),
      };
      if (profile.legal_name.length < 2 || !validDocument(profile.billing_cnpj) ||
          !validEmail(profile.billing_email) || profile.postal_code.length !== 8 ||
          !profile.street || !profile.street_number || !profile.neighborhood ||
          !profile.city || !/^[A-Z]{2}$/.test(profile.state)) {
        return jsonResponse({ error: "INVALID_BILLING_PROFILE" }, 400);
      }
      const { data, error } = await client.from("billing_profiles").upsert(profile)
        .select("*").single();
      if (error) throw error;
      return jsonResponse({ ok: true, profile: data });
    }

    if (action === "create_payment") {
      const method = cleanText(body.payment_method, 20);
      if (!["pix", "boleto"].includes(method)) {
        return jsonResponse({ error: "INVALID_PAYMENT_METHOD" }, 400);
      }
      const { data: profile, error: profileError } = await client.from("billing_profiles")
        .select("*").eq("company_id", companyId).maybeSingle();
      if (profileError) throw profileError;
      if (!profile) return jsonResponse({ error: "BILLING_PROFILE_REQUIRED" }, 409);

      const invoiceResult = await client.rpc("prepare_company_invoice_server", {
        p_user_id: user.id, p_company_id: companyId,
      });
      if (invoiceResult.error) throw invoiceResult.error;
      if (!invoiceResult.data?.ok) throw new Error(invoiceResult.data?.error || "INVOICE_PREPARATION_FAILED");
      let invoice = invoiceResult.data.invoice;
      await cancelSupersededAttempts(client, invoiceResult.data.superseded_attempts);
      const attemptResult = await client.rpc("prepare_billing_attempt_server", {
        p_user_id: user.id, p_invoice_id: invoice.id, p_payment_method: method,
      });
      if (attemptResult.error) throw attemptResult.error;
      if (!attemptResult.data?.ok) throw new Error(attemptResult.data?.error || "ATTEMPT_PREPARATION_FAILED");
      invoice = attemptResult.data.invoice;
      const attempt = attemptResult.data.attempt;
      if (attempt.provider_order_id) {
        return jsonResponse({ ok: true, reused: true, invoice, attempt });
      }
      if (attempt.status !== "pending") throw new Error("PAYMENT_RECONCILIATION_REQUIRED");

      const paymentMethod = method === "pix"
        ? { id: "pix", type: "bank_transfer" }
        : { id: "boleto", type: "ticket" };
      const payer: Record<string, unknown> = { email: profile.billing_email };
      if (method === "boleto") {
        const [firstName, lastName] = splitName(profile.legal_name);
        payer.first_name = firstName;
        payer.last_name = lastName;
        payer.identification = { type: profile.billing_cnpj.length === 11 ? "CPF" : "CNPJ", number: profile.billing_cnpj };
        payer.address = {
          zip_code: profile.postal_code,
          street_name: profile.street,
          street_number: profile.street_number || "S/N",
          neighborhood: profile.neighborhood,
          city: profile.city,
          state: profile.state,
        };
      }
      const amount = safeAmount(invoice.total_amount);
      const payment: Record<string, unknown> = {
        amount,
        payment_method: paymentMethod,
      };
      if (method === "boleto") payment.expiration_time = "P3D";
      const createProviderCharge = (currentAttempt: any) => {
        if (method === "pix") {
          // Mantem o fluxo comprovado da versao 1.9.6: Payments API.
          return mercadoPago(MP_PAYMENTS_URL, "", {
            method: "POST",
            headers: { "X-Idempotency-Key": currentAttempt.idempotency_key },
            body: JSON.stringify({
              transaction_amount: Number(amount),
              description: `SaaS Assistente PRO - ${invoice.period_start} a ${invoice.period_end}`,
              payment_method_id: "pix",
              notification_url: `${env("SUPABASE_URL")}/functions/v1/billing-api?webhook=mercado_pago`,
              external_reference: currentAttempt.external_reference,
              payer: { email: profile.billing_email },
            }),
          });
        }
        return mercadoPago(MP_ORDERS_URL, "", {
          method: "POST",
          headers: { "X-Idempotency-Key": currentAttempt.idempotency_key },
          body: JSON.stringify({
            type: "online",
            processing_mode: "automatic",
            total_amount: amount,
            external_reference: currentAttempt.external_reference,
            payer,
            transactions: { payments: [payment] },
          }),
        });
      };
      let order;
      try {
        order = await createProviderCharge(attempt);
      } catch (error) {
        if (!(error instanceof MercadoPagoRequestError)) throw error;
        await rejectKnownAttempt(client, attempt.id, error);
        if (error.providerCode === "idempotency_key_already_used") {
          throw new Error("PAYMENT_RECONCILIATION_REQUIRED");
        }
        throw error;
      }
      const info = paymentInfo(order);
      const recorded = await client.rpc("record_provider_order_server", {
        p_attempt_id: attempt.id,
        p_provider_order_id: cleanText(order.id, 180),
        p_provider_payment_id: info.provider_payment_id || null,
        p_provider_status: cleanText(order.status, 80),
        p_provider_status_detail: cleanText(order.status_detail, 120),
        p_payment_url: info.payment_url || null,
        p_pix_copy_paste: info.pix_copy_paste || null,
        p_boleto_barcode: info.boleto_barcode || null,
      });
      if (recorded.error) throw recorded.error;
      if (!recorded.data?.ok) throw new Error(recorded.data?.error || "ATTEMPT_RECORD_FAILED");
      if (recorded.data.attempt.status !== "pending") throw new Error("INVOICE_CHANGED");
      return jsonResponse({ ok: true, invoice, attempt: recorded.data.attempt }, 201);
    }

    return jsonResponse({ error: "UNKNOWN_ACTION" }, 400);
  } catch (error) {
    const code = error instanceof Error ? error.message : "INTERNAL_ERROR";
    const status = code === "UNAUTHORIZED" ? 401
      : ["FORBIDDEN", "OWNER_REQUIRED"].includes(code) ? 403
      : code === "EMAIL_OTP_REQUIRED" ? 428
      : ["PAYMENT_RECONCILIATION_REQUIRED", "PAYMENT_REPRICE_CANCELLATION_FAILED"].includes(code) ? 409
      : ["BILLING_PROFILE_REQUIRED", "INVOICE_NOT_OPEN", "INVOICE_CHANGED", "PAYMENT_METHOD_ALREADY_PENDING"].includes(code) ? 409
      : ["INVALID_PAYMENT_METHOD", "INVALID_BILLING_PROFILE"].includes(code) ? 400
      : code === "PAYMENT_RATE_LIMITED" ? 429
      : code === "PAYMENT_PROVIDER_ERROR" ? 502
      : 500;
    if (status === 500) console.error("Billing API failed", code);
    // Falhas conhecidas do provedor devem chegar ao Desktop com um codigo
    // seguro e acionavel. Somente erros internos inesperados sao ocultados.
    return jsonResponse({ error: status === 500 ? "INTERNAL_ERROR" : code }, status);
  }
});
