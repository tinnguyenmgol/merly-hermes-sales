# General criteria-to-live-inventory backend

No natural-language question matching in product_discovery.py. Existing model
emits structured search_products arguments; check_stock=true + confirmed size
now supports model_code optional and all color/heel/category/occasion criteria.
Known model+size without extra specs retains legacy reader. No fake model IDs.

Shared algorithm:search catalog for candidates ->GET fresh product ->revalidate
all specs/model identity ->read ALL variants via documented count/pagination ->
filter exact size/color ->batch inventory_locations GETs ->typed per-variant
results. Never drop a hard criterion to make a query succeed. No orders/writes,
new model/extra classifier, credential or AI budget changes. Catalog-only search
still exists; default direct shopping now uses this inventory workflow.

Color comparisons now exact accent/case-normalized labels, not substring:
Kem !=Trang Kem; generic color families need clarification/explicit mapping.
Known source fields/title or approved enrichment provide specs; not LLM guesses.
Missing attributes !=no matches; no matching variant !=verified zero; absent
warehouse row !=zero. Positive partial inventory retained; one failed product
leaves other verified rows intact. Failed/unverified candidates remain marked
as such with public link; changed/nonmatching variants not presented as fit.

Budget:up to4 candidates,40 selected variants,batches10,15s attempt deadline;
a GET already in flight may add up to12s existing transport timeout. Omitted
products/variants + unknown metadata disclosed, never claim whole-shop coverage.
Inventory is never cached. No automatic request replay or quota reset.

New merly-product-discovery-v1 provenance schema binds complete business criteria,
operation ID, current-turn timestamp, unique IDs, parent/spec/size/color/link,
warehouse consistency, prices and coverage. Shared row validator also preserves
old report safeguards. Different criteria do not collapse to same model-less
report. Model-response recovery cannot narrow a failed filter query to plain SKU.

Same five fixed MCP tools. /discover is authenticated fixed internal endpoint,
no arbitrary URL/tool; gateway only has dedicated internal API key, no Haravan or
provider token. Public/operator render titles/links safely and distinguish partial
results. Generic size inferred from foot length still needs confirmation first.

376 tests pass:24 new discovery cases with varying heights/sizes/colors, missing
metadata, changed products, complete zero vs unknown, partial warehouses, product
failure isolation, pagination after12 variants, bounded omissions, stale/mixed
report rejection, real internal HTTP, MCP/Responses-adapter integration. Stock
and model transport synthetic; NOT live Haravan stock or real model accuracy.
Chromium public/widget/context/XSS regression passes. No paid inference or
production deployment by Workspace. One long combined verification SSH command
timed out; split test/browser runs completed and verified separately.

Merge feat/criteria-to-live-inventory and redeploy BOTH existing sales services.
No DNS/theme/key/env changes. Confirm real supported product criteria and live
latency within approved budget after deployment; no100 concurrent AI/stock SLA.
