"""Configurable model provider support for the Studio assistant.

This module keeps provider selection and HTTP specifics out of the main
assistant service. The assistant can stay capability-bounded and deterministic
at its core while optionally using a configured model provider for
interpretation and explanation.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import os
from typing import Any

import httpx
from psycopg.types.json import Json

from .db import get_pool


_ASSISTANT_CONFIG_KEY = "assistant_runtime_config"
_DEFAULT_TIMEOUT_SECONDS = 240.0
_TRANSIENT_PROVIDER_ATTEMPTS = 2
_TRANSIENT_PROVIDER_BACKOFF_SECONDS = 3.0


@dataclass(frozen=True)
class AssistantProviderConfig:
    provider: str
    model: str | None
    base_url: str | None
    api_key: str | None
    temperature: float
    timeout_seconds: float
    strict: bool


@dataclass(frozen=True)
class AssistantProviderResolution:
    config: AssistantProviderConfig
    provider_source: str
    model_source: str
    base_url_source: str
    api_key_source: str
    temperature_source: str
    timeout_seconds_source: str
    strict_source: str
    stored_api_key_configured: bool


def load_assistant_provider_config() -> AssistantProviderConfig:
    return load_assistant_provider_resolution().config


def load_assistant_provider_resolution() -> AssistantProviderResolution:
    stored = load_persisted_assistant_provider_settings()

    env_provider_raw, env_provider_present = _env_string("STUDIO_ASSISTANT_PROVIDER")
    stored_provider = _normalize_provider(stored.get("provider"))
    provider = _normalize_provider(env_provider_raw if env_provider_present else stored_provider)
    provider_source = "env" if env_provider_present else ("stored" if stored_provider else "default")

    env_model, env_model_present = _env_string("STUDIO_ASSISTANT_MODEL")
    stored_model = _normalize_optional_string(stored.get("model"))
    model = env_model if env_model_present else stored_model
    model_source = "env" if env_model_present else ("stored" if stored_model else "default")

    env_base_url, env_base_url_present = _env_string("STUDIO_ASSISTANT_BASE_URL")
    stored_base_url = _normalize_optional_string(stored.get("base_url"))
    base_url = env_base_url if env_base_url_present else stored_base_url
    base_url_source = "env" if env_base_url_present else ("stored" if stored_base_url else "default")

    api_key, api_key_source, stored_api_key_configured = _resolve_provider_api_key(provider, stored)

    env_temperature, env_temperature_present = _env_float("STUDIO_ASSISTANT_TEMPERATURE")
    stored_temperature = _normalize_float(stored.get("temperature"))
    temperature = env_temperature if env_temperature_present else (stored_temperature if stored_temperature is not None else 0.2)
    temperature_source = "env" if env_temperature_present else ("stored" if stored_temperature is not None else "default")

    env_timeout, env_timeout_present = _env_float("STUDIO_ASSISTANT_TIMEOUT_SECONDS")
    stored_timeout = _normalize_float(stored.get("timeout_seconds"))
    timeout_seconds = env_timeout if env_timeout_present else (stored_timeout if stored_timeout is not None else _DEFAULT_TIMEOUT_SECONDS)
    timeout_seconds_source = "env" if env_timeout_present else ("stored" if stored_timeout is not None else "default")

    strict = True
    strict_source = "fixed"

    return AssistantProviderResolution(
        config=AssistantProviderConfig(
            provider=provider,
            model=model,
            base_url=base_url,
            api_key=api_key,
            temperature=temperature,
            timeout_seconds=timeout_seconds,
            strict=strict,
        ),
        provider_source=provider_source,
        model_source=model_source,
        base_url_source=base_url_source,
        api_key_source=api_key_source,
        temperature_source=temperature_source,
        timeout_seconds_source=timeout_seconds_source,
        strict_source=strict_source,
        stored_api_key_configured=stored_api_key_configured,
    )


def load_persisted_assistant_provider_settings() -> dict[str, Any]:
    try:
        with get_pool().connection() as conn:
            row = conn.execute(
                "SELECT value FROM studio_settings WHERE key = %s",
                (_ASSISTANT_CONFIG_KEY,),
            ).fetchone()
    except Exception:
        return {}
    if not row:
        return {}
    value = row.get("value")
    return value if isinstance(value, dict) else {}


def save_persisted_assistant_provider_settings(update: dict[str, Any]) -> dict[str, Any]:
    current = load_persisted_assistant_provider_settings()
    next_value = dict(current)

    if "provider" in update:
        next_value["provider"] = _normalize_provider(update.get("provider"))
    if "model" in update:
        next_value["model"] = _normalize_optional_string(update.get("model"))
    if "base_url" in update:
        next_value["base_url"] = _normalize_optional_string(update.get("base_url"))
    if "temperature" in update:
        next_value["temperature"] = _normalize_float(update.get("temperature"))
    if "timeout_seconds" in update:
        next_value["timeout_seconds"] = _normalize_float(update.get("timeout_seconds"))
    next_value.pop("strict", None)
    if "api_key" in update:
        next_value["api_key"] = _normalize_optional_string(update.get("api_key"))
    if update.get("clear_api_key"):
        next_value["api_key"] = None

    with get_pool().connection() as conn:
        conn.execute(
            "INSERT INTO studio_settings (key, value) VALUES (%s, %s)"
            " ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()",
            (_ASSISTANT_CONFIG_KEY, Json(next_value)),
        )
        conn.commit()
    return load_persisted_assistant_provider_settings()


def studio_read_only_enabled() -> bool:
    env_value, present = _env_bool("STUDIO_READ_ONLY")
    return env_value if present else False


def studio_read_only_reason() -> str | None:
    if not studio_read_only_enabled():
        return None
    return (
        _normalize_optional_string(os.getenv("STUDIO_READ_ONLY_REASON"))
        or "Studio is running in read-only mode. Explore the design, then download and run Studio locally to make changes."
    )


async def try_model_assistant_response(capability: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    config = load_assistant_provider_config()
    if config.provider in {"", "deterministic", "none", "off"}:
        return None

    if config.provider in {"openai", "ollama"}:
        return await _invoke_openai_compatible(config, capability, payload)
    if config.provider == "anthropic":
        return await _invoke_anthropic(config, capability, payload)
    raise ValueError(f"Unsupported STUDIO_ASSISTANT_PROVIDER: {config.provider}")


def _resolve_provider_api_key(provider: str, stored: dict[str, Any]) -> tuple[str | None, str, bool]:
    explicit, explicit_present = _env_string("STUDIO_ASSISTANT_API_KEY")
    if explicit_present and explicit:
        return explicit, "env", bool(_normalize_optional_string(stored.get("api_key")))
    if provider == "openai":
        openai_key, openai_present = _env_string("OPENAI_API_KEY")
        if openai_present and openai_key:
            return openai_key, "env", bool(_normalize_optional_string(stored.get("api_key")))
    if provider == "anthropic":
        anthropic_key, anthropic_present = _env_string("ANTHROPIC_API_KEY")
        if anthropic_present and anthropic_key:
            return anthropic_key, "env", bool(_normalize_optional_string(stored.get("api_key")))
    stored_key = _normalize_optional_string(stored.get("api_key"))
    if stored_key:
        return stored_key, "stored", True
    return None, "none", False


def _normalize_provider(value: Any) -> str:
    normalized = _normalize_optional_string(value)
    return normalized.lower() if normalized else "deterministic"


def _normalize_optional_string(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _normalize_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _env_string(name: str) -> tuple[str | None, bool]:
    if name not in os.environ:
        return None, False
    return _normalize_optional_string(os.environ.get(name)), True


def _env_float(name: str) -> tuple[float, bool]:
    if name not in os.environ:
        return 0.0, False
    return _safe_float(os.environ.get(name), default=0.0), True


def _env_bool(name: str) -> tuple[bool, bool]:
    if name not in os.environ:
        return False, False
    return (os.getenv(name) or "").strip().lower() in {"1", "true", "yes", "on"}, True


def _safe_float(raw: str | None, *, default: float) -> float:
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _system_prompt(capability: str) -> str:
    base = (
        "You are the Studio assistant inside ANIP Studio. "
        "You help interpret product intent and explain design decisions. "
        "Return only valid JSON with the exact fields requested. "
        "Do not wrap the JSON in markdown. "
        "Keep language concise, PM-readable, and concrete."
    )
    if capability == "interpret_project_intent":
        return (
            base
            + " Prefer recommendation language over certainty. "
              "Treat your output as a proposed first draft, not as final truth."
        )
    if capability == "clarify_design_section":
        return (
            base
            + " Return only the minimal clarification set for the requested section. "
              "Do not broaden the scope into a full draft or a full-project questionnaire."
        )
    if capability in {
        "propose_requirements",
        "propose_scenarios",
        "propose_business_summary",
        "propose_actor_model",
        "propose_business_areas",
        "propose_permission_intent",
        "propose_non_goals",
        "propose_success_criteria",
        "propose_service_design",
        "propose_capability_formalization",
        "propose_runtime_policy_bindings",
        "propose_input_contracts",
        "propose_verification_expectations",
        "propose_backend_bindings",
        "identify_missing_business_info",
    }:
        return (
            base
            + " Return structured proposal output only. "
              "Treat the response as review material that must be accepted explicitly before persistence. "
              "Do not imply that anything has already been saved. "
              "If deterministic_draft is present, treat it only as a fallback schema/reference, not as content to copy. "
              "Do not copy fallback identifiers, role names, service names, or capability names from deterministic_draft unless they are supported by the source text. "
              "Prefer source-specific terminology whenever the source text contains concrete actors, domains, systems, or workflows."
        )
    if capability == "suggest_next_step":
        return (
            base
            + " Return a single bounded next-step recommendation based on the current deterministic Studio state. "
              "Do not invent project status that is not present in the context. "
              "Prefer the highest-leverage immediate action over long roadmaps."
        )
    if capability == "analyze_agent_consumption_simulation":
        return (
            base
            + " Analyze saved simulator evidence as feedback for PM/dev review. "
              "Separate contract fixes, reviewed app-glue fixes, service behavior fixes, and acceptable limitations. "
              "Do not mutate artifacts, do not claim runtime proof, and do not hide domain-specific behavior in generic runtime guidance."
        )
    if capability in {"rewrite_business_brief", "rewrite_engineering_contract"}:
        return (
            base
            + " Rewrite the provided deterministic draft into a more readable, polished document for humans. "
              "Preserve the underlying facts, constraints, and conclusions. "
              "Do not invent architecture, policy, or results that are not already present in the context."
        )
    return base + " Explain clearly, but do not invent facts not supported by the provided context."


def _user_prompt(capability: str, payload: dict[str, Any]) -> str:
    if capability == "interpret_project_intent":
        return (
            "Create a first-pass Studio interpretation for this project brief.\n"
            "Return JSON with exactly these fields:\n"
            "- title\n"
            "- summary\n"
            "- recommended_shape_type (single_service or multi_service)\n"
            "- recommended_shape_reason\n"
            "- requirements_focus (array of strings)\n"
            "- scenario_starters (array of strings)\n"
            "- domain_concepts (array of strings)\n"
            "- service_suggestions (array of strings)\n"
            "- next_steps (array of strings)\n\n"
            f"Context:\n{json.dumps(payload, indent=2)}"
        )

    if capability == "propose_requirements":
        return (
            "Draft PM-facing requirement proposal blocks from the supplied business brief.\n"
            "Return JSON with exactly these fields:\n"
            "- title\n"
            "- summary\n"
            "- mode\n"
            "- capability\n"
            "- questions_for_user (array of strings)\n"
            "- watchouts (array of strings)\n"
            "- next_steps (array of strings)\n"
            "- proposal (object)\n\n"
            "The proposal object must contain:\n"
            "- proposal_kind = candidate_blocks\n"
            "- artifact_type = requirements\n"
            "- items (array of objects with client_id, title, body, confidence, rationale)\n\n"
            f"Context:\n{json.dumps(payload, indent=2)}"
        )

    if capability == "propose_scenarios":
        return (
            "Draft PM-facing scenario proposal blocks from the supplied business brief.\n"
            "Return JSON with exactly these fields:\n"
            "- title\n"
            "- summary\n"
            "- mode\n"
            "- capability\n"
            "- questions_for_user (array of strings)\n"
            "- watchouts (array of strings)\n"
            "- next_steps (array of strings)\n"
            "- proposal (object)\n\n"
            "The proposal object must contain:\n"
            "- proposal_kind = candidate_blocks\n"
            "- artifact_type = scenarios\n"
            "- items (array of objects with client_id, title, body, confidence, rationale, structured_data)\n\n"
            "Each scenario item should include structured_data.scenario with concrete name, category, narrative, actor_context, business_scope, time_scope, primary_capability, participating_services, orchestration_steps, expected_behavior, and expected_anip_support. "
            "If the brief does not support concrete values, ask targeted questions instead of filling vague placeholders.\n\n"
            f"Context:\n{json.dumps(payload, indent=2)}"
        )

    if capability == "propose_business_summary":
        return (
            "Draft PM-facing business summary patch proposals from the supplied business brief.\n"
            "Return JSON with exactly these fields:\n"
            "- title\n"
            "- summary\n"
            "- mode\n"
            "- capability\n"
            "- questions_for_user (array of strings)\n"
            "- watchouts (array of strings)\n"
            "- next_steps (array of strings)\n"
            "- proposal (object)\n\n"
            "The proposal object must contain:\n"
            "- proposal_kind = patch_candidates\n"
            "- artifact_type = product_summary\n"
            "- patches (array of objects with path, op, value, rationale)\n\n"
            "The patches must make the Product Summary lockable when the source supports it. Include concrete patches for these required fields whenever they can be inferred from the brief: "
            "/product_purpose, /business_problem, /business_goals, /supported_question_families, /governed_behavior_summary, and /approval_posture_summary. "
            "/supported_question_families must be an array of stable user question/task families the product should answer, for example risk review, forecast summary, enrichment summary, routing recommendation, or outreach draft. "
            "If the brief does not support a concrete value for a required field, return targeted questions instead of silently omitting that field.\n\n"
            f"Context:\n{json.dumps(payload, indent=2)}"
        )

    if capability == "propose_actor_model":
        return (
            "Draft PM-facing actor model patch proposals from the supplied business brief.\n"
            "Return JSON with exactly these fields:\n"
            "- title\n"
            "- summary\n"
            "- mode\n"
            "- capability\n"
            "- questions_for_user (array of strings)\n"
            "- watchouts (array of strings)\n"
            "- next_steps (array of strings)\n"
            "- proposal (object)\n\n"
            "The proposal object must contain:\n"
            "- proposal_kind = patch_candidates\n"
            "- artifact_type = actor_model\n"
            "- patches (array of objects with path, op, value, rationale)\n\n"
            "If the brief names actor ids or actor families, preserve those exact ids in /actors/- patch values. "
            "Do not replace source-declared actors with generic placeholders such as primary_operator or reviewing_manager. "
            "Do not use outcome, permission, or policy terms as actor ids; values such as approval_required, denied, restricted, bounded_result, or approval_stop are not actors. "
            "Each actor value should include actor_id, title, summary, visibility_expectations, action_expectations, approval_expectations, and notes. "
            "If approval authority differs by action type but the source is unclear, include targeted questions_for_user instead of inventing authority.\n\n"
            f"Context:\n{json.dumps(payload, indent=2)}"
        )

    if capability == "propose_business_areas":
        return (
            "Draft PM-facing business areas patch proposals from the supplied business brief.\n"
            "Return JSON with exactly these fields:\n"
            "- title\n"
            "- summary\n"
            "- mode\n"
            "- capability\n"
            "- questions_for_user (array of strings)\n"
            "- watchouts (array of strings)\n"
            "- next_steps (array of strings)\n"
            "- proposal (object)\n\n"
            "The proposal object must contain:\n"
            "- proposal_kind = patch_candidates\n"
            "- artifact_type = business_areas\n"
            "- patches (array of objects with path, op, value, rationale)\n\n"
            f"Context:\n{json.dumps(payload, indent=2)}"
        )

    if capability == "propose_permission_intent":
        return (
            "Draft PM-facing permission intent patch proposals from the supplied business brief.\n"
            "Return JSON with exactly these fields:\n"
            "- title\n"
            "- summary\n"
            "- mode\n"
            "- capability\n"
            "- questions_for_user (array of strings)\n"
            "- watchouts (array of strings)\n"
            "- next_steps (array of strings)\n"
            "- proposal (object)\n\n"
            "The proposal object must contain:\n"
            "- proposal_kind = patch_candidates\n"
            "- artifact_type = permission_intent\n"
            "- patches (array of objects with path, op, value, rationale)\n\n"
            "Permission rule values must be schema-valid:\n"
            "- actor_id must be one of context.canonical_product_vocabulary.actor_ids when that list is non-empty\n"
            "- business_area must be one of context.canonical_product_vocabulary.business_area_ids when that list is non-empty\n"
            "- access_posture must be one of allowed, bounded, restricted, denied, approval_required\n"
            "- governed_outcome_type must be one of direct_result, bounded_result, masked_or_restricted_result, deny_request, approval_stop, clarification_required\n"
            "- do not invent new actor ids or business-area ids in Permission Intent; ask a clarification question instead if the canonical vocabulary is insufficient\n\n"
            "Avoid generic ownership placeholders unless those exact terms appear in source text. "
            "Use source-declared actor ids, business-area ids, and concrete governed outcomes.\n\n"
            f"Context:\n{json.dumps(payload, indent=2)}"
        )

    if capability == "propose_non_goals":
        return (
            "Draft PM-facing non-goal patch proposals from the supplied business brief.\n"
            "Return JSON with exactly these fields:\n"
            "- title\n"
            "- summary\n"
            "- mode\n"
            "- capability\n"
            "- questions_for_user (array of strings)\n"
            "- watchouts (array of strings)\n"
            "- next_steps (array of strings)\n"
            "- proposal (object)\n\n"
            "The proposal object must contain:\n"
            "- proposal_kind = patch_candidates\n"
            "- artifact_type = non_goals\n"
            "- patches (array of objects with path, op, value, rationale)\n\n"
            f"Context:\n{json.dumps(payload, indent=2)}"
        )

    if capability == "propose_success_criteria":
        return (
            "Draft PM-facing success criteria patch proposals from the supplied business brief.\n"
            "Return JSON with exactly these fields:\n"
            "- title\n"
            "- summary\n"
            "- mode\n"
            "- capability\n"
            "- questions_for_user (array of strings)\n"
            "- watchouts (array of strings)\n"
            "- next_steps (array of strings)\n"
            "- proposal (object)\n\n"
            "The proposal object must contain:\n"
            "- proposal_kind = patch_candidates\n"
            "- artifact_type = success_criteria\n"
            "- patches (array of objects with path, op, value, rationale)\n\n"
            f"Context:\n{json.dumps(payload, indent=2)}"
        )

    if capability == "propose_service_design":
        return (
            "Draft developer-facing service design proposal blocks from the supplied locked-baseline context.\n"
            "Return JSON with exactly these fields:\n"
            "- title\n"
            "- summary\n"
            "- mode\n"
            "- capability\n"
            "- questions_for_user (array of strings)\n"
            "- watchouts (array of strings)\n"
            "- next_steps (array of strings)\n"
            "- proposal (object)\n\n"
            "The proposal object must contain:\n"
            "- proposal_kind = candidate_blocks\n"
            "- artifact_type = service_design\n"
            "- items (array of objects with client_id, title, body, confidence, rationale, structured_data)\n\n"
            "At least one item should include structured_data.shape with name, type, notes, services, coordination, and domain_concepts. "
            "Each service must include id, name, role, responsibilities, capabilities, and owns_concepts. "
            "Honor service_topology_preference when present. If target_service_count is set, structured_data.shape.services must contain exactly that many services by consolidating or splitting responsibilities at that requested granularity. "
            "If preserve_source_services is true or source_shape_services is provided without a target count, preserve those source service boundaries instead of inventing a new service count. "
            "If source_declared_service_id_candidates is non-empty, treat those ids as candidate canonical service ids requiring PM/dev confirmation. Prefer exact copied ids over paraphrased service ids when the source clearly declares the service boundary. "
            "If source_declared_capability_id_candidates is non-empty, treat those ids as candidate canonical ids requiring PM/dev confirmation. Prefer exact copied ids over paraphrases when ownership is clear, but ask a question or leave review notes when ownership is ambiguous; do not assign every candidate to every service. "
            "For governed fronting/API/MCP projects, Product Service Design must describe the public governed capability surface only. Do not create internal adapter, backend, execution, or raw-tool capability ids such as *.adapter.*, *.execution.*, or *.backend.* as public service capabilities; those belong in Developer Design backend evidence. "
            "A capability id may have only one owning service. Never copy one service's capability list to all services. If a service boundary has clear responsibilities but no explicit canonical ids, draft a small candidate capability surface using canonical dot-separated ids derived from the service namespace and responsibility verbs/nouns; add watchouts/questions that these inferred ids require PM/dev confirmation. Leave a service capabilities array empty only when both the boundary and its responsibilities are too vague to name safely. "
            "Use names inferred from the source baseline, not generic placeholders like handle_primary_action.\n\n"
            f"Context:\n{json.dumps(payload, indent=2)}"
        )

    if capability == "propose_capability_formalization":
        return (
            "Draft developer-facing capability formalization proposal blocks from the supplied locked-baseline context.\n"
            "Return JSON with exactly these fields:\n"
            "- title\n"
            "- summary\n"
            "- mode\n"
            "- capability\n"
            "- questions_for_user (array of strings)\n"
            "- watchouts (array of strings)\n"
            "- next_steps (array of strings)\n"
            "- proposal (object)\n\n"
            "The proposal object must contain:\n"
            "- proposal_kind = candidate_blocks\n"
            "- artifact_type = capability_formalization\n"
            "- items (array of objects with client_id, title, body, confidence, rationale, structured_data)\n\n"
            "When possible include structured_data.capabilities as concrete capability contracts with service_id, capability_id, title, summary, intent_type, operation_type, side_effect_level, backend_operation, output_shape, entity_targeted, subject_kind, context_type, output_intent, and inputs. "
            "If canonical_capability_inventory is present, structured_data.capabilities must include exactly one concrete capability contract for every inventory entry, using the exact service_id and capability_id from that inventory. Do not summarize, sample, collapse, or omit inventory entries. "
            "If a reviewed developer/interface inventory entry includes inputs, preserve every input exactly: input_name, input_type, required flag, allowed_values, default, semantic_type, and entity_reference. Do not rename reviewed runtime fields such as owner_scope to region_scope, cohort_ref to cohort, target_ref to target, target_queue to routing_target, account_names to account_scope, or source_window to any inferred field. "
            "If source_declared_service_id_candidates is non-empty, prefer those exact service ids for service_id values when matching source-declared capabilities to owners. "
            "If source_declared_capability_id_candidates is non-empty, treat those ids as candidate canonical ids requiring PM/dev confirmation. Prefer exact copied ids over paraphrases when the source clearly defines the capability, and flag ambiguous or duplicate paraphrased ids for review instead of hiding the ambiguity. "
            "Do not emit placeholder capability contracts. Avoid placeholder summaries, review_needed backend operations, review_needed output shapes, TBD values, or text like 'needs explicit ...'. If the source is insufficient for a concrete contract, ask targeted questions and omit that structured capability until the missing information is supplied. "
            "Every source-declared canonical capability must have concrete input contract details. Include at least one structured input with input_name, input_type, required, and summary unless the source explicitly says the capability has no inputs. "
            "When the locked-baseline context includes an implementation or custom-code-bundle surface, treat its capability ids, input names, required flags, defaults, and allowed values as source-owned runtime surface. Keep those machine names exactly in capability inputs; put friendlier wording only in summaries, semantic_aliases, or normalization hints. Do not make an optional/defaulted implementation input required unless the source explicitly says the runtime must clarify instead of using the default. "
            "Classify side effects from explicit source evidence about allowed behavior, approval stops, mutation boundaries, produced effects, and forbidden effects; do not infer execution authority from capability names alone. "
            "Every capability must include business_effects.produces and business_effects.does_not_produce. Approval/write-capable capabilities must include grant_policy. "
            "When emitting business_effects, use only these canonical effect IDs: content.draft, content.summary, content.recommendation, data.read, data.aggregate, data.export, raw_data_export, raw_model_features, system.preview_mutation, system.mutation, external_dispatch, approval.request, approval.execute. Do not invent near-synonyms such as content.rationale, external_send, or raw_conversation_export; choose the nearest canonical ID or ask a question if none fits. "
            "If kind is composed, include contract-level composition metadata: authority_boundary, ordered steps, input_mapping, output_mapping, failure_policy, and audit_policy. If the source does not establish the child steps or mappings, ask targeted questions and do not emit a composed shell. "
            "Inputs should include input_name, input_type, required, summary, allowed_values, entity_reference, semantic_aliases, normalization_hint, context_type, and output_intent where applicable. "
            "If agent_consumption_simulation is present, use failed probes as evidence for reviewable capability, input, approval, unsupported-effect, or app-glue fixes; do not suggest package-specific hardcoding in generic runtime.\n\n"
            f"Context:\n{json.dumps(payload, indent=2)}"
        )

    if capability == "propose_runtime_policy_bindings":
        return (
            "Draft developer-facing runtime policy binding proposal blocks from the supplied locked-baseline context.\n"
            "Return JSON with exactly these fields:\n"
            "- title\n"
            "- summary\n"
            "- mode\n"
            "- capability\n"
            "- questions_for_user (array of strings)\n"
            "- watchouts (array of strings)\n"
            "- next_steps (array of strings)\n"
            "- proposal (object)\n\n"
            "The proposal object must contain:\n"
            "- proposal_kind = candidate_blocks\n"
            "- artifact_type = runtime_policy_bindings\n"
            "- items (array of objects with client_id, title, body, confidence, rationale)\n\n"
            f"Context:\n{json.dumps(payload, indent=2)}"
        )

    if capability == "propose_input_contracts":
        return (
            "Draft developer-facing input contract proposal blocks from the supplied locked-baseline context.\n"
            "Surface questions the PM/dev must answer when source material does not clearly classify an input.\n"
            "Do not guess from field names alone. Required inputs need reviewed metadata such as semantic_type, entity_reference, input_format, validation_pattern, allowed_values, defaults, and clarification_hint.\n"
            "Return JSON with exactly these fields:\n"
            "- title\n"
            "- summary\n"
            "- mode\n"
            "- capability\n"
            "- questions_for_user (array of strings)\n"
            "- watchouts (array of strings)\n"
            "- next_steps (array of strings)\n"
            "- proposal (object)\n\n"
            "The proposal object must contain:\n"
            "- proposal_kind = candidate_blocks\n"
            "- artifact_type = input_contracts\n"
            "- items (array of objects with client_id, title, body, confidence, rationale, structured_data)\n\n"
            "For every source-declared capability that has a concrete runtime contract, include structured_data.capabilities.\n"
            "If input_contract_focus.capability_ids is present, return contracts only for those capability ids and include every id in that list.\n"
            "If canonical_capability_inventory is present, structured_data.capabilities must include exactly one entry for every inventory entry, using the exact capability_id from that inventory.\n"
            "For canonical inventory entries, do not emit empty inputs unless that inventory entry explicitly says the capability has no inputs.\n"
            "Each capability entry must contain capability_id and inputs.\n"
            "Each input entry must contain input_name, input_type, required, and summary.\n"
            "When known, also include semantic_type, entity_reference, allowed_values, default_value, clarification_hint, resolution, and catalog_ref.\n"
            "If the source does not contain enough evidence to define inputs for a capability, do not invent a silent placeholder; add a precise question_for_user instead.\n\n"
            f"Context:\n{json.dumps(payload, indent=2)}"
        )

    if capability == "propose_verification_expectations":
        return (
            "Draft developer-facing verification expectation proposal blocks from the supplied locked-baseline context.\n"
            "Return JSON with exactly these fields:\n"
            "- title\n"
            "- summary\n"
            "- mode\n"
            "- capability\n"
            "- questions_for_user (array of strings)\n"
            "- watchouts (array of strings)\n"
            "- next_steps (array of strings)\n"
            "- proposal (object)\n\n"
            "The proposal object must contain:\n"
            "- proposal_kind = candidate_blocks\n"
            "- artifact_type = verification_expectations\n"
            "- items (array of objects with client_id, title, body, confidence, rationale)\n\n"
            f"Context:\n{json.dumps(payload, indent=2)}"
        )

    if capability == "propose_backend_bindings":
        return (
            "Draft developer-facing backend binding proposal blocks from the supplied locked-baseline context.\n"
            "Return JSON with exactly these fields:\n"
            "- title\n"
            "- summary\n"
            "- mode\n"
            "- capability\n"
            "- questions_for_user (array of strings)\n"
            "- watchouts (array of strings)\n"
            "- next_steps (array of strings)\n"
            "- proposal (object)\n\n"
            "The proposal object must contain:\n"
            "- proposal_kind = candidate_blocks\n"
            "- artifact_type = backend_bindings\n"
            "- items (array of objects with client_id, title, body, confidence, rationale)\n\n"
            f"Context:\n{json.dumps(payload, indent=2)}"
        )

    if capability == "propose_governed_fronting_capabilities":
        return (
            "Draft review-only governed ANIP capability candidates in front of selected native API, MCP, database, or hybrid backend operations.\n"
            "Do not expose every raw backend operation directly. Curate a small governed behavior surface with explicit semantic inputs and governance.\n"
            "Return JSON with exactly these fields:\n"
            "- title\n"
            "- summary\n"
            "- mode\n"
            "- capability\n"
            "- questions_for_user (array of strings)\n"
            "- watchouts (array of strings)\n"
            "- next_steps (array of strings)\n"
            "- proposal (object)\n\n"
            "The proposal object must contain:\n"
            "- proposal_kind = candidate_blocks\n"
            "- artifact_type = governed_fronting_capabilities\n"
            "- items (array of objects with client_id, title, body, confidence, rationale, structured_data)\n\n"
            "Each item.structured_data must contain:\n"
            "- capability_id\n"
            "- service_id\n"
            "- service_name\n"
            "- intent\n"
            "- backend_bindings (array with backend_kind, connection_ref, raw_operation_refs, backend_input_mode)\n"
            "- required_inputs (array)\n"
            "- optional_inputs (array)\n"
            "- execution_posture\n"
            "- side_effect_level\n"
            "- approval_rule_refs (array)\n"
            "- denial_rule_refs (array)\n"
            "- clarification_rule_refs (array)\n"
            "- outbound_controls (object)\n"
            "- verification_scenarios (array)\n\n"
            "Keep credentials, tokens, and provider secrets out of the proposal. Reference connection IDs only.\n\n"
            f"Context:\n{json.dumps(payload, indent=2)}"
        )

    if capability == "clarify_design_section":
        return (
            "Return targeted clarification questions for exactly one design section.\n"
            "Return JSON with exactly these fields:\n"
            "- title\n"
            "- summary\n"
            "- mode\n"
            "- capability\n"
            "- questions_for_user (array of strings)\n"
            "- watchouts (array of strings)\n"
            "- next_steps (array of strings)\n"
            "- proposal (object)\n\n"
            "The proposal object must contain:\n"
            "- proposal_kind = clarification_questions\n"
            "- questions (array of objects with question_id, prompt, why_it_matters, target_artifact)\n\n"
            "Keep the question set narrow and section-specific.\n\n"
            f"Context:\n{json.dumps(payload, indent=2)}"
        )

    if capability == "identify_missing_business_info":
        return (
            "Identify the missing business decisions that should be clarified before PM design is treated as stable.\n"
            "Return JSON with exactly these fields:\n"
            "- title\n"
            "- summary\n"
            "- mode\n"
            "- capability\n"
            "- questions_for_user (array of strings)\n"
            "- watchouts (array of strings)\n"
            "- next_steps (array of strings)\n"
            "- proposal (object)\n\n"
            "The proposal object must contain:\n"
            "- proposal_kind = clarification_questions\n"
            "- questions (array of objects with question_id, prompt, why_it_matters, target_artifact)\n\n"
            f"Context:\n{json.dumps(payload, indent=2)}"
        )

    if capability == "suggest_next_step":
        return (
            "Suggest the single best next Studio action from the supplied deterministic project state.\n"
            "Return JSON with exactly these fields:\n"
            "- title\n"
            "- summary\n"
            "- focused_answer\n"
            "- action_label\n"
            "- action_path\n"
            "- highlights (array of strings)\n"
            "- watchouts (array of strings)\n"
            "- next_steps (array of strings)\n\n"
            "Constraints:\n"
            "- keep the first next step concrete and immediately actionable\n"
            "- do not suggest actions that are already complete in the provided state\n"
            "- respect the requested mode (pm or dev)\n\n"
            f"Context:\n{json.dumps(payload, indent=2)}"
        )

    if capability == "analyze_agent_consumption_simulation":
        return (
            "Analyze the saved agent-consumption simulator report and propose reviewable fixes.\n"
            "Return JSON with exactly these fields:\n"
            "- title\n"
            "- summary\n"
            "- focused_answer\n"
            "- action_label\n"
            "- action_path\n"
            "- highlights (array of strings)\n"
            "- watchouts (array of strings)\n"
            "- next_steps (array of strings)\n\n"
            "Constraints:\n"
            "- treat simulator failures as evidence, not automatic truth\n"
            "- if agent_consumption_readiness is blocked or has unreviewed findings, produce a readiness fix plan even when simulator failures are zero\n"
            "- do not say there are no fixes while readiness blockers, readiness warnings, or high-risk confirmations remain unresolved\n"
            "- identify whether each failure likely belongs to Developer Definition, reviewed agent consumability metadata, explicit app glue, service behavior, or acceptable warning\n"
            "- identify whether each unreviewed readiness finding should be fixed in the contract, classified as explicit app glue, accepted as a warning, or tracked as follow-up\n"
            "- do not suggest hardcoding package-specific logic into the generic ANIP runtime\n"
            "- suggest rerunning the simulator after reviewed changes\n\n"
            f"Context:\n{json.dumps(payload, indent=2)}"
        )

    if capability == "explain_shape":
        return (
            "Explain the current Studio service design in PM-friendly language.\n"
            "Return JSON with exactly these fields:\n"
            "- title\n"
            "- summary\n"
            "- focused_answer\n"
            "- highlights (array of strings)\n"
            "- watchouts (array of strings)\n"
            "- next_steps (array of strings)\n\n"
            f"Context:\n{json.dumps(payload, indent=2)}"
        )

    if capability == "explain_evaluation":
        return (
            "Explain the current Studio evaluation result in PM-friendly language.\n"
            "Return JSON with exactly these fields:\n"
            "- title\n"
            "- summary\n"
            "- focused_answer\n"
            "- highlights (array of strings)\n"
            "- watchouts (array of strings)\n"
            "- next_steps (array of strings)\n\n"
            f"Context:\n{json.dumps(payload, indent=2)}"
        )

    if capability == "rewrite_business_brief":
        return (
            "Rewrite this deterministic business brief into a clearer, more readable PM-facing narrative.\n"
            "Return JSON with exactly these fields:\n"
            "- document\n\n"
            "Constraints:\n"
            "- title the document as a Business Narrative\n"
            "- keep the same core facts and recommendations\n"
            "- improve flow and readability\n"
            "- use plain language, not protocol jargon unless already necessary\n"
            "- do not add sections that depend on facts not present in the context\n\n"
            f"Context:\n{json.dumps(payload, indent=2)}"
        )

    if capability == "rewrite_engineering_contract":
        return (
            "Rewrite this deterministic engineering contract into a clearer, more readable engineering-facing narrative.\n"
            "Return JSON with exactly these fields:\n"
            "- document\n\n"
            "Constraints:\n"
            "- title the document as an Engineering Narrative\n"
            "- keep the same facts, service boundaries, expectations, and conclusions\n"
            "- improve readability and sequencing for engineers\n"
            "- stay concrete and avoid marketing language\n"
            "- do not invent implementation details not present in the context\n\n"
            f"Context:\n{json.dumps(payload, indent=2)}"
        )

    raise ValueError(f"Unsupported assistant capability: {capability}")


async def _invoke_openai_compatible(
    config: AssistantProviderConfig,
    capability: str,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    if not config.model:
        raise ValueError("STUDIO_ASSISTANT_MODEL is required for openai or ollama providers")

    base_url = (config.base_url or _default_base_url(config.provider)).rstrip("/")
    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"

    body = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": _system_prompt(capability)},
            {"role": "user", "content": _user_prompt(capability, payload)},
        ],
        "temperature": config.temperature,
    }
    if config.provider == "openai":
        body["response_format"] = {"type": "json_object"}

    data = await _post_json_with_retry(
        provider=config.provider,
        url=f"{base_url}/chat/completions",
        headers=headers,
        body=body,
        timeout_seconds=config.timeout_seconds,
    )

    content = data["choices"][0]["message"]["content"]
    if isinstance(content, list):
        text = "".join(part.get("text", "") for part in content if isinstance(part, dict))
    else:
        text = str(content)
    return _parse_json_object(text)


async def _invoke_anthropic(
    config: AssistantProviderConfig,
    capability: str,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    if not config.model:
        raise ValueError("STUDIO_ASSISTANT_MODEL is required for anthropic provider")
    if not config.api_key:
        raise ValueError("ANTHROPIC_API_KEY or STUDIO_ASSISTANT_API_KEY is required for anthropic provider")

    base_url = (config.base_url or _default_base_url(config.provider)).rstrip("/")
    headers = {
        "Content-Type": "application/json",
        "x-api-key": config.api_key,
        "anthropic-version": "2023-06-01",
    }
    body = {
        "model": config.model,
        "max_tokens": 1200,
        "temperature": config.temperature,
        "system": _system_prompt(capability),
        "messages": [{"role": "user", "content": _user_prompt(capability, payload)}],
    }

    data = await _post_json_with_retry(
        provider=config.provider,
        url=f"{base_url}/messages",
        headers=headers,
        body=body,
        timeout_seconds=config.timeout_seconds,
    )

    parts = data.get("content", [])
    text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
    return _parse_json_object(text)


async def _post_json_with_retry(
    *,
    provider: str,
    url: str,
    headers: dict[str, str],
    body: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    last_timeout: httpx.TimeoutException | None = None
    for attempt in range(_TRANSIENT_PROVIDER_ATTEMPTS):
        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.post(url, headers=headers, json=body)
        except httpx.TimeoutException as exc:
            last_timeout = exc
            if attempt < _TRANSIENT_PROVIDER_ATTEMPTS - 1:
                await asyncio.sleep(_TRANSIENT_PROVIDER_BACKOFF_SECONDS)
                continue
            break

        if response.status_code in {408, 409, 425, 429, 500, 502, 503, 504} and attempt < _TRANSIENT_PROVIDER_ATTEMPTS - 1:
            await asyncio.sleep(_TRANSIENT_PROVIDER_BACKOFF_SECONDS)
            continue
        if response.is_error:
            _raise_provider_http_error(provider, response)
        return response.json()

    raise ValueError(f"{provider} provider timed out after {timeout_seconds:.0f}s")


def _raise_provider_http_error(provider: str, response: httpx.Response) -> None:
    detail = response.text.strip()
    if len(detail) > 800:
        detail = detail[:800] + "..."
    raise ValueError(
        f"{provider} provider returned HTTP {response.status_code}"
        + (f": {detail}" if detail else "")
    )


def _default_base_url(provider: str) -> str:
    if provider == "openai":
        return "https://api.openai.com/v1"
    if provider == "anthropic":
        return "https://api.anthropic.com/v1"
    if provider == "ollama":
        return "http://127.0.0.1:11434/v1"
    raise ValueError(f"Unsupported STUDIO_ASSISTANT_PROVIDER: {provider}")


def _parse_json_object(text: str) -> dict[str, Any]:
    raw = text.strip()
    if not raw:
        raise ValueError("Assistant provider returned an empty response")

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("Assistant provider did not return valid JSON") from None
        parsed = json.loads(raw[start : end + 1])

    if not isinstance(parsed, dict):
        raise ValueError("Assistant provider returned JSON, but not a JSON object")
    return parsed
