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

function jwtPayload(token: string): Record<string, unknown> {
  const encodedPayload = token.split(".")[1];
  if (!encodedPayload) throw new Error("UNAUTHORIZED");
  const normalized = encodedPayload.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized.padEnd(
    normalized.length + ((4 - normalized.length % 4) % 4),
    "=",
  );
  try {
    return JSON.parse(
      new TextDecoder().decode(
        Uint8Array.from(atob(padded), (char) => char.charCodeAt(0)),
      ),
    );
  } catch {
    throw new Error("UNAUTHORIZED");
  }
}

export async function requireUser(req: Request) {
  const authorization = req.headers.get("authorization") || "";
  if (!authorization.startsWith("Bearer ")) throw new Error("UNAUTHORIZED");
  const token = authorization.slice(7);
  const client = serviceClient();
  const { data, error } = await client.auth.getUser(token);
  if (error || !data.user) throw new Error("UNAUTHORIZED");
  return { client, user: data.user, payload: jwtPayload(token) };
}

export async function requireAdmin(req: Request, mutation = false) {
  const { client, user, payload } = await requireUser(req);

  const { data: admin, error: adminError } = await client
    .from("admin_users")
    .select("user_id, role, active")
    .eq("user_id", user.id)
    .maybeSingle();
  if (adminError) {
    console.error("admin_users lookup failed", adminError.code, adminError.message);
    throw new Error("ADMIN_LOOKUP_FAILED");
  }
  if (!admin?.active) throw new Error("FORBIDDEN");

  if (mutation && !["owner", "admin"].includes(admin.role)) {
    throw new Error("FORBIDDEN");
  }
  if (mutation && payload.aal !== "aal2") throw new Error("MFA_REQUIRED");
  return { client, user, admin };
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
