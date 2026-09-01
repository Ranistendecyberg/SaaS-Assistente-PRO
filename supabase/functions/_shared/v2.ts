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

export async function requireCompanyMember(
  client: SupabaseClient,
  userId: string,
  companyId: string,
  options: { mutation?: boolean; ownerOnly?: boolean; aal?: unknown } = {},
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
  if (options.mutation && options.aal !== "aal2") throw new Error("MFA_REQUIRED");
  return member;
}
