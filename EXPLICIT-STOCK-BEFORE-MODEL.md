# Explicit stock query before the model — fixes the timeout dependency

Main was93358715bd75a6cdab28327bc34188f0599a0216 at preparation. This branch includes
prior direct-recovery commit f47e9aca32199cb73d6b2691c73e8720ffd090f2 AND this shortcut;
owner only needs this combined branch, not two separate merges.

Prior recovery waited for /responses to finish. An inference timeout meant the
scoped recovery code never ran. The screenshot's explicit request can be resolved
without that inference dependency.

Authenticated /api/chat, AFTER approval gates, existing lock and rate reservation:
- Narrow full-message grammar accepts one explicit model code, one shoe size35-43
  and a fixed stock question, e.g. "mẫu 1514 38 còn màu gì".
- Directly calls the existing authenticated Haravan stock service BEFORE chat/audit/
  model. Same source contract+freshness validation and full option display.
- Source service timeout remains30s; model timeout is NOT raised. No provider call
  on this route. A slow/unavailable Haravan can still fail, not invent inventory.
- Generic advice, foot measurements, negation, several models/sizes, color/heel/
  occasion constraints, ambiguous requests and malformed sizes stay on AI path.
  This is a narrow shortcut, NOT a general regex chatbot or complete NLU solution.
- SKU spelling/case/leading zeros preserved; no hardcoded product/color/quantity.
- Fast results do not fabricate Native response IDs or overwrite previous CID.
  Small in-memory per-session requested-scope hint bridges subsequent AI context:
  max128 entries,30min TTL, no stock quantities, no raw chat, no durable DB schema
  change. Reset/logout clears it. Ordinary greetings retain it; a new native
  commerce turn clears it; normal-turn failures clear stale hints. Current user
  message overrides prior scope, and unclear followups require clarification.

Verified:253 tests pass. WSGI test installs failing chat AND audit and confirms
exact screenshot query still returns source data without either being called.
Chromium test has model failure active, submits the exact phrase and renders all
20 synthetic options with no additional model call. Guard/identity/context/reset/
budget tests pass. Quantities/model behavior are SYNTHETIC, no live inference or
Haravan calls from Workspace; no Docker build performed here.

No new env, key, provider or permission; no production main push/deploy by agent.
Owner merges fix/explicit-stock-before-model, waits Coolify, refreshes private UI
and starts NEW conversation. Same phrase should say "Đã đọc Haravan trực tiếp,
không chờ AI" and show actual current API stock. Not claiming post-deploy live
acceptance until this is observed. Keep direct button for independent comparison.
