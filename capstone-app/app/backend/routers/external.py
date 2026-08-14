"""T3a — External partner API (M2M).

A separate ``/api/external`` surface for partner systems. It returns the same
``CustomerDetail`` shape as the in-app detail endpoint, but reads **Delta gold
via the SQL warehouse using the caller's bearer (OBO)** — never Lakebase, never
the app SP — so warehouse RLS / audit reflect the calling (partner) identity.

Partners authenticate as a service principal via the OAuth ``client_credentials``
grant and send the resulting bearer to the Apps proxy; the proxy forwards it as
``X-Forwarded-Access-Token``, which the shared ``Obo`` dependency turns into a
per-request ``WorkspaceClient`` (see ``auth.obo_client``). See ``examples/`` for
the client-side M2M flow.
"""

from __future__ import annotations

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementParameterListItem
from fastapi import APIRouter, HTTPException

from ..config import get_settings
from ..deps import Obo
from ..models import CustomerDetail, CustomerSynced, TransactionSynced

router = APIRouter(prefix="/api/external", tags=["external"])

# Explicit column lists (no SELECT *), ordered to match the model fields. Bound
# on the named marker :cid — same parameterization as the in-app metrics path.
_PROFILE_SQL = (
    "SELECT customer_id, first_name, last_name, email, phone, country, city, "
    "gender, age, signup_date, last_purchase_date, segment_id, lifetime_value, "
    "churn_score, updated_at FROM customers WHERE customer_id = :cid"
)
_TXNS_SQL = (
    "SELECT transaction_id, customer_id, product_id, transaction_date, channel, "
    "status, amount FROM transactions WHERE customer_id = :cid "
    "ORDER BY transaction_date DESC LIMIT 20"
)


def _run_stmt(w: WorkspaceClient, sql: str, customer_id: str) -> list[dict]:
    """Run one warehouse statement bound to :cid, return rows as dicts."""
    s = get_settings()
    resp = w.statement_execution.execute_statement(
        statement=sql,
        warehouse_id=s.warehouse_id,
        catalog=s.capstone_catalog,
        schema=s.capstone_schema,
        parameters=[StatementParameterListItem(name="cid", value=customer_id)],
        wait_timeout="30s",
    )
    cols = [c.name for c in (resp.manifest.schema.columns or [])]
    data = resp.result.data_array if resp.result and resp.result.data_array else []
    return [dict(zip(cols, row)) for row in data]


# Sync handler: FastAPI runs it in a threadpool, so the blocking SDK call
# doesn't stall the event loop, and the two reads stay simple and sequential.
@router.get("/customers/{customer_id}", response_model=CustomerDetail)
def external_customer(customer_id: str, obo: Obo) -> CustomerDetail:
    profile = _run_stmt(obo, _PROFILE_SQL, customer_id)
    if not profile:
        raise HTTPException(status_code=404, detail="customer not found")
    txns = _run_stmt(obo, _TXNS_SQL, customer_id)
    return CustomerDetail(
        profile=CustomerSynced.model_validate(profile[0]),
        transactions=[TransactionSynced.model_validate(t) for t in txns],
    )
