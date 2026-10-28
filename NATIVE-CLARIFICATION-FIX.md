# Native clarification — offline verified, live acceptance pending

## Evidence and limits
Live QA run `7d19f650df3ea1cf573b5b4df9dc5016` completed three HTTP 200
turns, but turns 2/3 returned unverified/partial-stock fallbacks, not useful
clarification or product recommendations. QA does not expose the hidden model
reply/tool trace; the log MCP returns 401. The exact production trigger is not
yet established from runtime logs.

Independent before/after execution against main
`83f9c9311629287676bd3147a05c9afa01383c93` reproduces two actual code defects:
- Folding **chị** (address) to `chi` wrongly triggers **chỉ** (exclusivity).
- An unsuccessful stock call erases a data-free native clarification; display
  projection then replaces it with the unverified-stock fallback.

## Scope
- Preserve Vietnamese address during evidence checks, retaining exclusivity
  and unsupported-price guards.
- Conservative OUTPUT-only question check. No customer-input routing, invented
  JSON envelope, fixed response script, new model or framework.
- Preserve qualifying native questions with needs_clarification, no stock cards
  or product links. Failed evidence remains in bounded internal diagnostics.
  Non-inventory tool failures retain their existing guard behavior.
- Missing required size explicitly asks for customer clarification in tool error
  metadata, with source_read_attempted=false. Invalid types stay schema errors.
- Prompt separates missing customer facts from missing source metadata and asks
  for useful next decisions instead of silently dropping criteria.
- UI suppresses the incomplete-lookup support note for a pending clarification.
  Stock truth, four-card cap, limits and secrets are unchanged.

## Verification
- Full suite: 737 passed, no skips. Standalone Compose is used for config checks
  only; no Docker daemon/socket or production access.
- Synthetic regressions cover useful questions after failure, Unicode address,
  false claims followed by a question mark, positive cards, unchanged input,
  delivered history, bounded logs, schema errors and non-inventory tool guards.
- Before/after adapter execution proves old fallback versus preserved native
  question. Public JavaScript is parsed with QuickJS.

This is NOT a real-model quality score. Output checks are conservative heuristics,
not a semantic proof of arbitrary prose. No catalog attributes were guessed and
no stock-source algorithm was changed.

## Acceptance gate
Not deployed. Requires owner-approved production rollout followed by live QA:
1. Missing size -> useful question, not stock fallback.
2. Follow-up/typo -> retain confirmed heel/color/occasion; do not re-ask size.
3. Positive stock -> at most four verified positive choices, diverse products.
4. Partial/zero/error -> truthful scope plus useful next action; no invented
   stock, silent criteria relaxation or repeated failed source requests.
5. Correction/unclear intent -> ask only what is actually missing.
Do not reset QA quotas. Production code, volume, DB and tokens are unchanged.

## Packaging follow-up after first rollout
Live run `dd011c028ff1749d9e07cbac472ce78c` failed on its first message:
HTTP 503, diagnostic `2b65c8eac3e8ca0c`, request_failed. No automatic retry.

The original fix omitted clarification.py from BOTH Dockerfile COPY lists and
from the .dockerignore allowlist. Repository tests could import the source file,
but assembled deployment files could not. This is a packaging error introduced
by this change, not evidence that the customer's wording is wrong.

New isolated-interpreter smoke tests assemble the runtime COPY files, honor the
build allowlist and prevent repository-path fallback. Before the packaging fix,
both image contexts fail the inclusion test; removing the helper reproduces
ModuleNotFoundError: No module named 'clarification'. After the fix, both staged
contexts execute an ordinary first AI answer and a missing-size clarification.
The entire suite now returns **741 passed**, no skips. These are copied-runtime
smoke tests with synthetic model outputs, NOT Docker image builds or live-model
acceptance. The deployed traceback is unavailable through the log MCP (401).

Rollout must include an actual image rebuild, not only restarting the old image.
Do not redeploy or reset QA to bypass retained failure cooldown/daily quotas.
Live acceptance remains pending rollout of the packaging fix.
