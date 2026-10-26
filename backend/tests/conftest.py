"""
tests/conftest.py

Test-wide setup.

`config.Settings` declares ERPNext and Groq credentials as required fields with
no defaults, and `config.py` builds the settings singleton at import time.  Any
module that imports `config` therefore needs those variables to be present
before the import happens.

Setting them here — conftest is imported before any test module — lets the unit
tests import the agents without a real `.env`, a reachable ERPNext instance or a
Groq API key.  The values below are deliberately fake: nothing in these tests
opens a socket.

ANOMALY_THRESHOLD_PCT is pinned to 15.0 so the suite does not change behaviour
depending on what a developer happens to have in their local `.env`.
"""

import os

os.environ.setdefault("ERPNEXT_BASE_URL", "https://erpnext.test.invalid")
os.environ.setdefault("ERPNEXT_API_KEY", "test-key")
os.environ.setdefault("ERPNEXT_API_SECRET", "test-secret")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")

# Pinned, not setdefault — the suite asserts on this value.
os.environ["ANOMALY_THRESHOLD_PCT"] = "15.0"
