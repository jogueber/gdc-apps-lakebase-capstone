# Capstone review guide — Customer 360 on Databricks Apps + Lakebase

A reviewer's map of what was built, where it lives, how to verify it, and the
one task that is outstanding. Task spec: [`capstone-app/CAPSTONE_TASKS.md`](capstone-app/CAPSTONE_TASKS.md).

## At a glance

| | |
|---|---|
| **Live app** | https://customer360-dev-7474652647475090.aws.databricksapps.com |
| **Repo** | https://github.com/jogueber/gdc-apps-lakebase-capstone |
| **Deploy model** | DABs **git-source app**, `prod` target, pulls `capstone-app/app` from branch `main` |
| **Deployed commit** | `b10b66a` (matches `main` HEAD; verified via `databricks apps get`) |
| **Workspace** | `fevm-test-jg.cloud.databricks.com` |
| **Stack** | FastAPI + psycopg + Databricks SDK (Python 3.11, uv) · React + Vite + TypeScript + TanStack Query |
| **Forward-ETL pattern** | Pattern A — psycopg + `MERGE INTO` Delta (pull, on-demand) |

**Status: all 13 tasks implemented.** T3a's external M2M endpoint + scripts are
in place; only its *live* verification (partner-SP grants + a real `m2m_test.py`
run) remains — see [T3a: live verification pending](#t3a-live-verification-pending).
Note also the **T4 dashboard deviation** below.

## Where things live

```
capstone-app/app/
  app.yaml                       # T6 — runtime config, OBO scopes, OTel wrapper
  backend/
    auth.py                      # T2 — obo_client() / sp_client()
    db.py                        # T2 — lakebase_sp() async pool, token rotation
    config.py, deps.py           # pydantic-settings, FastAPI DI
    models.py                    # Pydantic response models (T3/T3a/T4/T5/T7)
    logging_config.py            # JSON log formatter + request_id ContextVar
    main.py                      # app assembly, GZip, request-id + Cache-Control mw
    routers/
      customers.py               # T3 — list/detail/metrics + notes/segment writes
      external.py                # T3a — GET /api/external/customers/{id} (M2M, OBO→gold)
      dashboard.py               # T4 — /api/config + /api/dashboard/analytics
      genie.py                   # T5 — conversation OBO endpoints
      jobs.py                    # T7 — run-forward-etl + run polling
    static/                      # committed built SPA (git-source runtime serves this)
    tests/                       # pytest (incl. offline test_external.py)
  frontend/src/
    pages/  Customers · CustomerDetail · Dashboard · Reports
    components/ GenieWidget (floating) · AppShell · charts · Gauge · …
capstone-app/examples/           # T3a — _token.py, m2m_test.py, README (M2M flow)
capstone-app/lakebase/
  reverse_etl/                   # T1 — synced + staging table DDL, SP grants
  forward_etl/pattern_a_psycopg2/drain_staging.py   # T7 job
  ops/  t9a_branch_pitr.py · t9b_query_insights.py  # T9
capstone-app/docs/
  optimizations-writeup.md       # Optimizations & hygiene
  t9-lakebase-ops-writeup.md     # T9 results + screenshots (docs/img/)

resources/app.yml                # T8 — git-source app resource, resource bindings
resources/jobs.yml               # T8 — forward-ETL job
databricks.yml                   # T8 — bundle root, dev/prod targets, variables
docs/superpowers/                # per-task design specs + implementation plans
```

## Task-by-task status

| Task | Status | Evidence / where to look |
|---|---|---|
| **T1** Reverse ETL: synced + staging | ✅ | `lakebase/reverse_etl/` — `create_synced_tables.py` (customers/transactions CONTINUOUS, products TRIGGERED), `create_staging_tables.py`, `grant_app_sp.py` (SP grants + `ALTER DEFAULT PRIVILEGES`) |
| **T2** Auth: OBO + SP | ✅ | `backend/auth.py` (`obo_client`/`sp_client`), `backend/db.py` (`lakebase_sp` pool, per-checkout token). Integration tests in `app/tests/`. OBO pinned `auth_type=pat` to avoid oauth+pat conflict |
| **T3** App APIs + React UI | ✅ | `routers/customers.py` — keyset pagination (`_encode/_decode_cursor`, `page_size` cap), notes + `customer_audit_log` in one txn, segment `ON CONFLICT … DO UPDATE` (idempotent). UI: `Customers.tsx`, `CustomerDetail.tsx` (parallel tab fetches) |
| **T3a** External M2M API | ✅ code · ⏳ live verify | `routers/external.py` (`/api/external/customers/{id}`, reads gold via caller's OBO bearer — never Lakebase/SP), `examples/_token.py` + `m2m_test.py`, offline `tests/test_external.py`. Live 200 pending partner-SP grants — see [below](#t3a-live-verification-pending) |
| **T4** Dashboard | ⚠️ **Done, different approach** | See [T4 deviation](#t4-dashboard-deviation). `/api/config` returns `dashboard_id`; UI renders a native Recharts cockpit, not the iframe embed |
| **T5** Genie chat | ✅ | `routers/genie.py` (start/create/get, OBO, poll loop). `components/GenieWidget.tsx` — floating bottom-right panel with enlarge + open-in-workspace |
| **T6** `app.yaml` | ✅ | `app/app.yaml` — env wiring, `FORWARD_ETL_JOB_ID` via `valueFrom`, OBO scopes `sql` + `dashboards.genie`, `opentelemetry-instrument` wrapper |
| **T7** Forward ETL (Pattern A) | ✅ | `lakebase/forward_etl/pattern_a_psycopg2/drain_staging.py` (pg8000 on serverless, `processed=false` filter → MERGE → mark processed). `routers/jobs.py`, `Reports.tsx`. Job in `resources/jobs.yml` |
| **T8** DABs git-source deploy | ✅ **Verified live** | `databricks.yml` + `resources/app.yml`. `bundle validate/deploy/run --target prod` all pass; app source shows git repo + branch `main`, resolved commit `b10b66a` |
| **T9** Lakebase ops | ✅ | `lakebase/ops/` + `docs/t9-lakebase-ops-writeup.md`. Screenshots in `docs/img/`. See [numbers below](#t9-results) |
| **Optimizations & hygiene** | ✅ | `docs/optimizations-writeup.md`. See [summary below](#optimizations--hygiene) |

### T9 results

- **Branching + PITR (T9a):** child branch created from `capstone-pg`;
  `DELETE FROM customer_notes_staging` on the branch (→ 0 rows) left
  `production` untouched at **8 rows** (isolation). PITR restore recovered all
  **8 rows** (`img/t9a-branch-creation.png`, `img/t9a-post-restore-count.png`).
- **Query insights (T9b):** 200k-row `customer_audit_log`, target predicate
  matches 200 rows. **p95 76.02 ms → 36.40 ms** after
  `CREATE INDEX … (actor_email)` (Seq Scan → Bitmap Index Scan; server-side
  mean 1.06 ms over 100 calls). Screenshots `img/t9b-before.png` / `-after.png`.

### Optimizations & hygiene

Keyset (cursor) pagination on the customer list; server-side `TTLCache`
(config/segments/products, 5 min) + `Cache-Control` on idempotent GETs +
per-key TanStack Query `staleTime`; `psycopg_pool.AsyncConnectionPool` with
per-checkout Lakebase token; `React.lazy` route splitting, memoized rows,
debounced filters, parallel detail fetches; `GZipMiddleware`, explicit column
lists (no `SELECT *`), Pydantic response models, outbound timeouts;
OpenTelemetry auto-instrumentation via `app.yaml` + `X-Request-Id` on spans.
Full detail: [`capstone-app/docs/optimizations-writeup.md`](capstone-app/docs/optimizations-writeup.md).

## T4 dashboard deviation

T4 as written asks for an **iframe embed** of the provisioned AI/BI dashboard
(`${host}/embed/dashboardsv3/${dashboard_id}`). This app instead ships a
**native analytics cockpit**: `GET /api/dashboard/analytics` recomputes five
aggregates against gold via the SQL warehouse (OBO) and `Dashboard.tsx`
renders them with Recharts. `GET /api/config` still returns
`{ databricks_host, dashboard_id }`, so switching to the iframe embed is a
small front-end change if the reviewer requires the literal embed. The
functional intent — broader in-app analytics without leaving the tool — is
met; the integration mechanism differs.

## T3a: live verification pending

The external M2M API is **implemented**: `routers/external.py` exposes
`GET /api/external/customers/{id}`, reading gold (`customers` + last 20
`transactions`) via the SQL warehouse using the **caller's** OBO bearer — never
Lakebase, never the app SP — and returning the same `CustomerDetail` shape.
`examples/_token.py` + `m2m_test.py` drive the client-side `client_credentials`
flow, and the offline `tests/test_external.py` (mocked warehouse) asserts the
shape + 404 path.

What remains is **live verification**, which needs workspace-admin actions I
can't perform without credentials:

1. Create a **separate partner SP** and mint its OAuth client-secret.
2. Grant it `CAN_USE` on the app, and warehouse `CAN_USE` + `USE CATALOG` /
   `USE SCHEMA` / `SELECT` on `gold.customers` + `gold.transactions`.
3. Run `examples/m2m_test.py` (steps in `capstone-app/examples/README.md`),
   confirm a `200` + customer JSON, and confirm the SQL audit log attributes
   the statement to the partner SP.

Give me the partner-SP creds once grants are in place and I'll run the live
test and capture stdout.

## JSON logging

App logging now emits **one JSON object per line** (`timestamp, level, logger,
message`, plus `request_id` and `exception` when present) via a stdlib
`JsonFormatter` on the root logger — so app and uvicorn logs are both
structured. `backend/logging_config.py` also owns a `request_id` `ContextVar`
that the request-id middleware sets, so each log line carries the same
`X-Request-Id` already stamped on its OTel span — one key ties a log line to its
trace.

## How to verify

**Deploy (git-source, prod):**
```bash
databricks bundle validate --target prod --profile fevm-test-jg
databricks bundle deploy   --target prod --profile fevm-test-jg
databricks bundle run customer360 --target prod --profile fevm-test-jg
# then confirm the resolved commit:
databricks apps get customer360-dev --profile fevm-test-jg   # → resolved_commit b10b66a, branch main
```

**Tests / lint** (from `capstone-app/`):
```bash
uvx ruff format --check app/ lakebase/ && uvx ruff check app/ lakebase/
cd app && uv run --with "psycopg[binary,pool]" --with databricks-sdk \
    --with python-dotenv --with pytest pytest -q
```
`live`-marked tests hit the `fevm-test-jg` workspace and skip when auth is absent.

**Frontend build** (committed to `app/backend/static/` for the git-source runtime):
```bash
cd capstone-app/app && bun run build
```
