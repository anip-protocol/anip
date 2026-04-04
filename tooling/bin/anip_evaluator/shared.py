from __future__ import annotations

from typing import Any


EvalResult = tuple[
    list[str],  # handled
    list[str],  # glue
    list[str],  # glue_category
    list[str],  # why
    list[str],  # improve
    str,        # result
]


def has_path(mapping: dict[str, Any], *keys: str) -> bool:
    cur: Any = mapping
    for key in keys:
        if not isinstance(cur, dict) or key not in cur:
            return False
        cur = cur[key]
    return True


def get_path(mapping: dict[str, Any], *keys: str, default: Any = None) -> Any:
    cur: Any = mapping
    for key in keys:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def append_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def _is_multi_service(req: dict[str, Any], proposal: dict[str, Any]) -> bool:
    if req.get("services") and isinstance(req["services"], list) and len(req["services"]) > 1:
        return True
    return proposal.get("recommended_shape") == "multi_service_estate"


def _common_lineage_surfaces(
    req: dict[str, Any],
    handled: list[str],
    why: list[str],
    expected_support: set[str],
) -> None:
    """Add lineage / audit / permission handled surfaces that are common across all categories."""
    permissions = req.get("permissions", {})
    audit = req.get("audit", {})
    lineage = req.get("lineage", {})

    if permissions.get("preflight_discovery") and "permission_discovery" in expected_support:
        append_unique(handled, "permission discovery")
    if lineage.get("task_id"):
        append_unique(handled, "task identity")
    if lineage.get("parent_invocation_id"):
        append_unique(handled, "parent invocation lineage")
    if audit.get("durable"):
        append_unique(handled, "durable audit")
    if audit.get("searchable") and "audit_queryability" in expected_support:
        append_unique(handled, "audit queryability")
    if "structured_failure" in expected_support:
        append_unique(handled, "structured failure")

    side_effect_required = (
        "side_effect_visibility" in expected_support
        or "irreversible_side_effect_visibility" in expected_support
    )
    if side_effect_required:
        append_unique(handled, "side-effect visibility")
    if "cost_visibility" in expected_support:
        append_unique(handled, "cost visibility")


def _extract_proposal_surfaces(proposal: dict[str, Any]) -> dict[str, bool]:
    """Extract which advisory surfaces the proposal actually declares."""
    ds = proposal.get("declared_surfaces")
    if isinstance(ds, dict):
        return {
            "budget_enforcement": bool(ds.get("budget_enforcement", False)),
            "binding": bool(ds.get("binding_requirements", False)),
            "authority_posture": bool(ds.get("authority_posture", False)),
            "recovery_class": bool(ds.get("recovery_class", False)),
            "refresh_via": bool(ds.get("refresh_via", False)),
            "verify_via": bool(ds.get("verify_via", False)),
            "followup": bool(ds.get("followup_via", False)),
            "cross_service_hints": bool(ds.get("cross_service_handoff", False)),
            "upstream_service": bool(ds.get("cross_service_continuity", False)),
            "cross_service_reconstruction": bool(ds.get("cross_service_reconstruction", False)),
            "audit": False,
            "lineage": False,
            "revalidation": False,
            "availability": False,
        }

    proposal_components = set(
        proposal.get("required_components", [])
        + proposal.get("optional_components", [])
    )
    key_requirements = proposal.get("key_runtime_requirements", [])
    key_req_text = " ".join(key_requirements).lower()
    rationale_text = " ".join(proposal.get("rationale", [])).lower()
    component_text = " ".join(proposal_components).lower()
    all_text = key_req_text + " " + rationale_text + " " + component_text

    return {
        "refresh_via": (
            "refresh_via" in all_text
            or "refresh" in all_text
        ),
        "verify_via": (
            "verify_via" in all_text
            or "verif" in all_text
        ),
        "cross_service_hints": (
            "cross_service" in all_text
            or "cross-service" in all_text
            or "handoff" in all_text
        ),
        "recovery_class": (
            "recovery_class" in all_text
            or "recovery" in all_text
        ),
        "budget_enforcement": (
            "budget" in all_text
            or "constraints.budget" in all_text
        ),
        "binding": (
            "binding" in all_text
            or "requires_binding" in all_text
        ),
        "audit": (
            "audit" in all_text
        ),
        "lineage": (
            "lineage" in all_text
        ),
        "upstream_service": (
            "upstream" in all_text
            or "task_id" in all_text
            or "task identity" in all_text
        ),
        "followup": (
            "followup" in all_text
            or "follow-up" in all_text
            or "follow_up" in all_text
        ),
        "revalidation": (
            "revalidat" in all_text
        ),
        "availability": (
            "availability" in all_text
            or "unavailab" in all_text
        ),
    }


def _common_multi_service_surfaces(
    req: dict[str, Any],
    proposal: dict[str, Any],
    handled: list[str],
    why: list[str],
) -> None:
    """Add cross-service surfaces when req declares multiple services AND proposal declares them."""
    if not _is_multi_service(req, proposal):
        return

    surfaces = _extract_proposal_surfaces(proposal)

    if surfaces["upstream_service"] or surfaces["lineage"]:
        append_unique(handled, "cross-service task identity continuity")

    if surfaces["audit"]:
        append_unique(handled, "independent but linkable audit records")

    if surfaces["cross_service_hints"]:
        append_unique(handled, "cleaner service handoff")

    credited = [h for h in [
        "cross-service task identity continuity",
        "independent but linkable audit records",
        "cleaner service handoff",
    ] if h in handled]

    if credited:
        why.append(
            "the design already removes a large amount of cross-service "
            "correlation and trace-stitching glue"
        )
