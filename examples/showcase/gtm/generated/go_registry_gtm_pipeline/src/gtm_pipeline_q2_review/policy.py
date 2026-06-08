"""Policy seam for generated capabilities."""
from __future__ import annotations

from typing import Any

async def evaluate_policy(_context: dict[str, Any]) -> dict[str, Any]:
    return {"decision": "allow"}
