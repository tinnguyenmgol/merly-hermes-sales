# Direct stock resolution after a model-tool failure

Observed live evidence from owner: direct Haravan check renders variant/location
stock while chat produces a failed report. Exact original tool failure is still
not recovered from the screenshot; this patch does not invent that diagnosis.

The shared Haravan reader is not replaced. For a COMPLETED native model turn with
a failed/source-error/loading/no-match stock report, gateway extracts only the explicit current-turn business
scope from search_products(check_stock=true) calls, validates exact string model,
integer size, optional exact color and known criteria, then reuses the existing
fixed/private probe_stock service. No regex of customer messages, hardcoded color,
new provider call, extra env, new port or expanded write permissions.

Safety:
- Never coerce model ID/size, merge color names or ignore non-null heel/category/
  occasion or unknown fields. Null known optional filters mean no criterion in
  the independent direct request, NOT an auto-repaired MCP invocation.
- Keep exact scoped color; broad availability without a color reads all options.
- A later invalid request for the same scope blocks earlier usable candidates.
- At most ONE direct read for the entire turn. Usable complete/partial existing reports do
  not trigger it. Remaining total budget65s from turn start, at most30s probe,
  skip with less than5s left, no retry loop. No timeout increases.
- Fresh direct response must match the exact scope. Production probe validates
  full source contract/timestamp/coverage. The model's data is not substituted.
- Source partial remains partial; failed direct read stays failure. No stock or
  color is guaranteed before an actual validated response. No model/order call.
- Native turn failure/timeout has no completed intent contract and is NOT turned
  into a successful answer. Existing legacy CID/isolated session behavior remains.

Verified:218 tests pass. Actual Chromium case intentionally returns a failed model
stock tool output, then runs existing native client -> direct read fixture ->
gateway -> all20 cards. Unknown filters, wrong types, budget, bounded call count
and source failures tested. These sources are SYNTHETIC. Not claiming real model
or API proof after this patch, and no automatic deployment.

Owner merges fix/direct-stock-resolution; existing Coolify flow deploys it.
No new keys/env. Refresh and use NEW chat. Stock cards recovered this way say
"Kết quả đọc trực tiếp từ Haravan". Keep the direct probe as an independent
comparison. Names stay exactly as source: e.g. Kem and Trắng Kem are not aliases.
