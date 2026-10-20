# One public Merly chat, reusing existing sales backend

New customer UI at chat.merlyshoes.com; no pilot-key login. One existing
hermes-sales + sales-gateway deployment; no extra pilot/backend replica. Old
legacy webchat service is not kept running after cutover. Git history remains
source control, not a second running app or local LLM consuming VPS RAM.

Security/limits:
- Public mode opt-in: MERLY_PUBLIC_CHAT_ENABLED=1, default0 preserves private mode.
- MERLY_PUBLIC_ORIGIN defaults exactly https://chat.merlyshoes.com.
- Visitor gets host-only Secure/HttpOnly/SameSite=Strict cookie + CSRF token.
  POST requires exact Origin, bound token and explicit consent. No private key
  reaches browser; server forwards to existing private logic using env credentials.
- Existing approval gates, source validation, literal pre-model lookup, fallback,
  context isolation, read-only Haravan and no-order behavior are unchanged.
- Four submissions/visitor/minute plus persistent GLOBAL6/min and100/day shared
  with operator. Conservative launch cap, not a promise of large-scale capacity.
  Bots can still consume public quota; no claim this replaces WAF/CAPTCHA.
- Customer notice says AI may process/store messages and asks no sensitive data.
  Current Native API history remains store=True; no false zero-retention claim.
- Only /api/public/session and /api/public/chat are anonymous. Private APIs and
  diagnostics still require operator key. /operator is same app's diagnostic UI,
  not an old chatbot service. No public arbitrary tool/URL or CORS wildcard.
- Public iframe allowed only on merlyshoes.com/www; operator remains unembeddable.

Verified:267 tests pass. Real Chromium+WSGI public session/cookie/CSRF, consent,
stock display without key/model, XSS literal rendering and iframe on simulated
Haravan origin pass. API/stock fixtures are SYNTHETIC. No live domain cutover,
Haravan theme edit or paid model call was performed by Workspace.

Owner-controlled cutover (tools here cannot write Coolify/production):
1. In existing merly-hermes-sales app save MERLY_PUBLIC_CHAT_ENABLED=1 (runtime).
   Keep current dedicated secrets/flags. No new key. Origin stays chat domain.
2. Remove chat.merlyshoes.com from OLD webchat app, stop that old app, and assign
   https://chat.merlyshoes.com to existing sales-gateway, port8080. Do not move
   Haravan main store or management domain. Merge release/public-merly-chat and
   deploy existing app. Avoid two resources claiming same FQDN.
3. Verify new page has no key input, consent and actual product/stock lookup.
   Confirm live approved-origin iframe before main-site activation.
4. Old app can be removed after cutover verified; clean only unused images/build
   cache through Coolify. Do NOT delete shared DB, management container, secrets,
   Docker volumes or either required management/sales Hermes without identifying
   dependencies. No root/SSH/Docker socket/prune-all commands.
5. Add integrations/haravan-chat-widget.html ONCE before </body> in active Haravan
   theme when public chat is live. This file contains no key. It reuses the same
   chat/backend; theme CSP may need owner-approved frame permission.

Cleanup actually completed:81 obsolete Workspace pytest-output/duplicate browser
folders removed,454012364 logical bytes (~433MiB); current Chromium/native SDK
and code kept. Workspace tmp went from2.8G to2.4G. This is NOT a claim of deleting
VPS production containers/images or freeing VPS RAM; that requires Coolify access.
Monitor snapshot seen15:10+07 showed disk39.1%,43.9GB free, RAM58.1%, swap1344MB;
these are snapshot values, not a new live measurement or reason to delete databases.
