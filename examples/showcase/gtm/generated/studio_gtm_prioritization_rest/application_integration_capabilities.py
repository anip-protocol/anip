"""Starter ANIP capability scaffold for Application Integration."""
# Project: GTM Prioritization Service

from typing import Any

capabilities = [
    {
        "name": "gtm.score_leads",
        "description": "Return bounded lead scores and explainable priority bands for a named cohort.",
        "side_effect_level": "read_only",
    },
    {
        "name": "gtm.prioritize_accounts",
        "description": "Rank bounded accounts or enriched cohorts by explainable GTM priority.",
        "side_effect_level": "read_only",
    },
    {
        "name": "gtm.route_leads",
        "description": "Preview or approve routing recommendations for a bounded lead cohort.",
        "side_effect_level": "approval_required_write",
    },
]

async def capability_permission_preflight(intent: dict[str, Any]) -> dict[str, Any]:
    raise NotImplementedError("Implement governed preflight for capability invocation")


async def execute_governed_capability(intent: dict[str, Any]) -> dict[str, Any]:
    raise NotImplementedError("Implement backend-specific execution after preflight and clarification")


async def request_mutation_approval(intent: dict[str, Any]) -> dict[str, Any]:
    raise NotImplementedError("Implement explicit approval handling for write capabilities")