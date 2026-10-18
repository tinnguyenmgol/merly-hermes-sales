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
