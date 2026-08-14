"""T3a happy-path M2M test.

Gets an OAuth bearer for the partner SP, calls the external endpoint through the
Apps proxy, and expects 200 + the customer JSON. Run from this directory so the
``_token`` import resolves:

    export DATABRICKS_HOST=https://fevm-test-jg.cloud.databricks.com
    export APP_URL=https://customer360-dev-....aws.databricksapps.com
    export DATABRICKS_CLIENT_ID=<partner-sp-client-id>
    export DATABRICKS_CLIENT_SECRET=<partner-sp-client-secret>
    export CUSTOMER_ID=C0000001            # optional
    uv run --with databricks-sdk python m2m_test.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

from _token import partner_bearer


def main() -> int:
    app_url = os.environ["APP_URL"].rstrip("/")
    customer_id = os.environ.get("CUSTOMER_ID", "C0000001")
    url = f"{app_url}/api/external/customers/{customer_id}"

    req = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {partner_bearer()}"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 — https app URL
            status, body = resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        status, body = e.code, e.read().decode()

    print(f"GET {url} -> {status}")
    try:
        print(json.dumps(json.loads(body), indent=2, default=str))
    except json.JSONDecodeError:
        print(body)

    if status != 200:
        print("FAILED: expected 200", file=sys.stderr)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
