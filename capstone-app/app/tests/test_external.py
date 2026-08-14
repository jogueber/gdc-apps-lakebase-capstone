"""T3a — external M2M endpoint tests (offline).

Unlike the in-app suites, these mock the OBO WorkspaceClient's warehouse call,
so they run without Databricks auth (no ``live`` marker). They assert the
handler reads gold via the injected caller client and returns the CustomerDetail
shape — the SP path and Lakebase are never involved.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from backend.deps import get_obo_client
from backend.main import app
from fastapi.testclient import TestClient

_PROFILE_COLS = [
    "customer_id", "first_name", "last_name", "email", "phone", "country",
    "city", "gender", "age", "signup_date", "last_purchase_date", "segment_id",
    "lifetime_value", "churn_score", "updated_at",
]  # fmt: skip
_TXN_COLS = [
    "transaction_id", "customer_id", "product_id", "transaction_date",
    "channel", "status", "amount",
]  # fmt: skip


def _stmt_response(columns: list[str], rows: list[list]) -> SimpleNamespace:
    """Shape a fake execute_statement response (columns + data_array)."""
    schema = SimpleNamespace(columns=[SimpleNamespace(name=c) for c in columns])
    return SimpleNamespace(
        manifest=SimpleNamespace(schema=schema),
        result=SimpleNamespace(data_array=rows),
    )


def _mock_obo(profile_rows: list[list], txn_rows: list[list]) -> MagicMock:
    w = MagicMock()

    def execute(statement: str, **_):
        if "FROM customers" in statement:
            return _stmt_response(_PROFILE_COLS, profile_rows)
        return _stmt_response(_TXN_COLS, txn_rows)

    w.statement_execution.execute_statement.side_effect = execute
    return w


@pytest.fixture
def client():
    # No `with`: skip the lifespan (which would touch live Lakebase). Router
    # routes are registered at import time, so the endpoint is available.
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_external_customer_ok(client):
    profile = [[
        "C0000001", "Ada", "Lovelace", "ada@x.com", "555", "UK", "London", "F",
        "36", "2020-01-02", "2021-03-04", "S1", "12345.6", "0.12",
        "2021-03-04T00:00:00",
    ]]  # fmt: skip
    txns = [["T1", "C0000001", "P1", "2021-03-04", "web", "completed", "99.5"]]
    app.dependency_overrides[get_obo_client] = lambda: _mock_obo(profile, txns)

    r = client.get("/api/external/customers/C0000001")
    assert r.status_code == 200
    body = r.json()
    assert body["profile"]["customer_id"] == "C0000001"
    assert body["profile"]["lifetime_value"] == 12345.6
    assert len(body["transactions"]) == 1
    assert body["transactions"][0]["amount"] == 99.5


def test_external_customer_404(client):
    app.dependency_overrides[get_obo_client] = lambda: _mock_obo([], [])
    assert client.get("/api/external/customers/NOPE-0000").status_code == 404
