"""ANIP-backed Studio assistant service.

The first slice is explanation-only on purpose. Studio uses a real ANIP
service for shape and evaluation explanations so we can dogfood the protocol
without turning the product into a generic chat surface.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

from anip_core import (
    CapabilityDeclaration,
    CapabilityComposition,
    CapabilityInput,
    CapabilityOutput,
    CrossServiceContract,
    CrossServiceContractEntry,
    ResponseMode,
    ServiceCapabilityRef,
    SessionInfo,
    SessionType,
    SideEffect,
    SideEffectType,
)
from anip_service import ANIPError, ANIPService, Capability

from .assistant_provider import try_model_assistant_response
from .consumer_mode import consumer_mode_from_labels, consumer_mode_label, normalize_consumer_mode
from .db import get_pool
from .derivation import derive_contract_expectations
from .repository import (
    NotFoundError,
    get_evaluation,
    get_project_detail,
    get_requirements,
    get_scenario,
    get_shape,
)

BOOTSTRAP_BEARER = "studio-assistant-bootstrap"
ASSISTANT_SCOPES = [
    "studio.assistant.explain_shape",
    "studio.assistant.explain_evaluation",
    "studio.assistant.interpret_project_intent",
    "studio.assistant.start_design_review_session",
    "studio.assistant.stream_design_review",
]
DOGFOOD_ROUND2_PROFILES = {"round2", "audit-posture", "round2-audit-posture"}
DOGFOOD_ROUND3_PROFILES = {"round3", "streaming-session", "round3-streaming-session"}
DOGFOOD_ROUND4_PROFILES = {"round4", "checkpoints-proofs", "round4-checkpoints-proofs"}
DOGFOOD_ROUND5_PROFILES = {"round5", "observability-scaling", "round5-observability-scaling"}
DOGFOOD_ROUND6_PROFILES = {"round6", "capability-graph", "round6-capability-graph"}


def _dogfood_profile() -> str:
    return os.getenv("STUDIO_DOGFOOD_PROFILE", "").strip().lower()


def _round2_dogfood_enabled() -> bool:
    return _dogfood_profile() in (DOGFOOD_ROUND2_PROFILES | DOGFOOD_ROUND3_PROFILES | DOGFOOD_ROUND4_PROFILES | DOGFOOD_ROUND5_PROFILES | DOGFOOD_ROUND6_PROFILES)


def _round3_dogfood_enabled() -> bool:
    return _dogfood_profile() in (DOGFOOD_ROUND3_PROFILES | DOGFOOD_ROUND4_PROFILES | DOGFOOD_ROUND5_PROFILES | DOGFOOD_ROUND6_PROFILES)


def create_studio_assistant_service() -> ANIPService:
    capabilities: list[Capability] = [
            Capability(
                declaration=CapabilityDeclaration(
                    name="interpret_project_intent",
                    description="Turn a plain-language project brief into first-pass requirements, scenarios, concepts, and service-shape suggestions.",
                    inputs=[
                        CapabilityInput(
                            name="project_id",
                            type="string",
                            required=True,
                            description="Project the brief belongs to.",
                        ),
                        CapabilityInput(
                            name="intent",
                            type="string",
                            required=True,
                            description="Plain-language description of what the user wants to build.",
                        ),
                        CapabilityInput(
                            name="consumer_mode",
                            type="string",
                            required=False,
                            description="Optional audience bias: human_app, agent_anip, or hybrid.",
                        ),
                    ],
                    output=CapabilityOutput(
                        type="object",
                        fields=[
                            "title",
                            "summary",
                            "recommended_shape_type",
                            "recommended_shape_reason",
                            "requirements_focus",
                            "scenario_starters",
                            "domain_concepts",
                            "service_suggestions",
                            "next_steps",
                        ],
                    ),
                    side_effect=SideEffect(
                        type=SideEffectType.READ,
                        rollback_window="not_applicable",
                    ),
                    minimum_scope=["studio.assistant.interpret_project_intent"],
                    cross_service_contract=CrossServiceContract(
                        handoff=[
                            CrossServiceContractEntry(
                                target=ServiceCapabilityRef(
                                    service="studio-workbench",
                                    capability="accept_first_design",
                                ),
                                required_for_task_completion=False,
                                continuity="same_task",
                                completion_mode="downstream_acceptance",
                            )
                        ]
                    ),
                ),
                handler=_interpret_project_intent,
            ),
            Capability(
                declaration=CapabilityDeclaration(
                    name="explain_shape",
                    description="Explain the current Studio service shape in PM-friendly terms.",
                    inputs=[
                        CapabilityInput(
                            name="project_id",
                            type="string",
                            required=True,
                            description="Project containing the shape.",
                        ),
                        CapabilityInput(
                            name="shape_id",
                            type="string",
                            required=True,
                            description="Shape to explain.",
                        ),
                        CapabilityInput(
                            name="question",
                            type="string",
                            required=False,
                            description="Optional focus question from the user.",
                        ),
                    ],
                    output=CapabilityOutput(
                        type="object",
                        fields=[
                            "title",
                            "summary",
                            "focused_answer",
                            "highlights",
                            "watchouts",
                            "next_steps",
                        ],
                    ),
                    side_effect=SideEffect(
                        type=SideEffectType.READ,
                        rollback_window="not_applicable",
                    ),
                    minimum_scope=["studio.assistant.explain_shape"],
                ),
                handler=_explain_shape,
            ),
            Capability(
                declaration=CapabilityDeclaration(
                    name="explain_evaluation",
                    description="Explain a Studio evaluation result and what it means next.",
                    inputs=[
                        CapabilityInput(
                            name="project_id",
                            type="string",
                            required=True,
                            description="Project containing the evaluation.",
                        ),
                        CapabilityInput(
                            name="evaluation_id",
                            type="string",
                            required=True,
                            description="Evaluation to explain.",
                        ),
                        CapabilityInput(
                            name="question",
                            type="string",
                            required=False,
                            description="Optional focus question from the user.",
                        ),
                    ],
                    output=CapabilityOutput(
                        type="object",
                        fields=[
                            "title",
                            "summary",
                            "focused_answer",
                            "highlights",
                            "watchouts",
                            "next_steps",
                        ],
                    ),
                    side_effect=SideEffect(
                        type=SideEffectType.READ,
                        rollback_window="not_applicable",
                    ),
                    minimum_scope=["studio.assistant.explain_evaluation"],
                    cross_service_contract=CrossServiceContract(
                        followup=[
                            CrossServiceContractEntry(
                                target=ServiceCapabilityRef(
                                    service="studio-workbench",
                                    capability="draft_fix_from_change",
                                ),
                                required_for_task_completion=False,
                                continuity="same_task",
                                completion_mode="downstream_acceptance",
                            )
                        ]
                    ),
                ),
                handler=_explain_evaluation,
            ),
        ]

    if _round3_dogfood_enabled():
        capabilities.extend(
            [
                Capability(
                    declaration=CapabilityDeclaration(
                        name="start_design_review_session",
                        description="Start a bounded review session for the current Studio design.",
                        inputs=[
                            CapabilityInput(name="project_id", type="string", required=True, description="Project to review."),
                            CapabilityInput(name="shape_id", type="string", required=False, description="Optional active shape."),
                            CapabilityInput(name="scenario_id", type="string", required=False, description="Optional active scenario."),
                        ],
                        output=CapabilityOutput(
                            type="object",
                            fields=["session_id", "title", "summary", "review_focus", "next_step"],
                        ),
                        side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
                        minimum_scope=["studio.assistant.start_design_review_session"],
                        composes_with=(
                            [CapabilityComposition(capability="stream_design_review", optional=False)]
                            if _dogfood_profile() in DOGFOOD_ROUND6_PROFILES
                            else []
                        ),
                        session=SessionInfo(type=SessionType.CONTINUATION),
                    ),
                    handler=_start_design_review_session,
                ),
                Capability(
                    declaration=CapabilityDeclaration(
                        name="stream_design_review",
                        description="Stream a bounded review walkthrough for the current Studio design session.",
                        inputs=[
                            CapabilityInput(name="project_id", type="string", required=True, description="Project being reviewed."),
                            CapabilityInput(name="session_id", type="string", required=True, description="Review session to continue."),
                            CapabilityInput(name="question", type="string", required=False, description="Optional focus question."),
                        ],
                        output=CapabilityOutput(
                            type="object",
                            fields=["session_id", "summary", "highlights", "next_steps"],
                        ),
                        side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
                        minimum_scope=["studio.assistant.stream_design_review"],
                        response_modes=[ResponseMode.UNARY, ResponseMode.STREAMING],
                        session=SessionInfo(type=SessionType.CONTINUATION),
                    ),
                    handler=_stream_design_review,
                ),
            ]
        )

    return ANIPService(
        service_id="studio-assistant",
        capabilities=capabilities,
        storage=":memory:",
        authenticate=_authenticate_bootstrap_bearer,
        trust="signed",
        disclosure_level="redacted" if _round2_dogfood_enabled() else "full",
    )


def _authenticate_bootstrap_bearer(bearer: str) -> str | None:
    if bearer == BOOTSTRAP_BEARER:
        return "studio-user"
    return None


def _invalid_request(detail: str) -> ANIPError:
    return ANIPError(
        "invalid_request",
        detail,
        resolution={
            "action": "fix_request_parameters",
            "recovery_class": "retry_now",
            "requires": detail,
            "grantable_by": None,
            "estimated_availability": None,
        },
        retry=True,
    )


def _not_found(detail: str) -> ANIPError:
    return ANIPError(
        "not_found",
        detail,
        resolution={
            "action": "revalidate_state",
            "recovery_class": "revalidate_then_retry",
            "requires": detail,
            "grantable_by": None,
            "estimated_availability": None,
            "recovery_target": {
                "kind": "revalidation",
                "target": {
                    "service": "studio-workbench",
                    "capability": "read_project_state",
                },
                "continuity": "same_task",
                "retry_after_target": True,
            },
        },
        retry=False,
    )


def _required_param(params: dict[str, Any], name: str) -> str:
    value = params.get(name)
    if not isinstance(value, str) or not value.strip():
        raise _invalid_request(f"{name} is required")
    return value.strip()


def _string_list(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    return [str(item).strip() for item in items if str(item).strip()]


def _normalized_words(text: str) -> list[str]:
    cleaned = []
    current = []
    for char in text.lower():
        if char.isalnum():
            current.append(char)
        else:
            if current:
                cleaned.append("".join(current))
                current = []
    if current:
        cleaned.append("".join(current))
    return cleaned


def _contains_any(words: set[str], *items: str) -> bool:
    return any(item in words for item in items)


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        key = item.strip()
        if key and key not in seen:
            seen.add(key)
            result.append(key)
    return result


def _string_value(value: Any, default: str) -> str:
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned:
            return cleaned
    return default


def _merged_string_list(value: Any, fallback: list[str], *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return fallback[:limit]
    merged = [str(item).strip() for item in value if str(item).strip()]
    return merged[:limit] or fallback[:limit]


def _merge_intent_interpretation(
    fallback: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    shape_type = str(candidate.get("recommended_shape_type", "")).strip().lower()
    if shape_type not in {"single_service", "multi_service"}:
        shape_type = fallback["recommended_shape_type"]

    return {
        "title": _string_value(candidate.get("title"), fallback["title"]),
        "summary": _string_value(candidate.get("summary"), fallback["summary"]),
        "recommended_shape_type": shape_type,
        "recommended_shape_reason": _string_value(
            candidate.get("recommended_shape_reason"),
            fallback["recommended_shape_reason"],
        ),
        "requirements_focus": _merged_string_list(
            candidate.get("requirements_focus"),
            fallback["requirements_focus"],
            limit=5,
        ),
        "scenario_starters": _merged_string_list(
            candidate.get("scenario_starters"),
            fallback["scenario_starters"],
            limit=5,
        ),
        "domain_concepts": _merged_string_list(
            candidate.get("domain_concepts"),
            fallback["domain_concepts"],
            limit=6,
        ),
        "service_suggestions": _merged_string_list(
            candidate.get("service_suggestions"),
            fallback["service_suggestions"],
            limit=5,
        ),
        "next_steps": _merged_string_list(
            candidate.get("next_steps"),
            fallback["next_steps"],
            limit=5,
        ),
    }


def _merge_explanation(
    fallback: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    return {
        "title": _string_value(candidate.get("title"), fallback["title"]),
        "summary": _string_value(candidate.get("summary"), fallback["summary"]),
        "focused_answer": _string_value(
            candidate.get("focused_answer"),
            fallback.get("focused_answer") or fallback["summary"],
        ),
        "highlights": _merged_string_list(candidate.get("highlights"), fallback["highlights"], limit=4),
        "watchouts": _merged_string_list(candidate.get("watchouts"), fallback["watchouts"], limit=4),
        "next_steps": _merged_string_list(candidate.get("next_steps"), fallback["next_steps"], limit=4),
    }


async def _interpret_project_intent(_: Any, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_param(params, "project_id")
    intent = _required_param(params, "intent")

    try:
        with get_pool().connection() as conn:
            project = get_project_detail(conn, project_id)
    except NotFoundError as exc:
        raise _not_found(f"{exc.entity} {exc.entity_id} does not exist") from exc

    words = set(_normalized_words(intent))
    project_name = project.get("name", project_id)
    consumer_mode = params.get("consumer_mode")
    consumer_mode = normalize_consumer_mode(str(consumer_mode).strip().lower()) if consumer_mode is not None else consumer_mode_from_labels(project.get("labels"))
    consumer_label = consumer_mode_label(consumer_mode)

    has_budget = _contains_any(words, "budget", "cost", "spend", "price", "pricing")
    has_approval = _contains_any(words, "approval", "approve", "approver", "escalate", "escalation")
    has_verification = _contains_any(words, "verify", "verification", "confirm", "confirmation", "reconcile")
    has_refresh = _contains_any(words, "refresh", "stale", "quote", "revalidate", "expiry", "expired")
    has_async = _contains_any(words, "async", "asynchronous", "later", "followup", "follow", "notification", "webhook")
    has_handoff = _contains_any(words, "handoff", "handoffs", "multi", "multiple", "estate", "services", "service")
    has_risk = _contains_any(words, "risk", "danger", "dangerous", "delete", "irreversible", "destructive")
    has_audit = _contains_any(words, "audit", "trace", "lineage", "history", "explain")

    recommended_shape_type = "single_service"
    if has_handoff or has_async or (has_approval and has_verification):
        recommended_shape_type = "multi_service"

    recommended_shape_reason = (
        "A multi-service shape is worth exploring because the brief implies handoffs, delayed follow-up, or clearly separable responsibilities."
        if recommended_shape_type == "multi_service"
        else "A single service is the best starting point because the brief reads like one tightly coupled responsibility that should stay easy to reason about."
    )

    requirements_focus: list[str] = []
    if has_budget:
        requirements_focus.append("Make cost visibility and over-budget behavior explicit before shaping the service.")
    if has_approval:
        requirements_focus.append("State clearly when the system should block, escalate, or require approval.")
    if has_verification:
        requirements_focus.append("Capture how completion should be verified instead of assuming success is enough.")
    if has_refresh:
        requirements_focus.append("Define what should happen when a stale quote, stale state, or expired input is encountered.")
    if has_risk:
        requirements_focus.append("Make destructive or high-risk actions explicit so authority and recovery posture are clear.")
    if has_audit:
        requirements_focus.append("Preserve lineage and explainability so later investigation does not depend on UI or prompt glue.")
    if not requirements_focus:
        requirements_focus.append("Start by defining what must always be true, what can block action, and what the system must explain afterward.")
    if consumer_mode == "agent_anip":
        requirements_focus.insert(0, "Bias the first design toward machine-usable capability boundaries, explicit blocked-action meaning, and low-glue ANIP consumption.")
    elif consumer_mode == "human_app":
        requirements_focus.insert(0, "Bias the first design toward a clear human-facing flow, understandable blocked states, and operator-friendly explanations.")
    else:
        requirements_focus.insert(0, "Bias the first design toward a hybrid flow where both people and ANIP consumers can follow the same bounded service logic.")

    scenario_starters: list[str] = [
        "Describe the normal success path that the service should handle cleanly."
    ]
    if has_budget:
        scenario_starters.append("Add a scenario where the action is over budget and the system must decide whether to block, escalate, or seek broader authority.")
    if has_approval:
        scenario_starters.append("Add a scenario where approval is required so the service shape can show where that responsibility should live.")
    if has_refresh:
        scenario_starters.append("Add a scenario where the required input is stale or expired and the system must refresh or revalidate before acting.")
    if has_verification:
        scenario_starters.append("Add a scenario where the system must verify the outcome after the initial action completes.")
    if has_async or has_handoff:
        scenario_starters.append("Add a follow-up or handoff scenario so the design is pressured across service boundaries, not only inside one request.")
    if consumer_mode == "agent_anip":
        scenario_starters.append("Add a scenario where an agent or tool must discover permissions, handle a blocked action, and continue without UI-only context.")
    elif consumer_mode == "human_app":
        scenario_starters.append("Add a scenario where a human needs the system to explain why work was blocked, delayed, or routed for review.")
    else:
        scenario_starters.append("Add a scenario where a person starts the work and an agent or tool continues it through a bounded handoff.")

    concept_map = {
        "flight": "Flight",
        "destination": "Destination",
        "booking": "Booking",
        "quote": "Quote",
        "approval": "Approval",
        "budget": "Budget",
        "payment": "Payment",
        "order": "Order",
        "invoice": "Invoice",
        "deployment": "Deployment",
        "cluster": "Cluster",
        "incident": "Incident",
        "customer": "Customer",
        "notification": "Notification",
        "policy": "Policy",
        "ticket": "Ticket",
    }
    domain_concepts = _unique([label for key, label in concept_map.items() if key in words])
    if not domain_concepts:
        domain_concepts = ["Primary business object", "Approval or control object", "Outcome or verification object"]

    service_suggestions: list[str] = []
    if recommended_shape_type == "single_service":
        service_suggestions.append("Start with one primary service that owns the main action and its control checks together.")
    else:
        service_suggestions.append("Keep the primary action in one service and separate approval, verification, or follow-up only where the brief clearly demands it.")
    if consumer_mode == "agent_anip":
        service_suggestions.append("Keep the machine-facing capability surface explicit so consumers do not have to recover workflow meaning from prompts or UI assumptions.")
    elif consumer_mode == "human_app":
        service_suggestions.append("Keep the first boundary legible for PMs, support, and operations instead of splitting the design earlier than the product needs.")
    else:
        service_suggestions.append("Treat the design as hybrid: keep the human workflow understandable while preserving ANIP-friendly capability and audit boundaries underneath.")
    if has_approval:
        service_suggestions.append("Consider an approval responsibility only if approvals need a distinct lifecycle or separate authority boundary.")
    if has_verification:
        service_suggestions.append("If verification is materially different from the initial action, treat it as a separate responsibility in the shape.")
    if has_refresh:
        service_suggestions.append("Make refresh or revalidation an explicit capability instead of hiding it inside UI or retry glue.")

    next_steps = [
        "Turn the requirements focus into the first requirements set.",
        "Capture two or three scenario starters that should pressure the design early.",
        f"Create a {'multi-service' if recommended_shape_type == 'multi_service' else 'single-service'} shape and assign the main domain concepts to it.",
        "Run evaluation after the first shape draft and use the result to tighten the boundaries.",
    ]

    summary = (
        f"This brief for {project_name} points toward a "
        f"{'multi-service' if recommended_shape_type == 'multi_service' else 'single-service'} starting shape. "
        f"It is being shaped primarily for {consumer_label.lower()}. "
        f"The main pressure points are {', '.join(item.split(' ')[0].lower() for item in requirements_focus[:3])}."
    )

    deterministic = {
        "title": f"Intent Interpretation: {project_name}",
        "summary": summary,
        "recommended_shape_type": recommended_shape_type,
        "recommended_shape_reason": recommended_shape_reason,
        "requirements_focus": requirements_focus[:5],
        "scenario_starters": scenario_starters[:5],
        "domain_concepts": domain_concepts[:6],
        "service_suggestions": service_suggestions[:5],
        "next_steps": next_steps,
    }

    model_result = await try_model_assistant_response(
        "interpret_project_intent",
        {
            "project": {
                "id": project_id,
                "name": project_name,
                "domain": project.get("domain"),
                "summary": project.get("summary"),
                "labels": project.get("labels") or [],
                "consumer_mode": consumer_mode,
            },
            "intent": intent,
            "deterministic_draft": deterministic,
        },
    )
    if model_result:
        return _merge_intent_interpretation(deterministic, model_result)
    return deterministic


def _focus_answer_from_question(question: str, *, summary: str, mappings: list[tuple[tuple[str, ...], list[str] | str]]) -> str | None:
    q = question.strip().lower()
    if not q:
        return None
    for keywords, answer in mappings:
        if any(keyword in q for keyword in keywords):
            if isinstance(answer, list):
                if answer:
                    return " ".join(answer[:3])
            elif answer:
                return answer
    return summary


async def _explain_shape(_: Any, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_param(params, "project_id")
    shape_id = _required_param(params, "shape_id")
    question = str(params.get("question", "") or "").strip()

    try:
        with get_pool().connection() as conn:
            project = get_project_detail(conn, project_id)
            shape = get_shape(conn, project_id, shape_id)
            requirements = get_requirements(conn, project_id, shape["requirements_id"])
    except NotFoundError as exc:
        raise _not_found(f"{exc.entity} {exc.entity_id} does not exist") from exc

    shape_data = shape["data"].get("shape", shape["data"])
    services = shape_data.get("services", [])
    coordination = shape_data.get("coordination", [])
    concepts = shape_data.get("domain_concepts", [])
    notes = _string_list(shape_data.get("notes", []))
    expectations = derive_contract_expectations(shape["data"], requirements["data"])

    type_label = "single-service" if shape_data.get("type") == "single_service" else "multi-service"
    project_name = project.get("name", project_id)
    shape_name = shape_data.get("name") or shape["title"]

    highlights: list[str] = [
        f"{shape_name} is a {type_label} design in {project_name}.",
        f"It currently defines {len(services)} service{'s' if len(services) != 1 else ''}, {len(concepts)} domain concept{'s' if len(concepts) != 1 else ''}, and {len(coordination)} coordination edge{'s' if len(coordination) != 1 else ''}.",
    ]
    if expectations:
        highlights.extend(
            f"Studio expects {item['surface']} because {item['reason']}."
            for item in expectations[:4]
        )
    elif services:
        highlights.append("This shape does not yet derive any explicit ANIP expectations from its current boundaries and requirements.")

    watchouts: list[str] = []
    if not services:
        watchouts.append("No services are defined yet, so this shape is not actionable.")
    if shape_data.get("type") == "multi_service" and not coordination:
        watchouts.append("This is marked as multi-service, but it does not yet describe how the services coordinate.")
    if not concepts:
        watchouts.append("No domain concepts are defined yet, so ownership and boundary reasoning will stay vague.")
    if not notes:
        watchouts.append("The shape does not yet record why these boundaries were chosen.")
    if any(not _string_list(service.get("capabilities", [])) for service in services):
        watchouts.append("At least one service has no listed capabilities yet, which makes the shape harder to evaluate.")

    next_steps: list[str] = []
    if not services:
        next_steps.append("Add the first service and state what it is responsible for.")
    if not concepts:
        next_steps.append("Add the main domain concepts so ownership and service boundaries become clearer.")
    if shape_data.get("type") == "multi_service" and not coordination:
        next_steps.append("Add coordination edges so the shape shows how work moves across services.")
    if not expectations:
        next_steps.append("Refine the shape until Studio can derive concrete ANIP expectations from it.")
    next_steps.append("Run evaluation against a key scenario after the next shape change.")

    summary = (
        f"This {type_label} shape is centered on {len(services)} service"
        f"{'s' if len(services) != 1 else ''}. "
        f"Studio currently derives {len(expectations)} expected ANIP exposure"
        f"{'s' if len(expectations) != 1 else ''} from the shape and requirements."
    )

    focused_answer = _focus_answer_from_question(
        question,
        summary=summary,
        mappings=[
            (("why", "decision", "choose"), notes or highlights),
            (("service", "boundary", "split"), highlights),
            (("concept", "entity", "domain"), [f"{concept.get('name', concept.get('id', 'concept'))} is owned by {concept.get('owner', 'shared')}." for concept in concepts]),
            (("anip", "protocol", "expose", "surface"), [f"{item['surface']}: {item['reason']}" for item in expectations]),
            (("risk", "approval", "authority"), [item["reason"] for item in expectations if item["surface"] == "authority_posture"] or watchouts),
            (("next", "change", "improve"), next_steps),
        ],
    )

    deterministic = {
        "title": f"Shape Explanation: {shape_name}",
        "summary": summary,
        "focused_answer": focused_answer,
        "highlights": highlights,
        "watchouts": watchouts,
        "next_steps": next_steps[:4],
    }

    model_result = await try_model_assistant_response(
        "explain_shape",
        {
            "project": {
                "id": project_id,
                "name": project_name,
            },
            "question": question,
            "shape": {
                "id": shape_id,
                "name": shape_name,
                "type": shape_data.get("type"),
                "services": services,
                "coordination": coordination,
                "domain_concepts": concepts,
                "notes": notes,
            },
            "requirements": requirements["data"],
            "derived_expectations": expectations,
            "deterministic_draft": deterministic,
        },
    )
    if model_result:
        return _merge_explanation(deterministic, model_result)
    return deterministic


def _evaluation_summary(result: str, handled: list[str], glue: list[str]) -> str:
    handled_count = len(handled)
    glue_count = len(glue)
    if result == "HANDLED":
        return (
            f"Result: {result}. This scenario is currently handled by the design. "
            f"Studio found {handled_count} handled area{'s' if handled_count != 1 else ''} and no required custom integration."
        )
    if result == "PARTIAL":
        return (
            f"Result: {result}. This scenario is partially supported. "
            f"Studio found {handled_count} handled area{'s' if handled_count != 1 else ''} and {glue_count} remaining integration gap{'s' if glue_count != 1 else ''}."
        )
    return (
        f"Result: {result}. This scenario still requires significant custom work. "
        f"Studio found {glue_count} integration gap{'s' if glue_count != 1 else ''} that the current design does not yet cover."
    )


async def _explain_evaluation(_: Any, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_param(params, "project_id")
    evaluation_id = _required_param(params, "evaluation_id")
    question = str(params.get("question", "") or "").strip()

    try:
        with get_pool().connection() as conn:
            project = get_project_detail(conn, project_id)
            evaluation_row = get_evaluation(conn, project_id, evaluation_id)
            scenario = get_scenario(conn, project_id, evaluation_row["scenario_id"])
    except NotFoundError as exc:
        raise _not_found(f"{exc.entity} {exc.entity_id} does not exist") from exc

    payload = evaluation_row["data"].get("evaluation", {})
    result = payload.get("result", evaluation_row.get("result", "REQUIRES_GLUE"))
    handled = _string_list(payload.get("handled_by_anip", []))
    glue = _string_list(payload.get("glue_you_will_still_write", []))
    why = _string_list(payload.get("why", []))
    improve = _string_list(payload.get("what_would_improve", []))
    notes = _string_list(payload.get("notes", []))

    project_name = project.get("name", project_id)
    scenario_name = scenario["data"].get("scenario", {}).get("name") or scenario["title"]

    highlights: list[str] = [
        f"{scenario_name} was evaluated inside {project_name} and returned {result}.",
    ]
    highlights.extend(why[:3] or handled[:3])

    watchouts: list[str] = []
    if evaluation_row.get("is_stale"):
        stale = evaluation_row.get("stale_artifacts", []) or ["linked artifacts"]
        watchouts.append(f"This explanation is based on a stale evaluation because {', '.join(stale)} changed.")
    watchouts.extend(glue[:3])
    if not watchouts and notes:
        watchouts.extend(notes[:2])

    next_steps = improve[:4]
    if not next_steps and glue:
        next_steps.append("Reduce or eliminate the remaining integration gaps before treating this scenario as covered.")
    if not next_steps:
        next_steps.append("Keep pressure-testing this shape with additional scenarios.")

    summary = _evaluation_summary(result, handled, glue)
    focused_answer = _focus_answer_from_question(
        question,
        summary=summary,
        mappings=[
            (("why", "decision", "result"), why or highlights),
            (("supported", "handled", "works"), handled or highlights),
            (("glue", "gap", "missing"), glue or watchouts),
            (("next", "change", "improve"), next_steps),
            (("risk", "concern", "watch"), watchouts),
        ],
    )

    deterministic = {
        "title": f"Evaluation Explanation: {scenario_name}",
        "summary": summary,
        "focused_answer": focused_answer,
        "highlights": highlights,
        "watchouts": watchouts,
        "next_steps": next_steps,
    }

    model_result = await try_model_assistant_response(
        "explain_evaluation",
        {
            "project": {
                "id": project_id,
                "name": project_name,
            },
            "question": question,
            "scenario": {
                "id": scenario["id"],
                "title": scenario["title"],
                "data": scenario["data"],
            },
            "evaluation": {
                "id": evaluation_id,
                "result": result,
                "handled_by_anip": handled,
                "glue_you_will_still_write": glue,
                "why": why,
                "what_would_improve": improve,
                "notes": notes,
                "is_stale": evaluation_row.get("is_stale", False),
                "stale_artifacts": evaluation_row.get("stale_artifacts", []),
            },
            "deterministic_draft": deterministic,
        },
    )
    if model_result:
        return _merge_explanation(deterministic, model_result)
    return deterministic


def _review_session_id(project_id: str, shape_id: str | None, scenario_id: str | None) -> str:
    shape_part = shape_id or "current-shape"
    scenario_part = scenario_id or "default-scenario"
    return f"review::{project_id}::{shape_part}::{scenario_part}"


async def _start_design_review_session(_: Any, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_param(params, "project_id")
    shape_id = str(params.get("shape_id", "") or "").strip() or None
    scenario_id = str(params.get("scenario_id", "") or "").strip() or None

    try:
        with get_pool().connection() as conn:
            project = get_project_detail(conn, project_id)
    except NotFoundError as exc:
        raise _not_found(f"{exc.entity} {exc.entity_id} does not exist") from exc

    project_name = project.get("name", project_id)
    session_id = _review_session_id(project_id, shape_id, scenario_id)
    review_focus = [
        "Explain the service boundary in PM-friendly language.",
        "Call out the most important handoff or verification point.",
        "Highlight one thing the PM should pressure next.",
    ]
    if scenario_id:
        review_focus.append("Keep the active scenario in view while reviewing the design.")

    return {
        "session_id": session_id,
        "title": f"Design Review Session: {project_name}",
        "summary": "A bounded continuation-style review session is ready. Use the session id to stream the walkthrough.",
        "review_focus": review_focus,
        "next_step": "Call stream_design_review with this session id to walk the design progressively.",
    }


async def _stream_design_review(ctx: Any, params: dict[str, Any]) -> dict[str, Any]:
    project_id = _required_param(params, "project_id")
    session_id = _required_param(params, "session_id")
    question = str(params.get("question", "") or "").strip()

    parts = session_id.split("::")
    if len(parts) != 4 or parts[0] != "review":
        raise _invalid_request("session_id must come from start_design_review_session")
    _, session_project_id, shape_part, scenario_part = parts
    if session_project_id != project_id:
        raise _invalid_request("session_id does not belong to the provided project_id")

    try:
        with get_pool().connection() as conn:
            project = get_project_detail(conn, project_id)
    except NotFoundError as exc:
        raise _not_found(f"{exc.entity} {exc.entity_id} does not exist") from exc

    project_name = project.get("name", project_id)
    highlights = [
        "The review keeps the current design bounded to one clear PM-facing walkthrough.",
        "Cross-service boundaries remain explicit instead of being hidden in assistant prose.",
        "The next step should come out of evaluation pressure, not from ad hoc guesswork.",
    ]
    if shape_part != "current-shape":
        highlights.insert(0, f"The walkthrough is anchored to shape {shape_part}.")
    if scenario_part != "default-scenario":
        highlights.append(f"The walkthrough keeps scenario {scenario_part} in view.")

    next_steps = [
        "Test the current design against a real scenario after this review.",
        "Capture what needs to change before widening the service boundary.",
        "Keep the shared business and engineering artifacts aligned with the reviewed design.",
    ]
    if question:
        next_steps.insert(0, f"Address the focus question directly: {question}")

    progress_events = [
        {"stage": "context", "message": f"Loading review context for {project_name}."},
        {"stage": "boundary", "message": "Explaining the current service boundary and why it exists."},
        {"stage": "next", "message": "Summarizing the next product decision to pressure."},
    ]
    for payload in progress_events:
        await ctx.emit_progress(payload)
        await asyncio.sleep(0.01)

    return {
        "session_id": session_id,
        "summary": f"Review complete for {project_name}. The design is ready for scenario pressure with a continuation-style review trail.",
        "highlights": highlights,
        "next_steps": next_steps,
    }
