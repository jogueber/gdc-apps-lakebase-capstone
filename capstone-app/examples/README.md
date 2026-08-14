# T3a — external partner API (M2M) examples

Client-side scripts that exercise `GET /api/external/customers/{id}` as a
partner **service principal** over the OAuth `client_credentials` grant.

- `_token.py` — mints the partner SP's OAuth bearer (SDK M2M flow).
- `m2m_test.py` — happy path: bearer → `GET {APP_URL}/api/external/customers/{id}`, expects `200` + the customer JSON.

## One-time workspace setup (admin)

The handler reads gold via the warehouse using the **caller's** bearer, so the
partner SP needs both app access and data reads:

1. **Create a partner SP** in the workspace (or reuse one).
2. **Mint an OAuth client-secret** for it:
   `databricks service-principal-secrets-proxy create <SP_ID>` → save `client_id` + `client_secret`.
3. **Grant `CAN_USE` on the app** to the SP (App → Permissions). Without it the proxy returns 401 even with a valid bearer.
4. **Grant data reads** to the SP: `CAN_USE` on the warehouse, `USE CATALOG` + `USE SCHEMA` on the gold catalog/schema, and `SELECT` on `gold.customers` + `gold.transactions`. Without these the warehouse query returns `INSUFFICIENT_PERMISSIONS`.

## Run

```bash
export DATABRICKS_HOST=https://fevm-test-jg.cloud.databricks.com
export APP_URL=https://customer360-dev-7474652647475090.aws.databricksapps.com
export DATABRICKS_CLIENT_ID=<partner-sp-client-id>
export DATABRICKS_CLIENT_SECRET=<partner-sp-client-secret>
export CUSTOMER_ID=C0000001            # optional

cd capstone-app/examples
uv run --with databricks-sdk python m2m_test.py
```

Expect `... -> 200` followed by the `CustomerDetail` JSON (`profile` +
`transactions`). The SQL audit log attributes the statement to the **partner
SP**, not the deploying user — confirming the OBO data path.
