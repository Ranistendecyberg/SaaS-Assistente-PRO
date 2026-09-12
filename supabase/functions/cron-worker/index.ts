import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

function serviceClient() {
  const supabaseUrl = Deno.env.get("SUPABASE_URL");
  const supabaseKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!supabaseUrl || !supabaseKey) {
    throw new Error("MISSING_SERVICE_CONFIGURATION");
  }
  return createClient(supabaseUrl, supabaseKey, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
}

async function runMaintenance() {
  const client = serviceClient();
  let telemetryDeleted = 0;
  let reservationsDeleted = 0;
  let removalsProcessed = 0;

  // Drena alguns lotes por execução sem criar uma transação longa nem trazer
  // todas as linhas para a memória da Edge Function.
  for (let batch = 0; batch < 4; batch += 1) {
    const { data, error } = await client.rpc("cleanup_expired_telemetry", {
      p_batch_size: 5000,
    });
    if (error) throw new Error(`TELEMETRY_CLEANUP_FAILED: ${error.message}`);
    const count = Number(data || 0);
    telemetryDeleted += count;
    if (count < 5000) break;
  }

  for (let batch = 0; batch < 4; batch += 1) {
    const { data, error } = await client.rpc("cleanup_completed_message_reservations", {
      p_batch_size: 5000,
    });
    if (error) throw new Error(`RESERVATION_CLEANUP_FAILED: ${error.message}`);
    const count = Number(data || 0);
    reservationsDeleted += count;
    if (count < 5000) break;
  }

  for (let batch = 0; batch < 4; batch += 1) {
    const { data, error } = await client.rpc("process_due_device_removals_server", {
      p_batch_size: 250,
    });
    if (error) throw new Error(`DEVICE_REMOVAL_FAILED: ${error.message}`);
    const count = Number(data || 0);
    removalsProcessed += count;
    if (count < 250) break;
  }

  console.log(JSON.stringify({ telemetryDeleted, reservationsDeleted, removalsProcessed }));
}

// Fallback manual autenticado. O agendamento hospedado é feito pelo Supabase
// Cron diretamente nas RPCs do banco (migração 028), sem depender de APIs de
// agendamento específicas do runtime da Edge Function.
Deno.serve(async (req) => {
  if (req.method !== "POST") {
    return new Response("Method Not Allowed", { status: 405 });
  }
  const expectedSecret = Deno.env.get("CRON_SECRET");
  const suppliedSecret = req.headers.get("authorization")?.replace(/^Bearer\s+/i, "");
  if (!expectedSecret || suppliedSecret !== expectedSecret) {
    return new Response("Unauthorized", { status: 401 });
  }
  try {
    await runMaintenance();
    return new Response(JSON.stringify({ ok: true }), {
      headers: { "Content-Type": "application/json; charset=utf-8" },
    });
  } catch (error) {
    console.error(error instanceof Error ? error.message : "MAINTENANCE_FAILED");
    return new Response(JSON.stringify({ error: "MAINTENANCE_FAILED" }), {
      status: 500,
      headers: { "Content-Type": "application/json; charset=utf-8" },
    });
  }
});
