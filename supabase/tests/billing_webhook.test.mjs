// Execute the actual handler in a VM. All network/database dependencies are fake.
// No Deno server, real credentials or external requests are used.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { stripTypeScriptTypes } from 'node:module';
import { createContext, runInContext } from 'node:vm';
import { createHmac, webcrypto } from 'node:crypto';

const source = await readFile(new URL('../functions/billing-api/index.ts', import.meta.url), 'utf8');
const http = await readFile(new URL('../functions/_shared/http.ts', import.meta.url), 'utf8');
const compiled = stripTypeScriptTypes(http.replace(/^export /gm, '') + '\n' +
  source.replace(/^import .*;\r?\n/gm, ''), { mode: 'transform' });
const secret = 'synthetic-webhook-secret';
let handler;
let calls, writes, mode;
const context = createContext({
  Request, Response, URL, TextEncoder, Uint8Array, Error, crypto: webcrypto,
  console: { error() {} },
  Deno: { env: { get: name => name === 'MERCADO_PAGO_WEBHOOK_SECRET' ? secret : 'synthetic-token' },
    serve: fn => { handler = fn; } },
  requireUser: async () => {
    if (!mode.startsWith('recovery')) throw new Error('UNAUTHORIZED');
    return { user: { id: 'fixture-user' }, payload: {}, client: { rpc: async (name) => {
      assert.equal(name, 'claim_payment_status_check_server');
      if (mode === 'recovery-throttle') return { data: { ok:false, error:'PAYMENT_RATE_LIMITED' } };
      return { data: { ok:true, provider_id:'123456', payment_method:'pix',
        external_reference: mode === 'recovery-identity' ? 'different-attempt' : 'fixture-attempt' } };
    } } };
  },
  requireCompanyMember: async (_client, _user, _company, options) => {
    assert.equal(options.ownerOnly, true);
    if (mode === 'recovery-forbidden') throw new Error('OWNER_REQUIRED');
  },
  serviceClient: () => ({ rpc: async (name, args) => {
    writes.push({ name, args });
    if (mode === 'database-error') return { error: new Error('synthetic failure') };
    if (mode === 'mismatch') return { data: { ok: false, error: 'AMOUNT_MISMATCH' } };
    return { data: { ok: true, duplicate: writes.length > 1 } };
  } }),
  fetch: async (url, init) => {
    calls.push({ url, method: init.method });
    assert.equal(url, 'https://api.mercadopago.com/v1/payments/123456');
    assert.equal(init.method, 'GET');
    if (mode === 'network-error') throw new Error('synthetic timeout');
    if (mode === 'provider-error') return Response.json({ error: 'unavailable' }, { status: 503 });
    return Response.json({ id: 123456, external_reference: 'fixture-attempt',
      transaction_amount: 350, status: 'approved', status_detail: 'accredited' });
  },
});
runInContext(compiled, context);
function request({ id = '123456', signedId = id, bad = false } = {}) {
  const ts = String(Date.now()), requestId = 'fixture-request';
  const signature = createHmac('sha256', secret)
    .update(`id:${signedId};request-id:${requestId};ts:${ts};`).digest('hex');
  return new Request(`https://fixture.invalid/?webhook=mercado_pago&type=payment&data.id=${id}`, {
    method: 'POST', headers: { 'x-request-id': requestId,
      'x-signature': `ts=${ts},v1=${bad ? '0'.repeat(64) : signature}` },
    // Untrusted body must never determine amount or status applied to SQL.
    body: JSON.stringify({ transaction_amount: 1, status: 'pending' }),
  });
}
async function check(name, fn, selected = '') {
  calls = []; writes = []; mode = selected;
  await fn(); console.log('PASS ' + name);
}
await check('assinatura inválida não consulta provedor nem banco', async () => {
  assert.equal((await handler(request({ bad: true }))).status, 401);
  assert.equal(calls.length + writes.length, 0);
});
await check('ID adulterado invalida assinatura', async () => {
  assert.equal((await handler(request({ id: '999', signedId: '123456' }))).status, 401);
  assert.equal(calls.length + writes.length, 0);
});
await check('webhook assinado usa valor e status do provedor, não do corpo', async () => {
  assert.equal((await handler(request())).status, 200);
  assert.equal(writes.length, 1);
  assert.equal(writes[0].name, 'apply_mercado_pago_order_server');
  assert.equal(writes[0].args.p_total_amount, '350.00');
  assert.equal(writes[0].args.p_provider_status, 'approved');
  assert.equal(writes[0].args.p_external_reference, 'fixture-attempt');
});
await check('repetição volta pela RPC idempotente', async () => {
  assert.equal((await handler(request())).status, 200);
  assert.equal((await handler(request())).status, 200);
  assert.equal(writes.length, 2); // Actual SQL duplicate semantics tested by PGlite suite.
});
for (const failure of ['network-error', 'provider-error']) {
  await check(failure + ' não aplica pagamento e permite reenvio HTTP', async () => {
    assert.equal((await handler(request())).status, 500);
    assert.equal(writes.length, 0);
  }, failure);
}
for (const failure of ['database-error', 'mismatch']) {
  await check(failure + ' não confirma processamento bem-sucedido', async () => {
    assert.equal((await handler(request())).status, 500);
  }, failure);
}
await check('requisição normal sem autenticação é recusada', async () => {
  const response = await handler(new Request('https://fixture.invalid/', {
    method: 'POST', body: JSON.stringify({ action: 'billing_summary', company_id: 'fixture' }),
  }));
  assert.equal(response.status, 401);
  assert.equal(calls.length + writes.length, 0);
});
for (const [selected, status, count] of [
  ['recovery',200,1], ['recovery-throttle',429,0],
  ['recovery-forbidden',403,0], ['recovery-identity',500,0],
]) {
  await check(selected + ' valida acesso, identidade e aplicação',async()=>{
    const response = await handler(new Request('https://fixture.invalid/', {
      method:'POST', body:JSON.stringify({ action:'refresh_payment_status',
        company_id:'fixture', attempt_id:'11111111-1111-4111-8111-111111111111',
        provider_id:'attacker-controlled-value', status:'approved', amount:1 }),
    }));
    assert.equal(response.status,status);
    assert.equal(writes.length,count);
    if (count) assert.equal(writes[0].args.p_total_amount,'350.00');
    if ([403,429].includes(status)) assert.equal(calls.length,0);
  },selected);
}
