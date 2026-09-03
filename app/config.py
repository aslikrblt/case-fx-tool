"""Application configuration, read once from environment variables.

Nothing outside this module may hardcode the upstream host or the port —
both are read here so the service can be pointed at a fake upstream (and a
different port) during evaluation without touching any other file.
"""

from __future__ import annotations

import os

PORT: int = int(os.environ.get("PORT", "8080"))
FX_UPSTREAM_BASE: str = os.environ.get("FX_UPSTREAM_BASE", "https://api.frankfurter.dev")
