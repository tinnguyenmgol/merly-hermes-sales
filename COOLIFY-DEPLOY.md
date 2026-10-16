# NEW Hermes sales resource: approved but NOT deployed on Coolify

Dify pilot source was deleted by owner approval. No Dify service was installed.
Existing webchat and management Hermes stay unchanged.

## Verified in workspace
Source848fc0ad8be766b9dc10fe42bd80b5fc2d45d95c, checksum in HERMES-SOURCE.json.
Python3.14.8, editable install (upstream wheel build blocked), mcp/web extras plus
aiohttp3.14.3. Actual bootstrap/startup5-tool audit passed; API health/capabilities200.
No live model/customer data call. Runtime in workspace/tmp is NOT a managed deployment.

## Blocker
workspace_shell is isolated uid10001 for development/tests. No permitted Coolify
API/deployment tool or host access. Do not bypass with root/sudo/Docker socket.
Docker build, deployed volume persistence and live model have NOT been verified.

## Operator resource spec
Create NEW repository/branch/resource, not the old auto-deploy webchat main.
Source is locally Git-committed only: publish to a reviewed location without
triggering old webhook, then connect new resource to that source.
Use compose.hermes.json (JSON is valid Compose YAML), Dockerfile.hermes.
Image/source/digest pinned. Two new services, no Postgres/Redis/vector database.
Starting runtime budgets1GiB/1CPU and256MiB/0.5CPU, NOT load guarantees.
Measure startup/chat peak memory before public use; don't reduce current budgets.

Generate NEW MERLY_SALES_API_KEY>=32 random chars, fresh PILOT_ACCESS_KEY and
PILOT_SESSION_SECRET. No owner default key. Enter secrets in runtime, not chat/Git.
Gateway gets NO Haravan token. Read-only Haravan token only in isolated adapter.
Only three NEW named volumes. Audit volume read-only in gateway. No production DB,
owner home/auth/skills/memories, Telegram keys or host/Docker mounts.
Raw Hermes API has no host port. Gateway loopback8789 requires pilot authorization.
This is not the public widget. Proxy/auth/TLS/rate controls need separate review.

## Model and acceptance
Configure model/provider with dedicated runtime's own config/setup and credential.
Do not copy management Hermes auth directory. Workspace instance has no real model
credential; health200 does NOT mean it can answer. Global memory/profile injection,
multiplexing and tools other than merly stay off. Re-audit after config changes.
Approve data terms and model cost before *_APPROVED flags1; set provider budgets,
transcript retention/access/deletion and customer privacy notice.

Test real size->heel/corrections/promos, tool-grounded facts, session isolation,
images/links, denied mutations/injection, latency and costs. Metadata/promotion
publication still require approved real data. No automatic cutover. Route website
only after real acceptance. Rollback only new resources, never delete old volumes.
