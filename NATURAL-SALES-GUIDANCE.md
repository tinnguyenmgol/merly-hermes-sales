# Native sales advice and a useful next action

Scope: managed instructions and examples, not fine-tuning or phrase routing.
Only SYSTEM-PROMPT.md changes runtime behavior. No changes to retrieval, stock
validation, customer display projection, model/provider or the five read-only
tools. No hard-coded closing sentence is appended by Python/JavaScript.

Guidance:
- After verified positive choices, briefly explain source-backed characteristics
  and invite a suitable next decision (choose/compare/view another option).
- Do not promise comfort, fit, urgency, discounts or extra available models without
  evidence. Do not push purchase into every FAQ or after a customer declines.
- Customer chooses: retain confirmed variant/quantity, ask only missing details;
  refresh current price/stock before confirming them. Historical cards are not
  a fresh inventory check.
- Current tools cannot create orders, reserve stock or contact staff. Offer the
  verified product link or an approved contact path; never claim an action ran.
- No premature phone/address collection, payment details or invented links.
- Examples contain no real price/SKU/stock and are explicitly tone examples,
  not factual knowledge or a mandatory response script.

Executed verification: 817 offline tests passed, no skips. Five new tests verify
instruction delivery to the native Responses payload, preservation of scripted
source-backed introductions/next-action language, and continued rejection of
unverified product links. Copied-runtime packaging checks remain included.
These are wiring/safety regressions, not proof the live model learned the tone.
No real inference call, production deployment or live QA was performed here.

After owner-approved merge/rebuild, live acceptance must check: verified product
gets concise advice + an appropriate invitation; buyer acceptance gets a real
purchase/contact path rather than a fake order; hesitation/FAQ/decline respects
intent; no unsupported claims or early PII request. An evidence-guard fallback
may still replace unsafe wording; it is intentionally not weakened for a CTA.
Alternative-product retrieval/exclusion is not implemented by this prompt change.
