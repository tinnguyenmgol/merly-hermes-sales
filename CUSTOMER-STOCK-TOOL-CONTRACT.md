# Customer selection tool contract — offline verified, not deployed

## Runtime evidence
Owner-provided logs for 26aca8f1a0aaf249 and eeaaf5032cc05499 show repeated
search_products results with decode=ok, source_status=ok and has_stock_report=false.
lookup_diagnostics is empty; unverified_product_listing triggers the guard.
Thus this trace supplies catalog candidates, not verified inventory evidence.
The guard must not be weakened to display those candidates. The log does not
contain argument values, and cannot prove the exact filters chosen by the model.

The old public MCP allowed optional check_stock to default to catalog browsing,
but customer display policy required verified positive variants. Prompt advice
alone did not close that mismatch. Synthetic before/after execution reproduces
catalog-only output from the old default and fresh stock from the new public
entrypoint using identical structured size/model arguments.

## Contract change, not a phrase-specific dialogue script
- Public MCP search_products: no confirmed size -> successful business outcome
  needs_clarification, missing_fields=['size'], no candidates or source read for
  that call. This is not an invalid schema call or source outage.
- Confirmed size -> fresh stock by default; omitted check_stock means true.
  Explicit false is rejected, not silently normalized. Input types/IDs are not
  coerced; all supplied filters are preserved.
- Internal catalog candidate retrieval remains unchanged and private to stock
  discovery; it does not recurse into the public stock policy.
- Tool schema, instructions, native trace validation and report extraction use
  the same default. A stock report from an omitted flag is still validated for
  correlation, scope and time. Missing output stays unverified.
- Clarification payloads have an exact validated business shape and cannot carry
  cards, arbitrary extra fields or a report disguised as clarification.
- Native prose remains native. No JSON final envelope, customer-language router,
  new model, additional tools, expanded resource budgets or disabled guards.

## Executed verification
774 tests pass, no skips. Includes both copied-runtime smoke tests and 33 new
contract regressions. Actual MCP result types, pinned Hermes result rendering
and Responses output extraction are exercised with synthetic sources/answers.
This is NOT inference or a Docker image build. Existing catalog-history fixture
now deliberately uses the internal catalog API to retain the no-unverified-card
regression; missing-size tests expect a business result rather than an error.
No live acceptance is claimed. No QA quota has been reset or bypassed.

## Rollout/acceptance
Owner-approved merge followed by image rebuild/redeploy of BOTH hermes-sales and
sales-gateway, not restart of an old image. Technical Hermes/QA need no changes.
Then live QA must show missing size -> useful question, confirmed size -> actual
stock_report/lookup diagnostics, <=4 verified positive choices or an honest,
useful next action. Respect remaining daily QA quota and failure cooldown.
