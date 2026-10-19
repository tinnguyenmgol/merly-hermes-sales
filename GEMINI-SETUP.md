# Dedicated sales Gemini setup (not management Hermes)

This branch does NOT deploy or enter credentials. Keep existing webchat unchanged.

1. Merge, then verify Coolify built that commit BEFORE adding a model key. Gateway
   masks must exist first: platform runtime env can reach every Compose service.
2. In sales runtime secrets enter ONE key, preferably GEMINI_API_KEY. Disable
   build-time use. Never send key values into Telegram, Git or screenshots.
3. Set MERLY_GEMINI_MODEL to an explicit text/tool-use Gemini ID available to that
   account. Example candidate gemini-3.8-flash appears in the official
   https://ai.google.dev/gemini-api/docs/models page inspected during development.
   Account access, pricing and actual inference have NOT been verified.
4. Apply env in a fresh deployment. Startup writes provider gemini and that model
   in the existing sales volume, with a private backup and unchanged other settings.
   Conflicting existing provider/inline key, missing key, key whitespace or differing
   Google/Gemini keys fail closed. No credentials are written to the model config.
5. The three isolation/data/cost approval flags are NOT automatically enabled.
   Keep at0 until the operator approves internal testing/readiness. No public
   domain or customer launch at this stage.

Gateway model keys resolve empty and startup refuses any nonempty model key.
The blank MERLY_GATEWAY_PROVIDER_EMPTY placeholder is NOT a secret; keep unset.
It avoids Coolify's DB override for literal empty values. Merly MCP gets only the
explicit Haravan/cache env, not Gemini keys under inspected Hermes filtering.
No management auth directory is copied. A separate sales key/project is preferable.

Verification:90 tests on Python3.14.8, real standalone Compose rendering, actual
Hermes config/provider selection and no model keys in Merly subprocess env.
Only synthetic credentials; zero Google API/inference calls. No live account,
reply quality, latency or cost acceptance is claimed.

Current admin bridge reads deployment/build logs, NOT runtime logs/Terminal/private
sales API. Build success is not live readiness. Inference needs an approved channel.
