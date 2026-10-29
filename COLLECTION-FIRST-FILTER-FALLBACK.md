# Collection-first retrieval with catalog-filter fallback

Feature branch only; no production deployment or real Haravan query performed.

## Behavior
- Public customer search retains the stock-first/missing-size contract.
- For broad structured criteria, optionally read the public custom/smart
  collection index and prioritize one unambiguous group. Matching group names
  only ranks candidates; it does not establish product attributes or stock.
- Without a suitable group, with ambiguous groups, or on optional collection
  failure, apply the SAME filters to the full cached catalog. No guessed
  collection, no silently dropped heel/color/size/occasion condition.
- `collection_hint` is an optional preference, not a predicate. `collection`
  remains a required scope when the customer explicitly restricts to a group;
  a missing required group does NOT silently expand outside that request.
- Even with a hint, filter the complete catalog. Interleave candidate batches
  from inside/outside the group while preserving size/color match ranks, so a
  large poorly stocked group cannot take all early candidate slots.
- Fetch fresh product/variant data, require color AND size on the SAME variant,
  then read inventory. Customer display still caps at four verified-positive
  choices. Collection labels never supply missing heel metadata.
- API calls use existing fixed-host GET-only transport. Optional discovery has
  a two-second sub-budget inside the existing lookup deadline; collection index
  cache lasts 300 seconds. No API token -> skip automatic optional discovery.
  A returned 429 stops further Haravan requests for the turn, not a fallback
  retry around the rate limit. Other optional-group failures may use filters.
- Global catalog loading/stale state and bounded scan omissions keep their
  existing incomplete semantics. This cannot promise exhaustive results beyond
  the existing product/variant/time limits. No quota increase or bypass.

## Verification actually executed
Full suite: 797 passed, no skips, including isolated copied-runtime smoke tests.
23 new synthetic regressions cover optional/required groups, no group, ambiguous
or unavailable groups, zero-stock group with an outside match, exact variants,
missing metadata, hidden groups, rate limits, routing validation and bounded logs.

One controlled fixture contains 31 otherwise matching products, with the only
positive SKU at the end and inside the preferred group. Filter-only ordering
uses the 24-product candidate window without reaching it; collection preference
finds that SKU after one fresh product-detail read. This is a synthetic ordering
comparison, NOT a production latency/coverage benchmark or real shop stock.

Routing metadata records only fixed strategy/status enums and counts. Collection
names/customer text/IDs/credentials are not added to runtime diagnostic logs.

## Rollout and limits
All runtime changes are in files already included by both Dockerfiles and the
build allowlist. Owner-approved merge/rebuild of hermes-sales and sales-gateway
is still needed before live acceptance. No changes to technical Hermes or QA.
Actual Merly collection names, coverage and product attributes have NOT been
verified by this work. A group title is not a substitute for missing source data.
