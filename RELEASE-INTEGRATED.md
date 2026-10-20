# Integrated Haravan sales release — private pilot only
Target: existing merly-hermes-sales / hermes-test.merlyshoes.com. Not old webchat
or Hermes management. Workspace cannot deploy/push production main.

Included together:
- Documented variant count/list pagination and product-option size/color mapping.
- New calls use server-generated v2 metadata, no nonce copied by model. Gateway
  binds authenticated current-turn native tool call/output, exact scope and source
  checked_at (3s clock-skew tolerance). Legacy v1 accepted with matching echoed
  call metadata+fresh boundaries; strict nonce remains without a turn boundary.
- Wrong/stale/prose payloads fail closed. Failed retry retains prior evidence but
  marks it historical/incomplete; loading/source/no-match/failure states explicit.
- Safe diagnostics, no customer values or secret dumps. Default OpenRouter model
  exactly openai/gpt-oss-20b; explicit env model overrides remain respected.
- Disable auxiliary title generation in template/existing sales config via atomic,
  private, idempotent migration. No provider account or approval flag changes.

Direct Haravan check, no AI:
New protected UI section takes model code+size, normal persisted rate limits,
existing PILOT_ACCESS_KEY. Gateway proxies only to fixed hermes-sales:8644/stock
using existing dedicated sales API key; Haravan/provider secrets stay in backend.
Typed stock scope only, same GET-only reader, no order/write/arbitrary URL/tool.
Port8644 NOT published to host/public. Server starts after startup audit, restores
MCP-written catalog cache on request, not a duplicate continuous sync worker.
No new env or secret. Model is not invoked or billed by this operation.

Verified:
203 tests pass. MCP2 stdio+pinned native serializer validate no-nonce v2 reports.
Chromium covers v2 reader/native serialization/client/WSGI/UI and direct-probe UI.
Real local HTTP validates probe auth/proxy; native OpenRouter SDK resolves chosen
model without inference. Synthetic HTTP case:20 variants, only Kem/Chì positive
beyond item12. ALL test quantities/model decisions are SYNTHETIC. No live Haravan,
paid model call or actual Docker build from Workspace. Not live acceptance.

One release procedure:
1. Owner reviews/merges release/haravan-sales-integrated only, not partial branches.
2. Coolify auto-deploy main; confirm finished for the new merge commit.
3. Refresh private page, connect using EXISTING pilot key. Open direct Haravan
   check, enter1514, select38. No model call. Compare stock with Haravan NOW.
4. New chat, same scope. Must show every verified choice. Kem/Chì should appear
   only if still in stock; no hardcoded colors/stock. Initial loading may require
   catalog warmup then one more direct check, not repeated paid chat requests.
5. Source/contract errors have explicit safe codes. Do not declare success from
   unit count/deployment finished alone. No public cutover until real checks pass.

Rollback through owner's Coolify/Git flow to pre-release main:
a05bab1524d5ad35c327ae1fe5fa19cdea35aaf0. No DB schema migration. Private sales-config
backups exist; title-disable persists until deliberately restored. Never publish
backup contents or credentials. No order creation or stock modification added.
