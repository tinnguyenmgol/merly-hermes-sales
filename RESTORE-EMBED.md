# Restore existing Haravan embed tag

LIVE checks before change:
- https://merlyshoes.com/ ->200, Haravan storefront, IPv4 210.245.125.93.
- www redirects to main storefront ->200.
- https://chat.merlyshoes.com/ ->200, public Merly chat, IPv4 103.245.237.65.
- Main theme already has <script src="https://chat.merlyshoes.com/embed.js" defer>.
- That script URL returned401 application/json; public.js returned200. Missing
  legacy embed endpoint is a confirmed cutover compatibility failure. This does
  not claim every possible storefront/network issue was diagnosed.

Fix: serve /embed.js as public JavaScript in enabled public mode, using existing
Docker public-web copy. It mounts one shadow-DOM chat button, lazy-loads existing
public chat iframe on first open, closes/reopens without duplication, supports
Escape and preserves allowed-origin CSP/cookie/CSRF protections. No API key,
provider call, backend replica, new secret or DNS/theme edit. No innerHTML.

268 tests pass. Actual Chromium+WSGI loads the EXACT existing script tag (twice
to check singleton behavior) on a simulated merlyshoes.com page, opens widget,
submits a question, renders synthetic source options, closes/reopens. No live
Haravan/model requests; no live deployment by Workspace.

Owner merges fix/restore-public-embed; Coolify deploys same app. Refresh storefront
and verify /embed.js now200 application/javascript and button opens working chat.
Do not add a second iframe/snippet or change main-store DNS to fix this issue.
