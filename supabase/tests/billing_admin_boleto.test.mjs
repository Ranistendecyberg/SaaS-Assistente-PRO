// Exercise the real auth and billing handler with fake DB/provider dependencies.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { stripTypeScriptTypes } from 'node:module';
import { createContext, runInContext } from 'node:vm';
import { webcrypto } from 'node:crypto';

const sources = await Promise.all([
  '../functions/_shared/http.ts', '../functions/_shared/security.ts',
  '../functions/_shared/v2.ts', '../functions/billing-api/index.ts',
].map(path => readFile(new URL(path, import.meta.url), 'utf8')));
const code = stripTypeScriptTypes(sources.map(source => source
  .replace(/^import .*;\r?\n/gm, '').replace(/^export /gm, '')).join('\n'), { mode: 'transform' });
const companyId = '11111111-1111-4111-8111-111111111111';
const invoice = { id: 'invoice-1', company_id: companyId, status: 'open', total_amount: '300.00',
  base_price: 300, additional_seat_price: 50 };
let config, calls, audits, profileWrites, handler;
function reset(extra = {}) {
  config = { adminRole: 'admin', aal: 'aal2', owner: true, method: 'boleto', ...extra };
  calls = []; audits = []; profileWrites = [];
}
const db = {
  auth: { getUser: async () => ({ data: { user: { id: 'admin-actor' } } }) },
  from(table) {
    let inserted, profile;
    const builder = {
      select() { return this; }, eq() { return this; }, gt() { return this; }, is() { return this; },
      neq() { return this; }, order() { return this; }, limit() { return this; },
      insert(row) { inserted = row; audits.push(row); return this; },
      upsert(row) { profile = row; profileWrites.push(row); return this; },
      single() { return Promise.resolve(result()); },
      maybeSingle() { return Promise.resolve(result()); },
      then(resolve, reject) { return Promise.resolve(result()).then(resolve, reject); },
    };
    function result() {
      if (inserted) return { data: null, error: null };
      if (profile) return { data: profile, error: null };
      const data = {
        admin_users: config.adminRole ? { role: config.adminRole, active: true } : null,
        companies: { id: companyId },
        company_members: config.owner ? { user_id: 'company-owner', role: 'owner', active: true } : null,
        billing_profiles: { legal_name: 'Fixture Company', billing_email: 'fixture@example.test' },
        billing_reconciliation_cases: [], billing_payment_test_companies: null,
        installations: [{ id: 'seat-1' }],
        company_subscriptions: { base_price: 300, additional_seat_price: 50, status: 'active' },
        billing_invoices: [{ ...invoice, billing_payment_attempts: [{
          id: 'attempt-1', payment_method: config.method, status: 'pending',
          payment_url: 'https://example.test/boleto', boleto_barcode: 'synthetic-barcode',
          invoice_snapshot: { installation_ids: ['seat-1'], total_amount: '300.00' },
        }] }],
      };
      return { data: data[table], error: null };
    }
    return builder;
  },
  async rpc(name, args) {
    calls.push({ name, args });
    if (name === 'prepare_company_invoice_server') return { data: { ok: true, invoice } };
    if (name === 'prepare_billing_attempt_server') return { data: { ok: true, invoice,
      attempt: { id: 'attempt-1', payment_method: args.p_payment_method,
        provider_order_id: 'existing-fixture-order', status: 'pending' } } };
    throw new Error('Unexpected RPC: ' + name);
  },
};
const context = createContext({ Request, Response, URL, TextEncoder, TextDecoder, Uint8Array,
  Error, atob, crypto: webcrypto, createClient: () => db,
  console: { error() {} }, fetch: () => { throw new Error('No real provider request allowed'); },
  Deno: { env: { get: () => 'synthetic' }, serve: fn => { handler = fn; } },
});
runInContext(code, context);
async function request(action, extra = {}) {
  const payload = Buffer.from(JSON.stringify({ aal: config.aal })).toString('base64url');
  const response = await handler(new Request('https://example.test/billing-api', {
    method: 'POST', headers: { authorization: `Bearer fixture.${payload}.signature` },
    body: JSON.stringify({ action, company_id: companyId, ...extra }),
  }));
  return { status: response.status, body: await response.json() };
}

reset();
let result = await request('create_payment', { payment_method: 'boleto' });
assert.equal(result.status, 403);
assert.equal(result.body.error, 'BOLETO_ADMIN_ONLY');
assert.equal(calls.length, 0);

for (const options of [{ adminRole: null }, { adminRole: 'viewer' }, { aal: 'aal1' }]) {
  reset(options);
  result = await request('admin_create_boleto');
  assert.ok([403, 428].includes(result.status));
  assert.equal(calls.length, 0);
  assert.equal(audits.length, 0);
}

reset();
result = await request('admin_create_boleto', { payment_method: 'pix', user_id: 'spoofed-owner' });
assert.equal(result.status, 200);
assert.equal(result.body.attempt.payment_method, 'boleto');
assert.equal(calls[0].args.p_user_id, 'company-owner');
assert.equal(calls[1].args.p_user_id, 'company-owner');
assert.equal(calls[1].args.p_payment_method, 'boleto');
assert.equal(audits[0].actor_user_id, 'admin-actor');
assert.equal(audits[0].action, 'billing.boleto_requested');

reset({ owner: false });
result = await request('admin_create_boleto');
assert.equal(result.body.error, 'BILLING_OWNER_REQUIRED');
assert.equal(calls.length, 0);

reset();
result = await request('billing_summary');
const customerAttempt = result.body.invoices[0].billing_payment_attempts[0];
assert.equal(customerAttempt.boleto_barcode, null);
assert.equal(customerAttempt.payment_url, null);
assert.equal(customerAttempt.payable, true); // Metadata preserves pending-charge reconciliation.
result = await request('admin_billing_summary');
assert.equal(result.body.invoices[0].billing_payment_attempts[0].boleto_barcode, 'synthetic-barcode');

reset({ method: 'pix' });
result = await request('create_payment', { payment_method: 'pix' });
assert.equal(result.status, 200);
assert.equal(result.body.attempt.payment_method, 'pix');

const profile = { legal_name: 'Fixture Payer', billing_cnpj: '11144477735',
  billing_email: 'fixture@example.test', postal_code: '64000000', street: 'Rua fictícia',
  street_number: '10', neighborhood: 'Centro', city: 'Teresina', state: 'pi' };
reset({ owner: false }); // Cadastro administrativo não exige vínculo do Admin nem titular na empresa.
result = await request('admin_save_billing_profile', profile);
assert.equal(result.status, 200);
assert.equal(profileWrites[0].company_id, companyId);
assert.equal(profileWrites[0].state, 'PI');
assert.equal(audits[0].actor_user_id, 'admin-actor');
assert.equal(audits[0].action, 'billing.profile_update_requested');
assert.equal(calls.length, 0); // Salvar dados não cria cobrança.
reset();
result = await request('admin_save_billing_profile', { ...profile, billing_cnpj: '123' });
assert.equal(result.status, 400);
assert.equal(result.body.error, 'INVALID_BILLING_PROFILE');
assert.equal(profileWrites.length, 0);
for (const options of [{ adminRole: null }, { adminRole: 'viewer' }, { aal: 'aal1' }]) {
  reset(options);
  result = await request('admin_save_billing_profile', profile);
  assert.ok([403, 428].includes(result.status));
  assert.equal(profileWrites.length, 0);
}
console.log('Billing: PIX desktop, admin-only boleto, MFA, delegation and redaction passed.');
