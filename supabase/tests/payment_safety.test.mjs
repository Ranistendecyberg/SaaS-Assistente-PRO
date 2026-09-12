import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const {PGlite}=require(process.env.PGLITE_MODULE || '@electric-sql/pglite');
const db=new PGlite();
// PostgreSQL descartável, sem rede. Stub de digest só testa resolução de schema;
// não testa a implementação criptográfica do pgcrypto do servidor.
await db.exec(`
create role anon; create role authenticated; create role service_role;
create schema extensions;
create function extensions.digest(text,text) returns bytea language sql immutable as $$ select decode(md5($1)||md5($1),'hex') $$;
create function extensions.gen_random_bytes(integer) returns bytea language sql as $$ select decode(repeat('ab',$1),'hex') $$;
create table companies(id uuid primary key default gen_random_uuid(),name text);
create table company_members(company_id uuid,user_id uuid,role text,active boolean);
create table company_subscriptions(id uuid default gen_random_uuid(),company_id uuid primary key,
 status text,base_price numeric,additional_seat_price numeric,current_period_start timestamptz,
 current_period_end timestamptz,trial_expires_at timestamptz);
create table installations(id uuid primary key default gen_random_uuid(),company_id uuid,status text default 'active',
 device_class text,billing_status text default 'active',removal_scheduled_for timestamptz);
create table licenses(installation_id uuid primary key,status text,license_type text,expires_at timestamptz);
create table billing_invoices(id uuid primary key default gen_random_uuid(),company_id uuid,period_start date,period_end date,
 due_at timestamptz,principal_seats integer,additional_seats integer,base_price numeric,additional_seat_price numeric,
 total_amount numeric,status text,paid_at timestamptz,created_at timestamptz default now(),unique(company_id,period_start,period_end));
create table billing_payment_attempts(id uuid primary key default gen_random_uuid(),invoice_id uuid references billing_invoices(id),
 payment_method text,external_reference text,idempotency_key text,status text,expires_at timestamptz,
 provider_payment_id text,payment_url text,pix_copy_paste text,boleto_barcode text,
 provider_payload jsonb default '{}',created_at timestamptz default now());
create table audit_events(action text,target_type text,target_id text,metadata jsonb,actor_user_id uuid,actor_installation_id uuid);
create table business_units(id uuid primary key,company_id uuid,active boolean);
create table device_link_codes(id uuid primary key default gen_random_uuid(),company_id uuid,code_hash text,
 business_unit_id uuid,created_by uuid,status text,expires_at timestamptz,redeemed_by_installation uuid,
 redeemed_by_user uuid,redeemed_at timestamptz);
alter table installations add column hardware_id text unique,add column business_unit_id uuid,
 add column token_hash text,add column token_issued_at timestamptz,add column app_version text,
 add column activated_by uuid,add column activated_at timestamptz,add column created_at timestamptz default now();
alter table licenses add column monthly_price numeric,add column report_links jsonb,
 add column adjustment_notice text,add column detailed_diagnostics_until timestamptz;
`);
const migration=async name=>db.exec(await readFile(new URL('../migrations/'+name,import.meta.url),'utf8'));
await migration('015_v2_consolidated_billing.sql');
await migration('018_v2_simple_device_activation.sql');
await migration('019_v2_invoice_seat_consistency.sql');
await migration('020_v2_payment_snapshot_safety.sql');
await migration('020_v2_payment_snapshot_safety.sql');
const scalar=async(sql,args=[]) => (await db.query(sql,args)).rows[0].value;
const rpc=async(name,args)=>scalar(`select public.${name}(${args.map((_,i)=>'$'+(i+1)).join(',')}) as value`,args);
let n=0;
async function setup(){
 const company=await scalar("insert into companies(name) values ('Teste') returning id as value");
 const owner=await scalar('select gen_random_uuid() as value');
 await db.query("insert into company_members values($1,$2,'owner',true)",[company,owner]);
 await db.query("insert into company_subscriptions(company_id,status,base_price,additional_seat_price,current_period_end) values($1,'active',300,50,now()+interval '2 days')",[company]);
 const machine=await add(company,'principal');return {company,owner,machine};
}
async function add(company,kind='additional'){
 const machine=await scalar('insert into installations(company_id,device_class) values($1,$2) returning id as value',[company,kind]);
 await db.query("insert into licenses(installation_id,status,license_type,expires_at) values($1,'active','subscription',now()+interval '2 days')",[machine]);return machine;
}
async function charge(c){
 const prepared=await rpc('prepare_company_invoice_server',[c.owner,c.company]);assert.equal(prepared.ok,true,JSON.stringify(prepared));
 const attempt=await rpc('prepare_billing_attempt_server',[c.owner,prepared.invoice.id,'pix']);assert.equal(attempt.ok,true,JSON.stringify(attempt));
 const order='test-'+(++n);
 assert.equal((await rpc('record_provider_order_server',[attempt.attempt.id,order,order,'pending','pending',null,'QRTEST',null])).ok,true);
 return {...attempt,order};
}
const pay=(c,amount=c.invoice.total_amount,status='approved')=>rpc('apply_mercado_pago_order_server',[c.order,c.attempt.external_reference,amount,status,'accredited']);
async function check(name,fn){await fn();console.log('PASS '+name);}
await check('pagamento válido, duplicado e evento atrasado',async()=>{
 const c=await setup(),p=await charge(c);assert.equal((await pay(p)).invoice_status,'paid');
 assert.equal((await pay(p)).duplicate,true);assert.equal((await pay(p,p.invoice.total_amount,'pending')).ignored,true);
 assert.equal(await scalar('select status as value from billing_payment_attempts where id=$1',[p.attempt.id]),'approved');
});
await check('PIX antigo com máquina nova não renova; conciliação idempotente',async()=>{
 const c=await setup(),p=await charge(c);await add(c.company);
 const expiry=await scalar('select current_period_end::text as value from company_subscriptions where company_id=$1',[c.company]);
 assert.equal((await pay(p)).reason,'SEAT_SNAPSHOT_MISMATCH');
 assert.equal(await scalar('select current_period_end::text as value from company_subscriptions where company_id=$1',[c.company]),expiry);
 assert.equal((await rpc('prepare_company_invoice_server',[c.owner,c.company])).error,'PAYMENT_RECONCILIATION_REQUIRED');
 assert.equal((await pay(p)).reconciliation_required,true);
 assert.equal(await scalar('select count(*)::int as value from billing_reconciliation_cases where company_id=$1',[c.company]),1);
});
await check('troca de máquina com mesma quantidade e preço',async()=>{
 const c=await setup(),old=await add(c.company),p=await charge(c);
 await db.query("update installations set billing_status='removed' where id=$1",[old]);await add(c.company);
 assert.equal((await pay(p)).reason,'SEAT_SNAPSHOT_MISMATCH');
});
await check('máquina vinculada depois de pagar não herda período pago',async()=>{
 const c=await setup(),p=await charge(c);await pay(p);const extra=await add(c.company);
 assert.equal(await scalar('select status as value from licenses where installation_id=$1',[extra]),'blocked');
 await db.query("update licenses set status='active',expires_at=now()+interval '15 days' where installation_id=$1",[extra]);
 assert.equal(await scalar('select status as value from licenses where installation_id=$1',[extra]),'blocked');
});
await check('recalcular cancela tentativa anterior e gera snapshot novo',async()=>{
 const c=await setup(),p=await charge(c);await add(c.company);
 const q=await charge(c);assert.equal(Number(q.invoice.total_amount),350);
 assert.notEqual(q.attempt.id,p.attempt.id);assert.equal((await pay(q)).invoice_status,'paid');
 assert.equal((await pay(p)).reason,'ATTEMPT_NOT_PAYABLE');
});
await check('valores inválidos ou inferiores não renovam',async()=>{
 const c=await setup(),p=await charge(c);assert.equal((await pay(p,null)).error,'AMOUNT_MISMATCH');
 assert.equal((await pay(p,300.001)).error,'AMOUNT_MISMATCH');assert.equal((await pay(p,1)).reason,'AMOUNT_MISMATCH');
});
await check('bloqueio individual preservado no pagamento',async()=>{
 const c=await setup(),extra=await add(c.company),p=await charge(c);
 await db.query("update installations set status='blocked',billing_status='blocked' where id=$1",[extra]);
 assert.equal((await pay(p)).invoice_status,'paid');assert.equal(await scalar('select status as value from licenses where installation_id=$1',[extra]),'blocked');
});
await check('reembolso exige conferência',async()=>{
 const c=await setup(),p=await charge(c);await pay(p);assert.equal((await pay(p,p.invoice.total_amount,'refunded')).reason,'PAYMENT_REFUNDED');
 const resolution=await rpc('resolve_billing_refund_server',[c.owner,p.attempt.id]);
 assert.equal(resolution.ok,true,JSON.stringify(resolution));
 assert.equal(await scalar('select status as value from licenses where installation_id=$1',[c.machine]),'blocked');
 assert.equal(await scalar('select status as value from billing_invoices where id=$1',[p.invoice.id]),'refunded');
 assert.equal((await rpc('resolve_billing_refund_server',[c.owner,p.attempt.id])).error,'RECONCILIATION_NOT_PENDING');
});
await check('remoção agendada preservada ao liberar máquina',async()=>{
 const c=await setup(),extra=await add(c.company);
 await db.query("update installations set billing_status='pending_removal',removal_scheduled_for=now()+interval '1 day' where id=$1",[extra]);
 await db.query("update installations set status='active',billing_status='active' where id=$1",[extra]);
 assert.equal(await scalar('select billing_status as value from installations where id=$1',[extra]),'pending_removal');
});
await check('snapshot imutável, exclusão protegida e meio de pagamento único',async()=>{
 const c=await setup(),p=await charge(c);
 await assert.rejects(db.query("update billing_payment_attempts set invoice_snapshot='{}' where id=$1",[p.attempt.id]),/IMMUTABLE_PAYMENT_SNAPSHOT/);
 await assert.rejects(db.query('delete from installations where id=$1',[c.machine]),/ENTERPRISE_DEVICE_DELETE_FORBIDDEN/);
 assert.equal((await rpc('prepare_billing_attempt_server',[c.owner,p.invoice.id,'boleto'])).error,'PAYMENT_METHOD_ALREADY_PENDING');
});
await check('funções internas e webhook não estão expostos aos papéis públicos',async()=>{
 assert.equal(await scalar("select has_function_privilege('service_role','public.apply_mercado_pago_order_v019(text,text,numeric,text,text)','execute') as value"),false);
 assert.equal(await scalar("select has_function_privilege('anon','public.apply_mercado_pago_order_server(text,text,numeric,text,text)','execute') as value"),false);
});
await check('preço alterado pelo Admin invalida o pagamento antigo',async()=>{
 const c=await setup(),p=await charge(c);
 await db.query('update company_subscriptions set base_price=400 where company_id=$1',[c.company]);
 assert.equal((await pay(p)).reason,'INVOICE_PRICE_CHANGED');
});
await check('resposta tardia fica associada sem reexibir QR cancelado',async()=>{
 const c=await setup(),p=await charge(c);await add(c.company);
 await rpc('prepare_company_invoice_server',[c.owner,c.company]);
 const r=await rpc('record_provider_order_server',[p.attempt.id,p.order,p.order,'pending','pending',null,'LATEQR',null]);
 assert.equal(r.attempt.status,'cancelled');assert.equal(r.attempt.pix_copy_paste,null);
 assert.equal(r.attempt.provider_status_detail,'invoice_seat_count_changed');
});
await check('cobrança legada sem snapshot exige conferência',async()=>{
 const c=await setup(),p=await charge(c);
 await db.exec('alter table billing_payment_attempts disable trigger billing_attempt_snapshot');
 await db.query('update billing_payment_attempts set invoice_snapshot=null where id=$1',[p.attempt.id]);
 await db.exec('alter table billing_payment_attempts enable trigger billing_attempt_snapshot');
 assert.equal((await pay(p)).reason,'LEGACY_PAYMENT_SNAPSHOT_REQUIRED');
});
await check('resgate real revalida emissor e não libera nova máquina após pagamento',async()=>{
 const c=await setup(),p=await charge(c);await pay(p);
 const hash='a'.repeat(64);
 await db.query("insert into device_link_codes(company_id,code_hash,created_by,status,expires_at) values($1,$2,$3,'new',now()+interval '15 minutes')",[c.company,hash,c.owner]);
 await db.query('update company_members set active=false where company_id=$1',[c.company]);
 assert.equal((await rpc('redeem_device_link_code_server',[hash,'HARDWARE-REAL-TEST','2.0.3'])).error,'LINK_CODE_NOT_AVAILABLE');
 await db.query('update company_members set active=true where company_id=$1',[c.company]);
 const redeemed=await rpc('redeem_device_link_code_server',[hash,'HARDWARE-REAL-TEST','2.0.3']);
 assert.equal(redeemed.ok,true,JSON.stringify(redeemed));
 assert.equal(await scalar('select status as value from licenses where installation_id=$1',[redeemed.installation_id]),'blocked');
});
await check('PIX 350 renova principal e adicional uma vez, sem atingir outra conta',async()=>{
 const c=await setup(),extra=await add(c.company),other=await setup();
 const beforeOther=await scalar('select row_to_json(l)::text as value from licenses l where installation_id=$1',[other.machine]);
 const p=await charge(c);assert.equal(Number(p.invoice.total_amount),350);
 assert.equal((await pay(p)).invoice_status,'paid');
 const first=await scalar('select json_agg(l order by installation_id)::text as value from licenses l where installation_id in ($1,$2)',[c.machine,extra]);
 assert.equal(await scalar("select count(*)::int as value from licenses where installation_id in ($1,$2) and status='active' and expires_at > now()+interval '2 days'",[c.machine,extra]),2);
 assert.equal((await pay(p)).duplicate,true);
 assert.equal(await scalar('select json_agg(l order by installation_id)::text as value from licenses l where installation_id in ($1,$2)',[c.machine,extra]),first);
 assert.equal(await scalar('select row_to_json(l)::text as value from licenses l where installation_id=$1',[other.machine]),beforeOther);
});
await migration('023_v2_payment_status_recovery.sql');
await check('recuperação exige dono, isola conta e limita consultas sem renovar',async()=>{
 const c=await setup(),p=await charge(c),other=await setup();
 const before=await scalar('select row_to_json(l)::text as value from licenses l where installation_id=$1',[c.machine]);
 assert.equal((await rpc('claim_payment_status_check_server',[other.owner,c.company,p.attempt.id])).error,'OWNER_REQUIRED');
 assert.equal((await rpc('claim_payment_status_check_server',[other.owner,other.company,p.attempt.id])).error,'PAYMENT_NOT_FOUND');
 const claim=await rpc('claim_payment_status_check_server',[c.owner,c.company,p.attempt.id]);
 assert.equal(claim.ok,true); assert.equal(claim.provider_id,p.order);
 assert.equal((await rpc('claim_payment_status_check_server',[c.owner,c.company,p.attempt.id])).error,'PAYMENT_RATE_LIMITED');
 assert.equal(await scalar('select row_to_json(l)::text as value from licenses l where installation_id=$1',[c.machine]),before);
 assert.equal(await scalar("select has_function_privilege('authenticated','claim_payment_status_check_server(uuid,uuid,uuid)','EXECUTE') as value"),false);
});
await db.close();
