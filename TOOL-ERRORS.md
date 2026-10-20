# Actionable read-only tool validation errors

The production log showed two search_products invalid_arguments errors but omitted
which validation failed. The exact original bad field is NOT recoverable from that
log; no claim is made that size, nonce, or optional filters were the actual cause.

This fix returns a bounded static reason, known field types, the existing input
schema and conditional stock requirements to the model. It explicitly tells the
model to correct arguments, omit unused optional fields, avoid repeating the same
failed call, and never interpret validation failure as zero stock. Unknown field
names, customer values, IDs, nonce values and arbitrary exception text are never
included in diagnostics. MCP stderr logs only the tool allowlist name, reason and
known field types. Existing validation remains strict: no coercion, dropped filters,
changed identifiers, guessed inventory, new tool permissions, or larger budgets.

146 offline tests pass. Actual MCP2+pinned Hermes serialization proves invalid-size
fixture feedback reaches the model-facing wrapper; a manually corrected subsequent
fixture call returns all20 options. This is protocol verification, NOT proof the
live gpt-oss-20b model will self-correct or finish within the existing time budget.
No real model/Haravan requests were made. Model/provider/key/approval flags unchanged.

After reviewed merge and deploy, use a NEW conversation and ONE real test. If it
still fails, diagnostics should identify the validation reason and field types
without asking for customer messages, key screenshots, or full argument dumps.
