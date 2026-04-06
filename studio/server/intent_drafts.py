"""Deterministic draft builders for Studio intent and fix generation."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import uuid4
import re


def slugify(value: str) -> str:
    return re.sub(r"(^-+|-+$)", "", re.sub(r"[^a-z0-9]+", "-", value.lower().strip()))


def normalized_words(*parts: str) -> set[str]:
    return {
        item.strip()
        for item in re.split(r"[^a-z0-9]+", " ".join(parts).lower())
        if item.strip()
    }


def titleize(value: str) -> str:
    compact = re.sub(r"\s+", " ", re.sub(r"[_-]+", " ", value)).strip()
    return " ".join(part.capitalize() for part in compact.split())


def clean_sentence(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def scenario_title_from_starter(text: str, index: int) -> str:
    cleaned = clean_sentence(text)
    cleaned = re.sub(r"^add a scenario where\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^describe\s+", "", cleaned, flags=re.IGNORECASE)
    compact = cleaned.rstrip(".")
    if not compact:
        return f"Scenario {index}"
    shortened = f"{compact[:69].strip()}..." if len(compact) > 72 else compact
    return titleize(shortened)


def infer_scenario_category(
    text: str,
) -> str:
    words = normalized_words(text)
    if {"handoff", "handoffs", "cross", "services", "service"} & words:
        return "cross_service"
    if {"verify", "verification", "confirm", "reconcile"} & words:
        return "observability"
    if {"refresh", "stale", "expired", "revalidate"} & words:
        return "recovery"
    if {"follow", "followup", "async", "approval"} & words:
        return "orchestration"
    return "safety"


def make_requirements_template(name: str, domain: str) -> dict[str, Any]:
    return {
        "system": {
            "name": slugify(name) or "new-service",
            "domain": domain or "general",
            "deployment_intent": "public_http_service",
        },
        "transports": {"http": True, "stdio": False, "grpc": False},
        "trust": {"mode": "signed", "checkpoints": False},
        "auth": {
            "delegation_tokens": True,
            "purpose_binding": True,
            "scoped_authority": True,
        },
        "permissions": {
            "preflight_discovery": True,
            "restricted_vs_denied": True,
        },
        "audit": {"durable": True, "searchable": True},
        "lineage": {
            "invocation_id": True,
            "client_reference_id": True,
            "task_id": True,
            "parent_invocation_id": True,
        },
        "risk_profile": {},
        "business_constraints": {},
        "scale": {
            "shape_preference": "production_single_service",
            "high_availability": False,
        },
    }


def make_requirements_template_from_intent(
    interpretation: dict[str, Any],
    intent: str,
    project_name: str,
    project_domain: str,
) -> dict[str, Any]:
    data = make_requirements_template(project_name, project_domain)
    words = normalized_words(
        intent,
        interpretation.get("summary", ""),
        interpretation.get("recommended_shape_reason", ""),
        *interpretation.get("requirements_focus", []),
        *interpretation.get("scenario_starters", []),
        *interpretation.get("next_steps", []),
    )
    data["system"]["name"] = slugify(project_name or interpretation.get("title", "") or "new-service") or "new-service"
    data["scale"]["shape_preference"] = (
        "multi_service_estate"
        if interpretation.get("recommended_shape_type") == "multi_service"
        else "production_single_service"
    )
    constraints = data["business_constraints"]
    mentions_budget = bool({"budget", "cost", "spend", "price", "pricing"} & words)
    mentions_approval = bool({"approval", "approve", "approver", "escalate", "escalation"} & words)
    mentions_recovery = bool({"refresh", "stale", "expired", "revalidate", "recovery"} & words)
    mentions_risk = bool({"risk", "danger", "dangerous", "destructive", "delete"} & words)
    constraints["spending_possible"] = mentions_budget
    constraints["cost_visibility_required"] = mentions_budget
    constraints["approval_expected_for_high_risk"] = mentions_approval or mentions_risk
    constraints["recovery_sensitive"] = mentions_recovery
    constraints["blocked_failure_posture"] = (
        "structured_blocked"
        if mentions_budget or mentions_approval or mentions_recovery or mentions_risk
        else "basic_failure_surface"
    )
    return data


def make_scenario_templates_from_intent(interpretation: dict[str, Any]) -> list[dict[str, Any]]:
    starters = list(interpretation.get("scenario_starters") or [])[:3]
    if not starters:
        starters = ["Describe the normal success path that the service should handle cleanly."]
    result: list[dict[str, Any]] = []
    for index, starter in enumerate(starters, start=1):
        category = infer_scenario_category(starter)
        title = scenario_title_from_starter(starter, index)
        scenario_name = slugify(title) or f"scenario-{index}"
        words = normalized_words(starter)
        if {"book", "booking"} & words:
            capability = "book_the_primary_action"
        elif {"verify", "verification"} & words:
            capability = "verify_the_outcome"
        elif {"refresh", "stale"} & words:
            capability = "refresh_or_revalidate_before_acting"
        elif {"approval", "approve"} & words:
            capability = "request_or_record_approval"
        else:
            capability = "handle_the_primary_action"
        expected_behavior = [
            starter,
            (
                "The service boundary should remain clear across the handoff."
                if category == "cross_service"
                else "The system should make the intended control decision explicit."
            ),
        ]
        if category == "recovery":
            expected_support = ["The contract should make refresh or recovery guidance explicit."]
        elif category == "observability":
            expected_support = ["The contract should expose enough context to verify and explain the outcome."]
        elif category == "cross_service":
            expected_support = ["The contract should preserve continuity and handoff meaning across services."]
        else:
            expected_support = ["The contract should make purpose, constraints, and blocked-action meaning explicit."]
        result.append(
            {
                "title": title,
                "data": {
                    "scenario": {
                        "name": scenario_name,
                        "category": category,
                        "narrative": starter,
                        "context": {"capability": capability},
                        "expected_behavior": expected_behavior,
                        "expected_anip_support": expected_support,
                    }
                },
            }
        )
    return result


def make_shape_template_from_intent(interpretation: dict[str, Any], project_name: str) -> dict[str, Any]:
    root_name = project_name or "new-service"
    shape_name = titleize(root_name)
    primary_service_id = slugify(root_name) or "primary-service"
    concept_ids = [
        {"id": slugify(concept) or f"concept-{uuid4()}", "name": concept}
        for concept in interpretation.get("domain_concepts", [])
    ]
    primary_service = {
        "id": primary_service_id,
        "name": shape_name,
        "role": "primary service",
        "responsibilities": [
            "Own the main action and the core control checks around it.",
            *list(interpretation.get("requirements_focus", []))[:2],
        ],
        "capabilities": [
            "handle_primary_action",
            *[(slugify(item) or "support_scenario") for item in list(interpretation.get("scenario_starters", []))[:2]],
        ],
        "owns_concepts": [concept["id"] for concept in concept_ids[: max(1, len(concept_ids) - 1)]],
    }
    services: list[dict[str, Any]] = [primary_service]
    coordination: list[dict[str, Any]] = []
    suggestions = [str(item).lower() for item in interpretation.get("service_suggestions", [])]
    starter_words = normalized_words(*[str(item) for item in interpretation.get("scenario_starters", [])])
    if interpretation.get("recommended_shape_type") == "multi_service":
        if any("approval" in item for item in suggestions):
            services.append(
                {
                    "id": "approval-service",
                    "name": "Approval Service",
                    "role": "approval boundary",
                    "responsibilities": ["Track approvals and decisions that should not be hidden inside the main action."],
                    "capabilities": ["request_approval", "record_approval_decision"],
                    "owns_concepts": [concept["id"] for concept in concept_ids if "approval" in concept["name"].lower()],
                }
            )
            coordination.append(
                {
                    "from": primary_service_id,
                    "to": "approval-service",
                    "relationship": "handoff",
                    "description": "Send blocked or exceptional work for approval before the main action proceeds.",
                }
            )
        if any("verification" in item for item in suggestions):
            services.append(
                {
                    "id": "verification-service",
                    "name": "Verification Service",
                    "role": "verification boundary",
                    "responsibilities": ["Verify the outcome after the initial action completes."],
                    "capabilities": ["verify_outcome", "record_verification_result"],
                    "owns_concepts": [concept["id"] for concept in concept_ids if "outcome" in concept["name"].lower()],
                }
            )
            coordination.append(
                {
                    "from": primary_service_id,
                    "to": "verification-service",
                    "relationship": "verification",
                    "description": "Verify that the completed action actually reached the intended end state.",
                }
            )
        if any("refresh" in item or "revalidation" in item for item in suggestions):
            services.append(
                {
                    "id": "revalidation-service",
                    "name": "Revalidation Service",
                    "role": "refresh boundary",
                    "responsibilities": ["Refresh stale or expired inputs before the main action continues."],
                    "capabilities": ["refresh_input", "revalidate_input"],
                    "owns_concepts": [concept["id"] for concept in concept_ids if "quote" in concept["name"].lower()],
                }
            )
            coordination.append(
                {
                    "from": primary_service_id,
                    "to": "revalidation-service",
                    "relationship": "refresh",
                    "description": "Refresh or revalidate inputs before the main action proceeds.",
                }
            )
        followup_signals = {"followup", "fulfillment", "notification", "notify", "webhook", "async", "later"}
        if starter_words & followup_signals:
            services.append(
                {
                    "id": "followup-service",
                    "name": "Follow-up Service",
                    "role": "follow-up boundary",
                    "responsibilities": ["Track follow-up status after the primary action is accepted."],
                    "capabilities": ["report_followup_status", "handle_followup"],
                    "owns_concepts": [concept["id"] for concept in concept_ids if "notification" in concept["name"].lower()],
                }
            )
            coordination.append(
                {
                    "from": primary_service_id,
                    "to": "followup-service",
                    "relationship": "async_followup",
                    "description": "Keep delayed follow-up work explicit instead of hiding it in retries or wrapper glue.",
                }
            )
        if len(services) == 1:
            services.append(
                {
                    "id": "support-service",
                    "name": "Support Service",
                    "role": "supporting responsibility",
                    "responsibilities": ["Handle the secondary follow-up, coordination, or verification responsibility implied by the brief."],
                    "capabilities": ["handle_followup_or_coordination"],
                    "owns_concepts": [],
                }
            )
            coordination.append(
                {
                    "from": primary_service_id,
                    "to": "support-service",
                    "relationship": "handoff",
                    "description": "Separate the secondary responsibility instead of hiding it inside one oversized service.",
                }
            )
    return {
        "shape": {
            "id": slugify(f"{shape_name}-shape") or "service-shape",
            "name": shape_name,
            "type": "multi_service" if interpretation.get("recommended_shape_type") == "multi_service" else "single_service",
            "notes": [
                interpretation.get("recommended_shape_reason", ""),
                *list(interpretation.get("service_suggestions", []))[:2],
            ],
            "services": services,
            "coordination": coordination,
            "domain_concepts": [
                {
                    "id": concept["id"],
                    "name": concept["name"],
                    "meaning": f"Business concept: {concept['name']}",
                    "owner": (
                        "approval-service"
                        if len(services) > 1 and "approval" in concept["name"].lower()
                        else "shared"
                        if len(services) > 1 and index == len(concept_ids) - 1
                        else primary_service_id
                    ),
                    "sensitivity": (
                        "medium"
                        if "approval" in concept["name"].lower() or "budget" in concept["name"].lower()
                        else "none"
                    ),
                }
                for index, concept in enumerate(concept_ids)
            ],
        }
    }


def classify_change_target(text: str) -> str:
    words = normalized_words(text)
    if {"requirement", "requirements", "budget", "approval", "audit", "lineage", "constraint", "authority"} & words:
        return "requirements"
    if {"shape", "service", "boundary", "coordination", "capability", "concept"} & words:
        return "shape"
    if {"scenario", "followup", "follow", "handoff", "verification", "refresh", "revalidate"} & words:
        return "scenario"
    return "shape"


def unwrap_data(data: dict[str, Any] | None) -> dict[str, Any]:
    base = data or {}
    return base.get("requirements") or base.get("shape") or base


def make_requirements_fix_template(change: str, current: dict[str, Any] | None) -> dict[str, Any]:
    base = deepcopy(unwrap_data(current) if current else make_requirements_template("new-service", "general"))
    words = normalized_words(change)
    constraints = base.setdefault("business_constraints", {})
    audit = base.setdefault("audit", {})
    lineage = base.setdefault("lineage", {})
    if {"budget", "cost", "spend"} & words:
        constraints["spending_possible"] = True
        constraints["cost_visibility_required"] = True
        constraints["blocked_failure_posture"] = "structured_blocked"
    if {"approval", "authority", "escalate"} & words:
        constraints["approval_expected_for_high_risk"] = True
        constraints["blocked_failure_posture"] = "structured_blocked"
    if {"recovery", "refresh", "revalidate", "stale"} & words:
        constraints["recovery_sensitive"] = True
        constraints["blocked_failure_posture"] = "structured_blocked"
    if {"audit", "trace"} & words:
        audit["durable"] = True
        audit["searchable"] = True
    if {"lineage", "continuity", "cross"} & words:
        lineage["task_id"] = True
        lineage["parent_invocation_id"] = True
        lineage["cross_service_continuity_required"] = True
        audit["cross_service_reconstruction_required"] = True
    return base


def make_scenario_fix_template(change: str, current: dict[str, Any] | None, index: int) -> dict[str, Any]:
    base_scenario = (current or {}).get("scenario", {})
    category = infer_scenario_category(change)
    title = scenario_title_from_starter(change, index)
    return {
        "scenario": {
            "name": slugify(title) or f"scenario-{index}",
            "category": category,
            "narrative": clean_sentence(change),
            "context": {
                "capability": base_scenario.get("context", {}).get("capability") or "handle_the_primary_action",
            },
            "expected_behavior": [
                clean_sentence(change),
                (
                    "The cross-service responsibility should stay explicit instead of hiding inside glue."
                    if category == "cross_service"
                    else "The system should make the intended decision and next step explicit."
                ),
            ],
            "expected_anip_support": [
                (
                    "The contract should preserve cross-service continuity and handoff meaning."
                    if category == "cross_service"
                    else "The contract should make refresh or recovery guidance explicit."
                    if category == "recovery"
                    else "The contract should make purpose, blocked-action meaning, and next steps explicit."
                )
            ],
        }
    }


def make_shape_fix_template(change: str, current: dict[str, Any] | None) -> dict[str, Any]:
    shape = deepcopy(
        unwrap_data(current)
        if current
        else {"type": "single_service", "services": [], "coordination": [], "domain_concepts": [], "notes": []}
    )
    words = normalized_words(change)
    shape["notes"] = [*shape.get("notes", []), clean_sentence(change)]
    shape.setdefault("services", [])
    shape.setdefault("coordination", [])
    shape.setdefault("domain_concepts", [])
    primary_service = shape["services"][0] if shape["services"] else None
    if primary_service:
        primary_service.setdefault("responsibilities", [])
        primary_service.setdefault("capabilities", [])
    if primary_service and {"budget", "approval", "authority"} & words:
        primary_service["responsibilities"].append("Make high-risk control checks explicit before the main action proceeds.")
        primary_service["capabilities"].append("enforce_control_decision")
    if primary_service and {"refresh", "revalidate", "stale"} & words:
        primary_service["capabilities"].append("refresh_or_revalidate_input")
    if {"verification", "verify"} & words and not any(item.get("id") == "verification-service" for item in shape["services"]):
        shape["services"].append(
            {
                "id": "verification-service",
                "name": "Verification Service",
                "role": "verification boundary",
                "responsibilities": ["Verify the outcome after the main action completes."],
                "capabilities": ["verify_outcome"],
                "owns_concepts": [],
            }
        )
    if {"verification", "verify"} & words and not any(item.get("to") == "verification-service" for item in shape["coordination"]):
        shape["coordination"].append(
            {
                "from": primary_service.get("id", "primary-service") if primary_service else "primary-service",
                "to": "verification-service",
                "relationship": "verification",
                "description": clean_sentence(change),
            }
        )
    if {"handoff", "cross", "coordination", "followup"} & words and not any(item.get("id") == "followup-service" for item in shape["services"]):
        shape["services"].append(
            {
                "id": "followup-service",
                "name": "Follow-up Service",
                "role": "handoff boundary",
                "responsibilities": ["Handle the follow-up or secondary service responsibility explicitly."],
                "capabilities": ["handle_followup"],
                "owns_concepts": [],
            }
        )
    if {"handoff", "cross", "coordination", "followup"} & words and not any(item.get("to") == "followup-service" for item in shape["coordination"]):
        shape["coordination"].append(
            {
                "from": primary_service.get("id", "primary-service") if primary_service else "primary-service",
                "to": "followup-service",
                "relationship": "async_followup" if "followup" in words else "handoff",
                "description": clean_sentence(change),
            }
        )
    if {"refresh", "revalidate", "stale"} & words and not any(item.get("id") == "revalidation-service" for item in shape["services"]):
        shape["services"].append(
            {
                "id": "revalidation-service",
                "name": "Revalidation Service",
                "role": "refresh boundary",
                "responsibilities": ["Refresh stale or expired inputs before the main action continues."],
                "capabilities": ["refresh_input", "revalidate_input"],
                "owns_concepts": [],
            }
        )
    if {"refresh", "revalidate", "stale"} & words and not any(item.get("to") == "revalidation-service" for item in shape["coordination"]):
        shape["coordination"].append(
            {
                "from": primary_service.get("id", "primary-service") if primary_service else "primary-service",
                "to": "revalidation-service",
                "relationship": "refresh",
                "description": clean_sentence(change),
            }
        )
    if {"concept", "entity", "domain"} & words:
        shape["domain_concepts"].append(
            {
                "id": f"concept-{uuid4()}",
                "name": "New Domain Concept",
                "meaning": clean_sentence(change),
                "owner": primary_service.get("id", "shared") if primary_service else "shared",
                "sensitivity": "none",
            }
        )
    return {"shape": shape}
