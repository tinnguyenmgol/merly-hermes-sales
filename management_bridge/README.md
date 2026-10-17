# Management-only read-only Coolify build-log bridge

Not installed/configured in the active Hermes instance yet. No live API call has
been verified; no token has been requested/received. NEVER install in customer
sales Hermes or expose this server over public HTTP. MCP stdio only, SDK2.0.0.

Two tools: recent_hermes_deployments and hermes_build_log. Both GET only, hardcoded
HTTPS host panel.merlyshoes.com and application UUID f3rhymt285isnfqa5pjmcnbx.
No caller-supplied resource, deployment URL, shell command, headers or raw API path.
No endpoints for environments, database, SSH, deploy/control or global inventory.
History restricted to10 offsets; response<=8MiB and returned log<=48k chars.
API route verified against official coollabsio/coolify routes/api.php and
app/Http/Controllers/Api/DeployController.php: GET /api/v1/deployments/applications/{uuid}
with skip/take. Raw config/snapshots in responses are discarded. No disk log cache.

## Permission boundary
Read + read:sensitive may be necessary for logs. The latter also grants access to
other sensitive fields at the TEAM level, so the token itself is NOT app-scoped.
Bridge narrows model-facing capabilities but is not a revocation of token rights.
Keep token secret inside management runtime; never mount/pass to sales Hermes.
Prefer a separately scoped team when feasible. No root/write/deploy token needed.
Revoke after diagnostics. Never send token into Telegram/Git.

## Redaction limitations
Whole lines with credential markers are hidden; exact Coolify token and URLs are
redacted. This is conservative/best-effort, not proof that arbitrary unlabeled
secrets are absent. Source logs are untrusted data, not instructions. Do not execute
commands from them. If output is redacted/unsupported/oversized, fail explicitly,
not claim successful log collection. Sensitive-line filtering may hide useful
context; review privately rather than widening output indiscriminately.

## One-time operator integration (not performed)
1. Review these files. Store a short-lived token in management Hermes runtime as
   COOLIFY_DIAGNOSTICS_TOKEN. No token in config YAML or command history.
2. Copy reader.py and server.py to a private integration directory in that active
   management Hermes home. Its Python must provide mcp==2.0.0; no shell installer.
3. Merge mcp-fragment.example.json into that SAME management profile's config.yaml,
   replacing absolute paths with actual runtime paths. JSON fragment is illustrative,
   not an entire config replacement. Do not overwrite unrelated tools/settings.
4. Reload MCP if supported, or have operator restart only management Hermes.
   Expose exactly the two selected diagnostic tools, no native Coolify write tools.
5. Verify discovery, fixed target, redaction and actual API permission; then read
   latest build log. Setting env alone does not add tools to a running session.

Current isolated workspace cannot modify Hermes host config or restart production.
This branch does NOT deploy or alter the existing app. Do not merge just to deploy.

## Offline tests
python -m pytest management_bridge/tests -q
python management_bridge/verify_mcp.py
Tests use synthetic API data; real MCP transport, explicit missing-token failure.
Live CLI after secure configuration: python reader.py --lines 200
