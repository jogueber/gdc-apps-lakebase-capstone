"""Shared M2M helper: run the SDK client_credentials flow, return a bearer.

The partner authenticates as a **service principal**. You cannot send the SP's
``client_secret`` as the bearer directly — the SDK exchanges it against
``/oidc/v1/token`` and returns the resulting OAuth ``access_token``, which is
what goes in ``Authorization: Bearer <token>`` to the Apps proxy.

Env:
  DATABRICKS_HOST           workspace URL (e.g. https://fevm-test-jg.cloud.databricks.com)
  DATABRICKS_CLIENT_ID      partner SP's OAuth client id
  DATABRICKS_CLIENT_SECRET  partner SP's OAuth client secret
"""

from __future__ import annotations

import os

from databricks.sdk.core import Config


def partner_bearer() -> str:
    """Mint an OAuth access token for the partner SP via client_credentials."""
    cfg = Config(
        host=os.environ["DATABRICKS_HOST"],
        client_id=os.environ["DATABRICKS_CLIENT_ID"],
        client_secret=os.environ["DATABRICKS_CLIENT_SECRET"],
    )
    return cfg.oauth_token().access_token
