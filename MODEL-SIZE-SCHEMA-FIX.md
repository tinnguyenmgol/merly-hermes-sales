# Required model-visible size and argument-shape diagnostics

## Evidence
Owner logs 66580bd1096785b1 / 2c41e51a2f0db991 show repeated
needs_clarification, no stock report and later decode rejection. Current server
produces that business result when the structured size argument is absent.
Customer size was already supplied: this is not missing customer information,
nor evidence that no product/collection matches. These traces do not establish
that inventory/collection lookup was reached.
Old logs do not expose argument shapes or decoding reasons, so omission cannot
yet be attributed to the model versus runtime/provider argument handling.

## Concrete defect reproduced
Search schema declares size but required=[]. Actual pinned Hermes schema
conversion preserves that optionality. Earlier tests mostly supplied correct
arguments manually, not the schema instructing the model to include the field.

## Fix
- Require size in the model-visible schema. Unknown customer size -> ask before
  calling, never invent size. Backend clarification stays defensive compatibility.
- Startup audit validates actual model-visible size type/range/requiredness,
  not only five tool names; refuse stale/empty schema.
- Log only whitelisted argument field names and size shape enums, never values,
  text, IDs or credentials. Decode rejection adds fixed reason enums, not raw
  exceptions or tool output.
- No changes to inventory truth, collection/filter logic, models, dependencies,
  quotas, runtime framework or production configuration.

## Verified and pending
812 tests pass, no skips: pinned schema conversion, startup refusal, redacted
metadata, copied-runtime tests and all prior retrieval/stock regressions.
This is NOT proof of real-model argument accuracy. Owner-approved backend and
gateway rebuild plus live QA are still required. No QA quota reset/bypass.
