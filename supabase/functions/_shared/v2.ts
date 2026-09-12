import { SupabaseClient } from "npm:@supabase/supabase-js@2";

export function normalizeCnpj(value: unknown): string {
  return String(value ?? "").replace(/\D/g, "");
}

export function validCnpj(value: unknown): boolean {
  const digits = normalizeCnpj(value);
  if (digits.length !== 14 || /^(\d)\1{13}$/.test(digits)) return false;
  const check = (base: string, weights: number[]) => {
    const remainder = [...base].reduce(
      (sum, digit, index) => sum + Number(digit) * weights[index],
      0,
    ) % 11;
    return String(remainder < 2 ? 0 : 11 - remainder);
  };
  const first = check(digits.slice(0, 12), [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]);
  const second = check(digits.slice(0, 12) + first, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]);
  return digits.endsWith(first + second);
}

export function validEmail(value: unknown): boolean {
  const email = String(value ?? "").trim().toLowerCase();
  return email.length <= 254 && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

export function validCpf(value: unknown): boolean {
  const digits = normalizeCnpj(value);
  if (digits.length !== 11 || /^(\d)\1{10}$/.test(digits)) return false;
  let base = digits.slice(0, 9);
  for (const size of [10, 11]) {
    const remainder = [...base].reduce((sum, digit, index) => sum + Number(digit) * (size - index), 0) % 11;
    base += String(remainder < 2 ? 0 : 11 - remainder);
  }
  return base === digits;
}

export function validDocument(value: unknown): boolean {
  return validCpf(value) || validCnpj(value);
}

export async function requireCompanyMember(
  client: SupabaseClient,
  userId: string,
  companyId: string,
  options: {
    mutation?: boolean;
    ownerOnly?: boolean;
    requireRecentEmail?: boolean;
    payload?: Record<string, unknown>;
  } = {},
) {
  if (!companyId) throw new Error("COMPANY_REQUIRED");
  const { data: member, error } = await client.from("company_members")
    .select("id, company_id, user_id, role, active")
    .eq("company_id", companyId)
    .eq("user_id", userId)
    .maybeSingle();
  if (error) throw new Error("MEMBERSHIP_LOOKUP_FAILED");
  if (!member?.active) throw new Error("FORBIDDEN");
  if (options.ownerOnly && member.role !== "owner") throw new Error("OWNER_REQUIRED");
  if (options.mutation && !["owner", "admin"].includes(member.role)) {
    throw new Error("FORBIDDEN");
  }
  if (options.mutation && options.requireRecentEmail !== false &&
      !hasRecentEmailConfirmation(options.payload)) {
    throw new Error("EMAIL_OTP_REQUIRED");
  }
  return member;
}

export function hasRecentEmailConfirmation(
  payload: Record<string, unknown> | undefined,
  maxAgeSeconds = 12 * 60 * 60,
): boolean {
  const methods = Array.isArray(payload?.amr) ? payload.amr : [];
  const now = Math.floor(Date.now() / 1000);
  return methods.some((entry) => {
    if (!entry || typeof entry !== "object") return false;
    const method = String((entry as Record<string, unknown>).method || "");
    const timestamp = Number((entry as Record<string, unknown>).timestamp || 0);
    return method === "otp" && Number.isFinite(timestamp) &&
      timestamp <= now + 60 && now - timestamp <= maxAgeSeconds;
  });
}
