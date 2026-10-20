> Historical design/API notes. For the integrated v2 release and deployment, see RELEASE-INTEGRATED.md; its behavior supersedes pending-work notes below.

# Haravan documented variant reader — review/staging only

Official docs read directly (User-Agent retry after initial403):
https://docs.haravan.com/docs/omni-apis/product-variants/
https://docs.haravan.com/docs/omni-apis/products/
https://docs.haravan.com/docs/omni-apis/inventory-locations/

Contracts checked:
- Each product at most100 variants; dedicated variant list defaults50/page.
  Read limit/page plus products/{id}/variants/count.json. Top summary contains a
  conflicting count URL; detailed count section is used, no guessed fallback.
- variants/{id}.json is the single-variant read endpoint. Product detail ALSO
  embeds variants; using it was not itself proven incorrect by these docs.
- option1/2/3 are custom values: product options name+position identifies meaning.
  Numeric color must not become shoe size. Option value length may reach255.
- Existing inventory_locations route, variant_ids/location_ids and qty_available
  ARE correct. Do not substitute inventory_quantity or qty_onhand. Negative
  available balances are documented. Policy continue does not prove physical stock.

Changes:
- New haravan_variants.py checks count, all50-row pages up to100, parent identity,
  unique variant IDs and total count. Incomplete/changed counts fail explicitly.
- Stock sweep uses dedicated reader within its unchanged deadline. This adds
  count/page requests; latency/live completeness must be measured before rollout.
- Discovery/quote/stock size/color use product option metadata. Missing/ambiguous
  metadata stays unknown; missing size makes stock scope partial, not no matches.
- Returned color validation supports255 instead of128 characters.
- Client allowlist adds ONLY documented GET list/count/single variant routes.
  Fixed host/redirect block/secret env remain; orders and writes still prohibited.
- Both Docker contexts include helper/stock modules. Vendor manifest records the
  original upstream hash and explicit local override, not a false untouched copy.

Verified:177 tests pass, actual MCP+pinned Hermes serialization and Chromium pass.
New tests include pagination51/100, count mismatch, wrong product, duplicate IDs,
metadata positions reversed/ambiguous, unknown size,255-char option, deadlines and
allowed/forbidden routes. A full HTTP-shaped contract test runs real request
construction+JSON decoding+variant reader+stock grouping+report validation with20
variants and only Kem/Chì available beyond item12. Its HTTP bodies and quantities
are SYNTHETIC, NOT real Merly inventory. Existing fixtures now correctly model
count/list/page/product_id. No live model or Haravan requests were made.

NOT solved/NOT claimed:
- Exact production screenshot cause, credentials/scopes, real response shapes,
  live model behavior and latency are not verified.
- Legacy model nonce and report aggregation defects still require the separate
  orchestration redesign. Do not label this API-reader change a complete fix.
- Current application ID bounds are stricter than the documented64-bit product
  ID range. Full ID transport migration is separate; never normalize/truncate IDs.
- No order creation, stock mutation, key/env edits or deployment. Do not merge only
  because offline fixtures passed. Keep for reviewed staging+real API acceptance.
