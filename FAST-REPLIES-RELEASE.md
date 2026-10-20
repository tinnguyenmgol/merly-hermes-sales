# Fast replies, separated limits; streaming deferred

Gateway runtime/Compose defaults (MERLY_ prefix):PUBLIC_PER_MINUTE120,
VISITOR_PER_MINUTE12, STOCK_PER_MINUTE30, AI_PER_MINUTE6, AI_PER_DAY100,
AI_CONCURRENT2, STOCK_CONCURRENT1. Config integers1..10000; concurrency <=2 each
and sum<=3 reserves fast capacity in existing1-worker/4-thread gateway. Do not
increase workers/replicas without shared coordination. Defaults do not raise paid
budget. Paid quota means CHAT TURNS, not provider API calls/dollars. Stock limit
means lookup actions, not individual Haravan GETs. All caps remain protected.

Policy allowlist =>local approved customer get_policy data. Complete explicit
model+size =>live stock. Complete heel-cm+size (e.g. can mau5cm size41) =>fixed
private /catalog-search, never inference. Other conversation retains Hermes.
Only approved metadata or explicit unique heel-cm in Haravan title is used;
ambiguous/missing/conflicting measurements never guessed. Additional customer
constraints not ignored. Catalog variants are not live stock; actual inventory
still checked via existing GET-only reader. No provider/Haravan key in gateway.

Old calls table retained, including historical pilot reservations; cannot safely
separate already-paid from unpaid history. No quota reset. Only NEW AI turns
reserve AI budget. Rate rows prune after60s. No destructive migration. Canonical
expiring topic/filter hints preserve context without prices/inventory/messages.
Catalog restore bounded5s, inventory never cached. No new container/dependency.

Pilot defects fixed:typed429/Retry-After, read-only AI-budget availability in
public session (no counts/identities), exact session locks (no hash collisions),
serialized SQLite writes in single worker. Initial load run exposed SQLite_BUSY;
fixed and rerun. Existing journal mode unchanged. No automatic retry/model replay.

318 tests + Chromium public/iframe/quick-policy/catalog/XSS checks pass.
performance/fast-policy-load.json is ACTUAL local Gunicorn1x4 result:100 concurrent
HTTP visitors querying warranty, all200, AI budget already100/full, zero inference;
synthetic stock200 and general AI429. Last p95~1.4s. NOT production/Haravan latency
or100-AI capacity. Async client used because Workspace cannot spawn100 OS threads.
No paid model call or production modification. Not every phrasing is accelerated.

Merge feat/fast-public-replies; deploy existing app; read public session
ai_availability and verify actual stock separately. No new key/DNS/theme edits.
Streaming, model tuning and100 simultaneous real AI turns remain out of scope.
