# Protected internal chat pilot

Static login UI at /; JavaScript/CSS at fixed paths. API remains authenticated with
PILOT_ACCESS_KEY, not any Gemini/Haravan/management credential. No real credential
is embedded in assets. Pilot key stays only in JS memory, not URL/storage/cookie.
Only the pseudonymous chat token is a Secure/HttpOnly/SameSite=Strict cookie.
Public HTML is a login shell, not proof that the backend or Gemini is ready.

UI requires a secure browser context (HTTPS; localhost is allowed for development).
No external scripts, analytics, fonts or markup rendering; strict CSP, no frames.
Model text uses textContent. One outstanding message, no automatic inference retry.
Readiness GET checks approval flags and signed inventory/API, not model inference.
Consent checkbox warns about synthetic data and API cost. It does not replace the
three server-side approval flags. Failed calls may have consumed budget or cost.

Logout/new-chat removes the local session-to-response mapping and expires cookie.
It does NOT delete stored upstream Hermes conversations. No real customer data.
Every authenticated pilot operator shares the configured access key; this is NOT
production per-user account authorization. Keep trial URL/key restricted.

Deployment sequence (operator configuration; not performed by source publishing):
1. Merge reviewed UI branch. Verify new build before claiming a working page.
2. Use a dedicated TEST hostname; do not replace chat.merlyshoes.com. Proposed
   hermes-test.merlyshoes.com is only a suggestion, not a provisioned endpoint.
3. DNS points that hostname to owner's confirmed Coolify VPS103.245.237.65.
4. Coolify Domains: receiving service sales-gateway, protocol HTTPS, internal8080.
   Do not route to Hermes8643 or expose host port8789 publicly. Port8080 is an
   internal proxy target, not a port to append in the user's browser address.
5. Three approval flags stay0 by default. Operator must approve isolated internal
   testing/data handling/model costs before setting all3 to1 and applying env.
   Until then, UI can display login and why chat is blocked; no inference.
6. Open test URL, enter PILOT_ACCESS_KEY privately (never Gemini key), acknowledge
   synthetic-data/cost notice and send an explicit test question. Live Gemini,
   Haravan accuracy, latency and costs still need acceptance. No public cutover.

Verified:101 Python tests and actual Chromium mobile-viewport interactions against
real local WSGI gateway with explicitly synthetic audit/model fixtures. Browser
checks login rejection/acceptance, approvals/consent gates, context continuity,
two browser-context isolation, literal XSS text, no persistent secret, reset/logout,
no automatic retries and rejection of an insecure non-localhost origin. ZERO real
Gemini requests or production UI/DNS changes were made. Browser fixtures are not
provider quality evidence. verify_pilot_browser.py requires test-only Playwright;
no browser runtime/library is added to the deployed image.

The current MCP bridge reads only deployment/build logs, not private API/runtime
logs or DNS settings. Do not claim these configuration steps are automated.
