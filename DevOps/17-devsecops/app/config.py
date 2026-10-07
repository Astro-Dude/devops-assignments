"""Runtime configuration for the payment integration.

Credentials are never stored in source code: they are injected at runtime
(e.g. from a Kubernetes Secret via env) and default to empty.
"""

import os

PAYMENT_API_KEY = os.environ.get("PAYMENT_API_KEY", "")
PAYMENT_API_URL = os.environ.get("PAYMENT_API_URL", "https://payments.example.invalid/v1")
