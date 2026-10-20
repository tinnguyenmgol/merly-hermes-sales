> Historical design/API notes. For the integrated v2 release and deployment, see RELEASE-INTEGRATED.md; its behavior supersedes pending-work notes below.

# Stock-option sweep: staged fix, not live acceptance

Discovery previously returned up to12 variants/product and4 products by default;
quote_variant checked one variant per model call. Three tool rounds cannot cover
many colors, and the model's final prose may omit valid choices.

search_products(check_stock=true) requires exact model_code + confirmed size.
It uses all matching catalog candidates, refreshes each product from Haravan,
checks inventory in batches of10 IDs and returns every collected option. Discovery
keeps its limits but now declares truncation. Explicit color filters remain named
in the displayed scope. Unsupported heel/category/occasion constraints in stock
mode are rejected, not silently discarded. The same5 MCP tools remain read-only.

Coverage tracks products checked/unverified and variants found/checked/omitted.
Missing warehouse rows mean unknown, not zero. Positive partial inventory is a
known minimum; all-zero requires valid data for all3 configured locations.
Invalid/duplicate inventory makes that batch unknown. Product fetch failure does
not mean no stock. Limits20 products/100 variants and a soft15s next-request budget
are explicit; the last urllib request retains its12s timeout plus the MCP RPC
limit. Limits/errors/stale (>300s) index yield partial, never silently complete.
Completeness is relative to the catalog snapshot plus refreshed product details,
NOT an atomic all-Haravan/global-stock guarantee. Nothing reserves stock.

Gateway issues a fresh request ID per turn. Native Responses function_call/output
items are paired by call ID, tool name, request ID and matching scope. Only these
tool outputs can create cards; assistant prose cannot. Missing/truncated/stale-turn
reports produce an unverified warning. Counts, identities, warehouse totals and
links are validated. Multiple scopes remain separate. The gateway uses a
deterministic summary and browser renders ALL returned options, independently of
what colors the model mentions. Available, unknown and zero groups stay separate.
Links use the same live product ID/handle; suspicious handles are not rewritten by
guessing. No new keys/provider/approval flags/database migration are required.

Boundary: interpreting the natural-language request and choosing tools STILL
belongs to the model. If it never calls stock mode, there is no verified full
report. This patch cannot guarantee all free-form requests are understood. Real
acceptance MUST verify broad availability questions trigger stock mode, broadening
clears stale color filters, and the table matches Haravan. Prose/individual quotes
without a full table FAIL this case; do not launch publicly on that basis.

Offline fixtures:20 colors including Kem/Chì Bóng after entry12, >4 product records,
missing/partial inventory, batch failure, limits, duplicate rows and stale index.
All fixture prices/quantities are SYNTHETIC, not Merly's current inventory. Actual
MCP2+pinned Hermes serialization and real Chromium rendering are exercised. No
live Haravan/model requests were made from Workspace. After reviewed merge/deploy,
use a NEW conversation and compare staging with live Haravan at the same time.
