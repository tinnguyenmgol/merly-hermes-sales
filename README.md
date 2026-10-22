> Tìm tên/loại/nhóm và ảnh nhỏ: [CATALOG-SEARCH-IMAGES.md](CATALOG-SEARCH-IMAGES.md). Bản nhánh riêng, chưa deploy.

> Bản refactor hội thoại: xem [HERMES-LED-DIALOGUE.md](HERMES-LED-DIALOGUE.md). Chưa nghiệm thu model thật; không tự deploy.

# Merly Hermes sales pilot — no production cutover

## Status / architecture
Gateway -> dedicated Hermes Responses API -> five read-only MCP tools -> Haravan.
Actual MCP2 SDK roundtrip and a pinned real Hermes runtime are now installed/tested
in the workspace. A dedicated local listener is bootstrapped for development only.
No live model/customer/provider call or production config change. Do not substitute
the owner's current API server. Dify local pilot was deleted by explicit owner approval.

Python here is transport and tools, NOT a rule-based conversational engine.
Hermes owns free-form dialogue and tool/context history via previous_response_id.
Customers cannot choose other response IDs. Gateway derives opaque session keys,
strips reasoning/commentary and treats failed/cancelled turns as errors.

## Files
mcp_server.py: real MCP2 stdio with exactly five read-only annotated tools.
merly_tools.py/vendor: typed catalogue, live quote, size, policy, promo data.
hermes_client.py/sales_gateway.py/state.py: API transport/per-customer chaining.
hermes-config.template.json: NEW isolated-home settings, not applied anywhere.
audit_instance.py/safety.py: actual startup schema check + signed inventory;
API capability/toolset discovery additionally rejects broad enabled toolsets.
SYSTEM-PROMPT.md/acceptance.json/evaluate_live.py: guidance and quality cases.

## Dedicated sales runtime: operator action, not performed
Use a separate Hermes instance/container/home with empty private working directory.
Never edit/mount default Hermes home, owner memories/skills/plugins, production DB,
root filesystem, Docker socket, Telegram credentials or SSH keys. No root/sudo.
Own API key, only necessary model credentials, only Merly MCP. OS/network/container
restrictions are necessary: a profile/prompt/signed inventory alone is NOT a sandbox.
No memory/session_search/files/shell/browser/delegation/admin tools for customers.

Template is for a NEW instance. Configure actual model/provider separately; no
model is guessed or billing enabled. Global memory and user-profile injection are
disabled; Responses history still provides per-conversation memory. Project skills,
external skills/plugins and tool-search bridge are off. MCP merly command/args use
MERLY_MCP_PYTHON/MERLY_MCP_SCRIPT: dedicated Python and absolute adapter script path.
Adapter requires tested mcp==2.0.0. Only adapter requires Haravan credentials.
Runtime import paths may vary by version; fail closed rather than expand rights.

## Startup audit / gateway
Run audit_instance.py INSIDE the dedicated Hermes install under its HERMES_HOME.
It requires actual model_tools/MCP discovery, verifies raw AND model-visible
schema names, memory flags and allowlist; no model call. API_SERVER_KEY signs
inventory at HERMES_SALES_ATTESTATION; read-only mount into pilot gateway with
matching HERMES_SALES_API_KEY. Startup audit has now passed against the installed pinned Hermes runtime in workspace.

Gateway checks /v1/capabilities and /v1/toolsets too. Discovery can omit MCP rows,
so signed startup inventory is required. Expires24h: renew and re-audit on config
changes. Snapshot is not continuous attestation or OS sandbox. Keep instance
configuration fixed while serving. Wrong/missing audit or extra enabled toolsets
blocks requests. No admin/default API key or frontend-exposed provider secret.
Approval flags default0: separately approve isolation/data/cost before live calls.

## Limits / data
One gateway worker. Persisted6 calls/min,100/rolling24h; NOT a money/iteration cap.
Template limits actual agent4 turns/40s; configure provider budgets separately.
Gateway45s timeout/no retry does not guarantee remote cancellation. API discovery
adds latency; no speed claim. Missing/evicted response chains are errors, never
silent attachment to another customer's history. Only final text reaches client.

Owner-approved size35–43 included; policies/promotions remain unapproved. Need
verified heel/category/occasion metadata. Missing data is not proof of no stock or
no promotions. No silent constraint dropping. Model/provider terms and retention
must be reviewed: Hermes Responses stores transcripts/tool results. Mapping TTL
is NOT deletion of remote history. Old SQLite logs/data are not migrated.
No new marketing dashboard or automatic learning.

## Verify
python -m pytest -q --basetemp=/workspace/tmp/pytest-merly-hermes
python verify_mcp.py
Real MCP2 subprocess initialize/list/call. Actual approved chart, no live stock/model.
python verify_http.py
Real HTTP with explicitly SYNTHETIC Hermes endpoint/inventory fixture. Contract
proof only, not actual runtime/tool-isolation or model-quality acceptance.
python evaluate_live.py --case size-to-heel
Dry-run, no inference.
python evaluate_live.py --live --case size-to-heel --gateway https://PILOT_GATEWAY
Requires live configured dedicated instance, startup audit and all approvals;
captures ACTUAL replies for human review. Respect6/min budget. No credential in chat.

## Owner approval update
Owner approved a new Hermes instance and unconditional deletion of local Dify pilot.
/workspace/merly-dify-pilot was deleted and absence verified; production webchat and
owner Hermes remain untouched. No Dify stack/production volume was present or removed.
New Hermes currently runs only in isolated workspace, NOT as a Coolify application.
Coolify API URL/token/tools are unavailable here; deployment bundle is prepared but
cannot be applied from this sandbox. Do not bypass this with SSH/root/Docker socket.
Actual live model, final website integration and sales acceptance remain untested.

References:
https://hermes-agent.nousresearch.com/docs/user-guide/features/api-server
https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp
