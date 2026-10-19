# OpenRouter for isolated Merly SALES

Publishing this branch changes no production environment or management profile.
A reviewed merge triggers the existing Coolify auto-deployment.

## Owner: one new secret, no terminal
1. Coolify merly-hermes-sales app: add OPENROUTER_API_KEY with the real value.
   Runtime enabled, Build-time disabled, secret/masked. Save WITHOUT deploying yet.
   Never paste it into Telegram, Git, build arguments or screenshots.
2. Review/merge feat/openrouter-sales-runtime; let auto-deployment finish.
3. Open https://hermes-test.merlyshoes.com, start a NEW conversation and compare
   stock options against Haravan. OpenRouter account/key needs sufficient credit.

Defaults: provider=openrouter, base=https://openrouter.ai/api/v1,
api_mode=chat_completions, model=openai/gpt-4.1-mini. Public OpenRouter model catalog
was checked for this exact ID and tools/tool_choice support. Not a free-tier model;
no automatic random/free-model routing. Optional MERLY_OPENROUTER_MODEL changes
it to another explicitly selected tool-capable model. MERLY_SALES_PROVIDER should
stay unset/empty for key-only selection; explicit gemini keeps selecting Gemini.

## Startup and isolation
- With a key, migrate ONLY dedicated sales config from Gemini/blank/OpenRouter,
  preserving tools/safety/stock-report settings. Credentials remain in process
  environment, never YAML or backups. Existing config gets atomic mode0600 backup
  and readback-verified write. Restart is idempotent. Inline keys/unknown providers
  require review instead of being silently overwritten.
- Old GOOGLE_API_KEY/GEMINI_API_KEY/MERLY_GEMINI_MODEL do not override automatic
  OpenRouter selection. Remove old Google variables after successful testing.
- No key initially keeps old behavior; removing key AFTER migration fails closed
  instead of silently reverting to Gemini's exhausted quota.
- Gateway explicitly blanks provider keys even with Coolify's shared env_file;
  startup refuses any such key that nevertheless reaches gateway.
- No provider secret is committed, billing account created, or management config
  changed. No approval flags are automatically enabled.

## Verified / not verified
142 tests pass, including actual standalone Compose env-file precedence without a
Docker daemon. Pinned Hermes provider resolver and real OpenAI SDK client resolve
OpenRouter credentials/endpoint/chat-completions with network blocked. All keys in
these tests are synthetic. Paid inference remains UNVERIFIED until owner supplies
a real key. Existing read-only MCP tools and stock-option UI remain unchanged.
Reference: https://hermes-agent.nousresearch.com/docs/integrations/providers
