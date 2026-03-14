"""Shared SDK instances -- initialized by main.py at import time.

This module exists to break circular-import chains: capability files need
the DelegationEngine, but main.py imports capability files.  By storing
the shared instances here (populated during startup), both sides can
reference them without importing each other.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from anip_crypto import KeyManager
    from anip_server import DelegationEngine, SQLiteStorage

# These are set by main.py during startup
engine: DelegationEngine = None  # type: ignore[assignment]
storage: SQLiteStorage = None  # type: ignore[assignment]
keys: KeyManager = None  # type: ignore[assignment]
