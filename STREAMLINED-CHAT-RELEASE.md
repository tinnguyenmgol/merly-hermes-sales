# Streamlined public chat UI

Owner requested smaller launcher, then removal of visitor consent checkbox.
-48px black/white SVG launcher; touch-safe, desktop hover label, focus ring,
 reduced-motion/safe-area support, no duplicate widget/iframe/backend.
-White compact chat layout; no checkbox or hidden auto-checked control. Send
 enables after session ready and nonempty input; explicit submit still required.
-Notice after composer/send:AI may store history; no passwords/cards/sensitive
 data. Short footer retains live-price/stock/no-reservation/no-order caveats.
-New browser request is exactly {message}; no invented consent:true assertion.
 API accepts message-only. Legacy checked consent:true remains compatible for
 already-open old tabs; false/nonboolean flags still rejected. Extra fields,
 cross-origin, wrong CSRF/session and visitor/global limits remain guarded.
-Private backend, approval flags, credentials, model behavior and Haravan GET-only
 access unchanged. No claim that submitting proves statutory/privacy consent;
 operator remains responsible for lawful processing and applicable privacy notice.
-UTF8 script header avoids corrupt Vietnamese labels on hosts without charset.

Verified295 tests. Chromium desktop320/390/1440 width, touch mobile,48px geometry,
 contained panel, no sticky touch tooltip, accessible labels/Escape, source query,
 XSS-as-text and message-only network payload pass. Synthetic inventory/no paid
 inference. Existing public/operator security tests pass. Not live-deployed.

Merge feat/streamlined-public-chat and deploy same existing sales app, then reload
 storefront/chat. No theme, DNS, environment or key changes. Sales-policy01 work
 was paused separately; this branch does not include unfinished policy changes.
