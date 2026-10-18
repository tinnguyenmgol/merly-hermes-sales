# Gateway Haravan isolation under Coolify

The gateway must not serve requests while holding a Haravan token. Keep the
run_sales.py fail-closed startup guard. Backend token mapping is unchanged.

Coolify applicationParser has a compatibility branch: when a service environment
value is a literal empty string, an existing nonempty application DB env value for
the same key can replace it. Therefore `HARAVAN_ACCESS_TOKEN: ""` is insufficient.
Reference inspected: coollabsio/coolify v4.x bootstrap/helpers/parsers.php,
applicationParser, `elseif ($value === '')` / `Empty string - allow database override`.
The exact installed Coolify version/rendered deployment has not been inspected.

Gateway uses `HARAVAN_ACCESS_TOKEN: "${MERLY_GATEWAY_HARAVAN_EMPTY:-}"` instead.
The raw Compose value is nonempty, so that compatibility branch does not replace
it with the Haravan token. Docker Compose later resolves this reserved, normally
unset variable to an empty value. No new secret is needed. Keep
MERLY_GATEWAY_HARAVAN_EMPTY unset or empty; if misconfigured as nonempty, the
existing startup guard still rejects it. Do not put a token in that variable.

Do not use `${HARAVAN_ACCESS_TOKEN:+}` here: although Docker Compose supports it,
the inspected Coolify helper recognizes only :-, -, :?, ? while creating DB vars.
Do not rely on null either: Compose may resolve passthrough keys from its env.

Regression tests model the relevant Coolify DB override and render with a real,
checksum-verified standalone Compose binary using `config --format json` only.
They do not access a Docker daemon or execute the complete Coolify PHP application.
All token-looking test values are explicitly synthetic. Runtime API/model tests
and verification of the final Coolify-created container remain required.

Scope: this masks Haravan for the gateway; it is not proof that no other global
platform secrets reach that service. Broader credential isolation needs a separate
audit/deployment boundary, not disabling this guard.

## Consolidated runtime fixes after deeper review

The same branch also forwards HARAVAN_ACCESS_TOKEN and CATALOG_CACHE_PATH explicitly
ONLY to the Merly MCP child. Hermes otherwise filters them out of subprocess env.
No management provider/auth directory is copied. An isolated real child probe
verified both required envs arrive and an unrelated synthetic owner secret does not.

run_sales.py now applies a narrow, idempotent migration for existing sales-home
volumes BEFORE startup audit. It validates the isolated-sales config, adds only
those two env references, creates a private timestamped backup and atomically
replaces config.yaml. Model/provider and other settings are preserved. Unexpected
child env keys/literal values fail closed rather than overwrite operator choices.
There is no volume deletion/reset or automatic approval of cost/customer-data flags.

Client no longer injects an undeclared `merly-sales` model name by default: absent
HERMES_SALES_MODEL_ALIAS means omit model and use server configuration. An explicit
operator model value is preserved. .env.example defaults to blank. Current Compose
does not forward that optional override explicitly; changing gateway model selection
through Coolify still requires reviewed per-service config. No real provider is
chosen, copied from management, billed or claimed working by these code changes.

Verification: full 78-test suite on Python 3.14.8 with actual Compose CLI enabled;
existing-volume -> actual Hermes config interpolation/env filter -> real child probe.
Existing gateway Gunicorn smoke verified 401 without auth / 200 with synthetic auth.
No production runtime, real Haravan request or model inference was verified here.
After deployment, require gateway stability, credential-scoped Haravan access,
server model/provider readiness and approved real conversation before any public UI.
