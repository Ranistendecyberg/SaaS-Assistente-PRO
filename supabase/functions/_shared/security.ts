import { createClient, SupabaseClient } from "npm:@supabase/supabase-js@2";

export function serviceClient(): SupabaseClient {
  const url = Deno.env.get("SUPABASE_URL");
  const key = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!url || !key) throw new Error("SERVER_CONFIGURATION_ERROR");
  return createClient(url, key, { auth: { persistSession: false } });
}

export async function sha256(value: string): Promise<string> {
  const bytes = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)]
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

export function randomToken(bytes = 32): string {
  const data = crypto.getRandomValues(new Uint8Array(bytes));
  return [...data].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

export async function requireAdmin(req: Request, mutation = false) {
  const authorization = req.headers.get("authorization") || "";
  if (!authorization.startsWith("Bearer ")) throw new Error("UNAUTHORIZED");
  const token = authorization.slice(7);
  const client = serviceClient();
  const { data: authData, error: authError } = await client.auth.getUser(token);
  if (authError || !authData.user) throw new Error("UNAUTHORIZED");

  const { data: admin, error: adminError } = await client
    .from("admin_users")
    .select("user_id, role, active")
    .eq("user_id", authData.user.id)
    .maybeSingle();
  if (adminError) {
    console.error("admin_users lookup failed", adminError.code, adminError.message);
    throw new Error("ADMIN_LOOKUP_FAILED");
  }
  if (!admin?.active) throw new Error("FORBIDDEN");

  const encodedPayload = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
  const paddedPayload = encodedPayload.padEnd(
    encodedPayload.length + ((4 - encodedPayload.length % 4) % 4),
    "=",
  );
  const payload = JSON.parse(
    new TextDecoder().decode(
      Uint8Array.from(
        atob(paddedPayload),
        (char) => char.charCodeAt(0),
      ),
    ),
  );
  if (mutation && !["owner", "admin"].includes(admin.role)) {
    throw new Error("FORBIDDEN");
  }
  if (mutation && payload.aal !== "aal2") throw new Error("MFA_REQUIRED");
  return { client, user: authData.user, admin };
}

export async function requireInstallation(req: Request, hardwareId: string) {
  const token = req.headers.get("x-installation-token") || "";
  if (token.length < 40 || hardwareId.length < 8) throw new Error("UNAUTHORIZED");
  const client = serviceClient();
  const tokenHash = await sha256(token);
  const { data, error } = await client
    .from("installations")
    .select("id, company_id, hardware_id, status, app_version")
    .eq("hardware_id", hardwareId)
    .eq("token_hash", tokenHash)
    .maybeSingle();
  if (error || !data || data.status !== "active") throw new Error("UNAUTHORIZED");
  return { client, installation: data };
}

export async function claimLegacyInstallation(hardwareId: string, claimCode: string) {
  if (hardwareId.length < 8 || claimCode.length < 40) throw new Error("INVALID_CLAIM");
  const client = serviceClient();
  const claimHash = await sha256(claimCode.toUpperCase());
  const { data: installation, error } = await client
    .from("installations")
    .select("id, hardware_id, status, migration_claim_until, migration_claimed_at")
    .eq("hardware_id", hardwareId)
    .eq("migration_claim_hash", claimHash)
    .maybeSingle();
  if (error) throw new Error("CLAIM_LOOKUP_FAILED");
  if (!installation || installation.migration_claimed_at) throw new Error("INVALID_CLAIM");
  if (!installation.migration_claim_until || Date.parse(installation.migration_claim_until) < Date.now()) {
    throw new Error("CLAIM_EXPIRED");
  }
  const installationToken = randomToken();
  const { error: updateError } = await client.from("installations").update({
    token_hash: await sha256(installationToken),
    token_issued_at: new Date().toISOString(),
    status: "active",
    migration_claim_hash: null,
    migration_claim_until: null,
    migration_claimed_at: new Date().toISOString(),
  }).eq("id", installation.id).eq("migration_claim_hash", claimHash);
  if (updateError) throw new Error("CLAIM_UPDATE_FAILED");
  await client.from("audit_events").insert({
    actor_installation_id: installation.id,
    action: "installation.legacy_claimed",
    target_type: "installation",
    target_id: installation.id,
    metadata: {},
  });
  return { installation, installationToken };
}

export async function installationBootstrapMode(hardwareId: string) {
  if (hardwareId.length < 8) throw new Error("INVALID_HARDWARE");
  const client = serviceClient();
  const { data, error } = await client.from("installations")
    .select("status, migration_claim_hash, migration_claimed_at")
    .eq("hardware_id", hardwareId)
    .maybeSingle();
  if (error) throw new Error("INSTALLATION_LOOKUP_FAILED");
  if (!data) return { mode: "new" };
  if (data.migration_claim_hash && !data.migration_claimed_at) return { mode: "legacy" };
  return { mode: "recovery_required" };
}
