"""Audit probe — queries the ANIP audit endpoint and classifies events."""

from __future__ import annotations

import httpx

# Mapping from declared side_effect.type to expected audit event_class.
_EVENT_CLASS_MAP: dict[str, str] = {
    "read": "low_risk_success",
    "write": "high_risk_success",
    "irreversible": "high_risk_success",
    "transactional": "high_risk_success",
}


class AuditProbe:
    """Queries the ANIP audit surface to verify event classification."""

    def __init__(self, base_url: str, bearer: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.bearer = bearer

    async def query_latest(self, capability: str, limit: int = 5) -> list[dict]:
        """Query ``POST /anip/audit`` and return entries for *capability*."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/anip/audit",
                headers={"Authorization": f"Bearer {self.bearer}"},
                json={"capability": capability, "limit": limit},
            )
            resp.raise_for_status()
            data = resp.json()
        entries = data if isinstance(data, list) else data.get("entries", [])
        return [e for e in entries if e.get("capability") == capability]

    @staticmethod
    def check_event_class(
        entry: dict, expected_side_effect: str
    ) -> tuple[str, str, str]:
        """Compare ``event_class`` against the expected mapping.

        Returns ``(result, confidence, detail)`` where *result* is one of
        ``"PASS"``, ``"FAIL"``, or ``"WARN"``.
        """
        expected_class = _EVENT_CLASS_MAP.get(expected_side_effect)
        if expected_class is None:
            return (
                "WARN",
                "medium",
                f"Unknown side_effect type '{expected_side_effect}'",
            )

        actual_class = entry.get("event_class")
        if actual_class is None:
            return ("FAIL", "medium", "Audit entry missing 'event_class' field")

        if actual_class == expected_class:
            return (
                "PASS",
                "elevated",
                f"event_class '{actual_class}' matches expected for {expected_side_effect}",
            )

        return (
            "FAIL",
            "elevated",
            f"event_class '{actual_class}' != expected '{expected_class}' "
            f"for side_effect '{expected_side_effect}'",
        )

    @staticmethod
    def check_cost_actual(invoke_response: dict) -> tuple[str, str, str]:
        """Check whether ``cost_actual`` is present in a successful response.

        Returns ``(result, confidence, detail)``.
        """
        if "cost_actual" in invoke_response and invoke_response["cost_actual"]:
            return ("PASS", "medium", "cost_actual present in response")
        return ("FAIL", "medium", "cost_actual missing from response")
