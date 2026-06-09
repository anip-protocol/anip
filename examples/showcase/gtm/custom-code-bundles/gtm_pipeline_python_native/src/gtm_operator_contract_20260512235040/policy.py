"""Policy seam for the GTM Python-native language-parity bundle."""
from __future__ import annotations

from typing import Any


async def evaluate_policy(_context: dict[str, Any]) -> dict[str, Any]:
    return {
        "decision": "allow",
        "detail": "GTM Python native bundle evaluates actor and approval behavior in its backend adapter.",
    }
