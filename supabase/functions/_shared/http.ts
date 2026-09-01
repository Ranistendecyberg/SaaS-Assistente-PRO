export const jsonHeaders = {
  "Content-Type": "application/json; charset=utf-8",
  "Cache-Control": "no-store",
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, apikey, content-type, x-installation-token",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: jsonHeaders });
}

export async function readJson(req: Request): Promise<Record<string, unknown>> {
  const contentLength = Number(req.headers.get("content-length") || "0");
  if (contentLength > 256_000) throw new Error("PAYLOAD_TOO_LARGE");
  const value = await req.json();
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("INVALID_JSON");
  }
  return value as Record<string, unknown>;
}

export function cleanText(value: unknown, max: number): string {
  return String(value ?? "").trim().slice(0, max);
}
