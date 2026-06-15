"""Generic LLM-driven ANIP agent runtime.

This runtime is intentionally domain-agnostic. It discovers ANIP capabilities
from configured services, asks an LLM to choose one capability from that
metadata, issues a token with the declared scope, invokes the selected
capability, and returns the ANIP response.
"""
from __future__ import annotations

import asyncio
import importlib
import json
import os
import time
from pathlib import Path
from typing import Any

import httpx
from anip_runtime_utils.agent_consumption import (
    build_agent_capability_catalog,
    build_clarification_continuation,
    build_clarification_continuation_prompt,
    build_compact_agent_capability_brief,
    clarification_continuation_from_history,
    conversation_text_from_history,
    normalize_clarification_continuation_plan,
    normalize_invocation_plan,
)
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel


def _env_int(name: str, default: int, *, minimum: int = 1) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(minimum, value)


OPENAI_BASE_URL = (os.getenv("ANIP_AGENT_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
OPENAI_MODEL = (os.getenv("ANIP_AGENT_MODEL") or os.getenv("OPENAI_MODEL") or "").strip()
OPENAI_API_KEY = (os.getenv("ANIP_AGENT_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()
FALLBACK_BASE_URL = (
    os.getenv("ANIP_AGENT_FALLBACK_BASE_URL")
    or os.getenv("OPENAI_FALLBACK_BASE_URL")
    or OPENAI_BASE_URL
).rstrip("/")
FALLBACK_MODEL = (
    os.getenv("ANIP_AGENT_FALLBACK_MODEL")
    or os.getenv("ANIP_AGENT_MODEL_FALLBACK")
    or os.getenv("OPENAI_FALLBACK_MODEL")
    or ""
).strip()
FALLBACK_API_KEY = (
    os.getenv("ANIP_AGENT_FALLBACK_API_KEY")
    or os.getenv("OPENAI_FALLBACK_API_KEY")
    or OPENAI_API_KEY
).strip()
AGENT_TIMEOUT_SECONDS = float(os.getenv("ANIP_AGENT_TIMEOUT_SECONDS", "30"))
AGENT_TEMPERATURE = float(os.getenv("ANIP_AGENT_TEMPERATURE", "0.1"))
AGENT_MODEL_MAX_RETRIES = int(os.getenv("ANIP_AGENT_MODEL_MAX_RETRIES", "6"))
CATALOG_TTL_SECONDS = int(os.getenv("ANIP_AGENT_CATALOG_TTL_SECONDS", os.getenv("CATALOG_TTL_SECONDS", "30")))
COMPACT_CATALOG_ENABLED = (os.getenv("ANIP_AGENT_COMPACT_CATALOG") or "").strip().lower() in {"1", "true", "yes"}
COMPACT_CATALOG_TOP_N = _env_int("ANIP_AGENT_COMPACT_CATALOG_TOP_N", 10)
UI_PATH = Path(__file__).resolve().parent / "index.html"
ENTRY_PATH = Path(__file__).resolve().parent / "entry.html"
METABASE_PATH = Path(__file__).resolve().parent / "metabase.html"
QUESTIONS_PATH = Path(__file__).resolve().parent / "questions.html"
RUNBOOK_PATH = Path(__file__).resolve().parent / "runbook.html"
APPROVALS_PATH = Path(__file__).resolve().parent / "approvals.html"
AGENT_CONSUMPTION_KIT_DIR = (os.getenv("ANIP_AGENT_CONSUMPTION_KIT_DIR") or "").strip()
SHOWCASE_LANGUAGE = (os.getenv("ANIP_AGENT_LANGUAGE") or "").strip()
SHOWCASE_METABASE_URL = (os.getenv("ANIP_AGENT_METABASE_URL") or "").strip()
SHOWCASE_README_URL = (os.getenv("ANIP_AGENT_README_URL") or "").strip()
SHOWCASE_DOCS_BASE_URL = (os.getenv("ANIP_AGENT_DOCS_BASE_URL") or "https://anip.dev").rstrip("/")
CATALOG_CACHE: dict[str, Any] = {"expires_at": 0.0, "catalog": None}
PLANNER_LOOP_COUNT = 1
SERVICE_INVOKE_LOOP_COUNT = 1
TRANSIENT_MODEL_STATUS_CODES = {429, 500, 502, 503, 504}

DEFAULT_SYSTEM_PROMPT = """You are a generic ANIP agent runtime.

You must operate only through the ANIP capabilities provided in the capability brief.
Do not invent tools, workflows, datasets, permissions, capability IDs, parameter names, or enum values.

Rules:
- Select exactly one capability from the brief.
- Construct one bounded invocation using only declared input names.
- Use defaults and allowed values from the brief when they clearly apply.
- If required business scope is missing, still select the best capability and pass only known parameters so the service can return clarification_required.
- If the selected capability cannot satisfy an explicitly requested output or action, mark the request unsupported instead of silently narrowing it.
- Do not emulate service behavior in the agent.
- Do not plan multi-step workflows unless a single declared capability represents that business capability.
- Treat denied, clarification_required, approval_required, and temporarily_unavailable as normal ANIP outcomes.
- Return only valid JSON.
"""
DEFAULT_RUNTIME_NAME = "anip-generic-llm"
DEFAULT_RUNTIME_TITLE = "Generic ANIP LLM Agent Runtime"
DEFAULT_APP_PROFILE: dict[str, Any] = {
    "runtime_name": DEFAULT_RUNTIME_NAME,
    "title": DEFAULT_RUNTIME_TITLE,
    "system_prompt": DEFAULT_SYSTEM_PROMPT,
    "planning_guidance": "",
    "capability_metadata": {},
    "selection_hints": [],
    "runtime_customization": {},
}
APP_PROFILE = DEFAULT_APP_PROFILE | {}


def _merge_dicts(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    merged = dict(left)
    for key, value in right.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_generated_app_profile() -> dict[str, Any]:
    if not AGENT_CONSUMPTION_KIT_DIR:
        return {}
    path = Path(AGENT_CONSUMPTION_KIT_DIR) / "agent-app-profile.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid agent app profile metadata: {path}") from exc
    if not isinstance(data, dict):
        return {}
    profile: dict[str, Any] = {}
    capability_metadata = data.get("capability_metadata")
    if isinstance(capability_metadata, dict):
        profile["capability_metadata"] = {
            str(capability_id): metadata
            for capability_id, metadata in capability_metadata.items()
            if isinstance(metadata, dict)
        }
    selection_hints = data.get("selection_hints")
    if isinstance(selection_hints, list):
        profile["selection_hints"] = [item for item in selection_hints if isinstance(item, dict)]
    for key in ("runtime_name", "title", "system_prompt", "planning_guidance"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            profile[key] = value
    return profile


def _load_runtime_customization_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid agent runtime customization metadata: {path}") from exc
    return data if isinstance(data, dict) else {}


def _load_generated_runtime_customization() -> dict[str, Any]:
    if not AGENT_CONSUMPTION_KIT_DIR:
        return {}
    kit_dir = Path(AGENT_CONSUMPTION_KIT_DIR)
    generated = _load_runtime_customization_file(kit_dir / "runtime-customization.json")
    overrides = _load_runtime_customization_file(kit_dir / "custom" / "runtime-overrides.json")
    merged = _merge_dicts(generated, overrides)
    for field in ("artifact_type", "schema_version"):
        if generated.get(field) is not None:
            merged[field] = generated[field]
    return merged


def _load_app_profile() -> dict[str, Any]:
    profile = _merge_dicts(APP_PROFILE, _load_generated_app_profile())
    generated_customization = _load_generated_runtime_customization()
    if generated_customization:
        profile["runtime_customization"] = _merge_dicts(
            profile.get("runtime_customization") if isinstance(profile.get("runtime_customization"), dict) else {},
            generated_customization,
        )
    module_name = (os.getenv("ANIP_AGENT_APP_MODULE") or "").strip()
    if not module_name:
        return profile
    module = importlib.import_module(module_name)
    module_profile = {
        "runtime_name": getattr(module, "RUNTIME_NAME", APP_PROFILE["runtime_name"]),
        "title": getattr(module, "RUNTIME_TITLE", APP_PROFILE["title"]),
        "system_prompt": getattr(module, "SYSTEM_PROMPT", APP_PROFILE["system_prompt"]),
        "planning_guidance": getattr(module, "PLANNING_GUIDANCE", APP_PROFILE["planning_guidance"]),
        "capability_metadata": getattr(module, "CAPABILITY_METADATA", APP_PROFILE["capability_metadata"]),
        "selection_hints": getattr(module, "SELECTION_HINTS", APP_PROFILE["selection_hints"]),
        "runtime_customization": getattr(module, "RUNTIME_CUSTOMIZATION", APP_PROFILE["runtime_customization"]),
    }
    return _merge_dicts(profile, module_profile)


APP_PROFILE = _load_app_profile()
SYSTEM_PROMPT = str(APP_PROFILE["system_prompt"])
RUNTIME_NAME = str(APP_PROFILE["runtime_name"])
RUNTIME_TITLE = str(APP_PROFILE["title"])


def _apply_app_plan_customization(
    plan: dict[str, Any],
    conversation: str,
    metadata: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    module_name = (os.getenv("ANIP_AGENT_APP_MODULE") or "").strip()
    if not module_name:
        return plan
    module = importlib.import_module(module_name)
    hook = getattr(module, "normalize_plan_for_app", None)
    if not callable(hook):
        return plan
    updated = hook(plan=plan, conversation=conversation, metadata=metadata)
    return updated if isinstance(updated, dict) else plan


class AskRequest(BaseModel):
    question: str
    history: list[dict[str, Any]] | None = None
    actor_id: str | None = None


class AuditRequest(BaseModel):
    actor_id: str
    service: str | None = None
    capability: str | None = None
    limit: int = 20


class ApprovalActionRequest(BaseModel):
    actor_id: str
    approval_request_id: str
    service: str | None = None


def _json_env(name: str, default: Any) -> Any:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{name} must be valid JSON") from exc


def _configured_services() -> list[dict[str, Any]]:
    configured = _json_env("ANIP_AGENT_SERVICES_JSON", [])
    services: list[dict[str, Any]] = []
    seen_urls: dict[str, str] = {}
    allow_duplicate_urls = (os.getenv("ANIP_AGENT_ALLOW_DUPLICATE_SERVICE_URLS") or "").strip().lower() in {"1", "true", "yes"}
    if isinstance(configured, list):
        for index, item in enumerate(configured):
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip().rstrip("/")
            if not url:
                continue
            name = str(item.get("name") or item.get("service") or f"service-{index + 1}").strip()
            if not allow_duplicate_urls and url in seen_urls:
                raise RuntimeError(
                    "ANIP_AGENT_SERVICES_JSON contains duplicate service URLs "
                    f"({url!r} for {seen_urls[url]!r} and {name!r}). "
                    "Run separate service endpoints for language-parity tests, or set "
                    "ANIP_AGENT_ALLOW_DUPLICATE_SERVICE_URLS=true only when duplicate "
                    "catalog discovery is intentional."
                )
            seen_urls[url] = name
            service = {"name": name, "url": url}
            for field in ("approval_list_path", "approval_approve_path_template"):
                value = str(item.get(field) or "").strip()
                if value:
                    service[field] = value
            services.append(service)

    if not services:
        raise RuntimeError("Configure ANIP_AGENT_SERVICES_JSON")
    return services


def _actor_profiles() -> dict[str, dict[str, Any]]:
    configured = _json_env("ANIP_AGENT_ACTORS_JSON", [])
    profiles: dict[str, dict[str, Any]] = {}
    if isinstance(configured, list):
        for item in configured:
            if not isinstance(item, dict):
                continue
            actor_id = str(item.get("actor_id") or item.get("id") or "").strip()
            bearer = str(item.get("bearer_token") or item.get("api_key") or item.get("token") or "").strip()
            if not actor_id or not bearer:
                continue
            public = {key: value for key, value in item.items() if key not in {"bearer_token", "api_key", "token"}}
            profiles[actor_id] = {"actor_id": actor_id, "bearer_token": bearer, "public": public}

    default_bearer = (os.getenv("ANIP_AGENT_DEFAULT_BEARER_TOKEN") or "").strip()
    default_actor = (os.getenv("ANIP_AGENT_DEFAULT_ACTOR_ID") or "default").strip()
    if default_bearer and default_actor not in profiles:
        profiles[default_actor] = {
            "actor_id": default_actor,
            "bearer_token": default_bearer,
            "public": {"actor_id": default_actor},
        }
    return profiles


def _actor_bearer(actor_id: str | None) -> tuple[str | None, str]:
    profiles = _actor_profiles()
    chosen = (actor_id or os.getenv("ANIP_AGENT_DEFAULT_ACTOR_ID") or "").strip()
    if not chosen and len(profiles) == 1:
        chosen = next(iter(profiles))
    if chosen and chosen in profiles:
        return chosen, profiles[chosen]["bearer_token"]
    default_bearer = (os.getenv("ANIP_AGENT_DEFAULT_BEARER_TOKEN") or "").strip()
    if default_bearer:
        return chosen or "default", default_bearer
    if chosen:
        raise HTTPException(status_code=400, detail=f"Unknown actor_id: {chosen}")
    raise HTTPException(status_code=503, detail="No actor bearer token configured")


def _public_actor_profiles() -> list[dict[str, Any]]:
    return [profile["public"] for profile in _actor_profiles().values()]


def _runtime_customization() -> dict[str, Any]:
    value = APP_PROFILE.get("runtime_customization")
    return value if isinstance(value, dict) else {}


def _condition_terms(value: Any) -> list[str]:
    return [str(item).strip().lower() for item in value if str(item or "").strip()] if isinstance(value, list) else []


def _condition_matches(text: str, condition: Any) -> bool:
    if not isinstance(condition, dict):
        return False
    lowered = str(text or "").lower()
    all_terms = _condition_terms(condition.get("all_terms"))
    any_terms = _condition_terms(condition.get("any_terms"))
    exclude_terms = _condition_terms(condition.get("exclude_terms"))
    if all_terms and not all(term in lowered for term in all_terms):
        return False
    if any_terms and not any(term in lowered for term in any_terms):
        return False
    if exclude_terms and any(term in lowered for term in exclude_terms):
        return False
    return bool(all_terms or any_terms)


def _preflight_rules() -> list[dict[str, Any]]:
    rules = _runtime_customization().get("preflight_denial_rules")
    return [rule for rule in rules if isinstance(rule, dict)] if isinstance(rules, list) else []


def _actor_public_profile(actor_id: str) -> dict[str, Any]:
    for profile in _public_actor_profiles():
        if str(profile.get("actor_id") or "") == actor_id:
            return profile
    return {"actor_id": actor_id}


def _actor_constraints_match(actor_profile: dict[str, Any], constraint: Any) -> bool:
    if not isinstance(constraint, dict) or not constraint:
        return True
    actor_ids = {str(item) for item in constraint.get("actor_ids") or [] if str(item or "").strip()}
    if actor_ids and str(actor_profile.get("actor_id") or "") not in actor_ids:
        return False
    required_claims = constraint.get("claims")
    if isinstance(required_claims, dict):
        for key, expected in required_claims.items():
            actual = actor_profile.get(str(key))
            expected_values = expected if isinstance(expected, list) else [expected]
            if str(actual) not in {str(item) for item in expected_values}:
                return False
    denied_claims = constraint.get("claim_not_values")
    if isinstance(denied_claims, dict):
        for key, denied in denied_claims.items():
            actual = str(actor_profile.get(str(key)) or "")
            denied_values = denied if isinstance(denied, list) else [denied]
            if actual in {str(item) for item in denied_values}:
                return False
    return True


def _preflight_denial_result(question: str, history: list[dict[str, str]] | None, actor_id: str | None) -> dict[str, Any] | None:
    conversation = _conversation_text(question, history)
    resolved_actor_id, _ = _actor_bearer(actor_id)
    resolved_actor_id = resolved_actor_id or "default"
    actor_profile = _actor_public_profile(resolved_actor_id)

    for rule in _preflight_rules():
        if not _condition_matches(conversation, rule.get("applies_when")):
            continue
        if not _actor_constraints_match(actor_profile, rule.get("actor")):
            continue
        detail = str(rule.get("detail") or "The request is outside the reviewed app boundary.").strip()
        result = _unsupported_result(
            {
                "unsupported_reason": detail,
                "rationale": str(rule.get("rationale") or "App preflight denied the request before invocation.").strip(),
                "user_message": str(rule.get("user_message") or detail).strip(),
            }
        )
        return {
            "runtime": RUNTIME_NAME,
            "question": question,
            "actor_id": resolved_actor_id,
            "history": history or [],
            "loop_counts": {
                "planner_loops": 0,
                "service_invoke_loops": 0,
                "total_loops": 0,
            },
            "planner": {
                "model": OPENAI_MODEL,
                "base_url": OPENAI_BASE_URL,
                "rationale": rule.get("rationale") or "App preflight denied the request before invocation.",
                "user_message": rule.get("user_message") or detail,
            },
            "planned_capability": None,
            "selected_capability": None,
            "selected_service": None,
            "parameters": {},
            "capability_metadata": None,
            "anip_result": result,
        }
    return None


def _load_agent_consumability_from_kit() -> dict[str, Any]:
    if not AGENT_CONSUMPTION_KIT_DIR:
        return {}
    path = Path(AGENT_CONSUMPTION_KIT_DIR) / "agent-consumability.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid agent consumability metadata: {path}") from exc
    capabilities = data.get("capabilities")
    return capabilities if isinstance(capabilities, dict) else {}


def _agent_consumption_kit_available() -> bool:
    if not AGENT_CONSUMPTION_KIT_DIR:
        return False
    kit_dir = Path(AGENT_CONSUMPTION_KIT_DIR)
    return (
        (kit_dir / "agent-app-profile.json").exists()
        and (kit_dir / "capability-index.json").exists()
    )


def _metadata_from_agent_consumability() -> dict[str, dict[str, Any]]:
    metadata: dict[str, dict[str, Any]] = {}
    for capability_id, raw_hint in _load_agent_consumability_from_kit().items():
        if not isinstance(raw_hint, dict):
            continue
        intent = raw_hint.get("intent") if isinstance(raw_hint.get("intent"), dict) else {}
        business_effects = raw_hint.get("business_effects") if isinstance(raw_hint.get("business_effects"), dict) else {}
        app_glue = raw_hint.get("app_glue") if isinstance(raw_hint.get("app_glue"), dict) else {}
        required_context = raw_hint.get("required_context") if isinstance(raw_hint.get("required_context"), list) else []
        input_semantics = raw_hint.get("input_semantics") if isinstance(raw_hint.get("input_semantics"), list) else []
        input_meanings = raw_hint.get("input_meanings") if isinstance(raw_hint.get("input_meanings"), dict) else {}
        reference_catalogs = raw_hint.get("reference_catalogs") if isinstance(raw_hint.get("reference_catalogs"), dict) else {}
        result_display = raw_hint.get("result_display") if isinstance(raw_hint.get("result_display"), dict) else {}
        app_boundaries = raw_hint.get("app_boundaries") if isinstance(raw_hint.get("app_boundaries"), dict) else {}
        approval = raw_hint.get("approval") if isinstance(raw_hint.get("approval"), dict) else {}
        derived_target_owner = raw_hint.get("derived_target_owner") if isinstance(raw_hint.get("derived_target_owner"), dict) else {}
        intent_rules = raw_hint.get("intent_rules") if isinstance(raw_hint.get("intent_rules"), list) else []
        business_language_rules = raw_hint.get("business_language_rules") if isinstance(raw_hint.get("business_language_rules"), list) else []
        metadata[str(capability_id)] = {
            "capability_framing": str(intent.get("summary") or "").strip(),
            "business_effects": business_effects,
            "input_meanings": input_meanings,
            "reference_catalogs": reference_catalogs,
            "result_display": result_display,
            "app_boundaries": app_boundaries,
            "approval": approval,
            "input_semantics": input_semantics,
            "required_context": required_context,
            "app_glue": app_glue,
            "derived_target_owner": derived_target_owner,
            "intent_rules": intent_rules,
            "business_language_rules": business_language_rules,
            "agent_consumability": raw_hint,
        }
        does_not_produce = business_effects.get("does_not_produce")
        if isinstance(does_not_produce, list) and does_not_produce:
            metadata[str(capability_id)]["app_boundaries"] = _merge_dicts(app_boundaries, {
                "unsupported_effects": [str(item) for item in does_not_produce],
            })
    return metadata


def _deep_merge(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    merged = dict(left)
    for key, value in right.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _capability_metadata() -> dict[str, dict[str, Any]]:
    kit_metadata = _metadata_from_agent_consumability()
    profile_metadata = APP_PROFILE.get("capability_metadata")
    if not isinstance(profile_metadata, dict):
        profile_metadata = {}
    result = {key: dict(value) for key, value in kit_metadata.items()}
    for capability_id, raw_value in profile_metadata.items():
        if not isinstance(raw_value, dict):
            continue
        existing = result.get(str(capability_id), {})
        # Generated kit metadata is the canonical contract/profile view. App
        # modules may add hints, but must not override regenerated fields.
        result[str(capability_id)] = _deep_merge(raw_value, existing)
    runtime_customization = APP_PROFILE.get("runtime_customization")
    if isinstance(runtime_customization, dict) and runtime_customization:
        for capability_id, metadata in result.items():
            metadata["runtime_customization"] = runtime_customization
    return result


def _load_catalog() -> tuple[str, dict[str, dict[str, Any]], list[dict[str, str]]]:
    now = time.time()
    catalog = CATALOG_CACHE.get("catalog")
    if isinstance(catalog, dict) and CATALOG_CACHE["expires_at"] > now:
        return catalog["routing_brief"], catalog["metadata"], catalog["services"]

    services = _configured_services()
    profile_capability_metadata = _capability_metadata()
    service_payloads: list[dict[str, Any]] = []
    for service in services:
        service_url = service["url"]
        discovery = httpx.get(f"{service_url}/.well-known/anip", timeout=20.0).json().get("anip_discovery", {})
        manifest = httpx.get(f"{service_url}/anip/manifest", timeout=20.0).json()
        service_payloads.append(
            {
                **service,
                "discovery": discovery,
                "manifest": manifest,
            }
        )

    allow_duplicate_urls = (os.getenv("ANIP_AGENT_ALLOW_DUPLICATE_SERVICE_URLS") or "").strip().lower() in {"1", "true", "yes"}
    try:
        catalog = build_agent_capability_catalog(
            service_payloads,
            profile_capability_metadata,
            allow_duplicate_service_urls=allow_duplicate_urls,
        )
    except ValueError as exc:
        raise RuntimeError(str(exc)) from exc

    CATALOG_CACHE["catalog"] = catalog
    CATALOG_CACHE["expires_at"] = now + CATALOG_TTL_SECONDS
    return catalog["routing_brief"], catalog["metadata"], catalog["services"]


def _conversation_text(question: str, history: list[dict[str, Any]] | None = None) -> str:
    return conversation_text_from_history(question, history)


def _planner_capability_brief(
    question: str,
    history: list[dict[str, Any]] | None,
    routing_brief: str,
    metadata: dict[str, dict[str, Any]],
) -> tuple[str, dict[str, Any]]:
    if not COMPACT_CATALOG_ENABLED:
        return routing_brief, {"compact_catalog": False}
    return build_compact_agent_capability_brief(_conversation_text(question, history), metadata, top_n=COMPACT_CATALOG_TOP_N)


def _user_prompt(question: str, capability_brief: str, history: list[dict[str, Any]] | None = None) -> str:
    transcript = _conversation_text(question, history)
    planning_guidance = str(APP_PROFILE.get("planning_guidance") or "").strip()
    guidance_block = f"\nApp-specific planning guidance:\n{planning_guidance}\n" if planning_guidance else ""
    return (
        "Pick the best ANIP capability for the user request and construct one invocation.\n"
        "Return JSON with exactly these fields:\n"
        "- selected_capability: string\n"
        "- parameters: object\n"
        "- unsupported: boolean\n"
        "- unsupported_reason: short string or null\n"
        "- rationale: short string\n"
        "- user_message: short string\n\n"
        "Selection and parameter rules:\n"
        "- Use only capability IDs from the capability brief.\n"
        "- Use only declared parameter names for the selected capability.\n"
        "- Use declared defaults and allowed values when they clearly apply.\n"
        "- Preserve user-provided business scope, timeframe, entity names, counts, and requested action when the selected capability declares matching inputs.\n"
        "- If the user names a concrete business entity and the selected capability declares a matching entity/reference/name input, bind that entity string rather than omitting it.\n"
        "- Do not invent inputs that the metadata classifies as business context, references, or app-selected targets; bind them only when present in the conversation or provided by explicit app glue.\n"
        "- If an input is required but not present in the user request/history, omit it rather than guessing; the service owns clarification.\n"
        "- If the user asks for a compound outcome, choose a single declared compound/business capability if one exists; otherwise choose the narrowest capability that can safely respond.\n\n"
        "- Negative constraints are exclusions, not requested work. If the user says not to draft, send, export, mutate, route, assign, or create something, do not select a capability merely because that forbidden action appears in the text.\n"
        "- Prefer the capability that satisfies the affirmative requested outcome while preserving the user's negative constraints as boundaries.\n\n"
        "- If a compound request includes both read/summary language and prepare/preview/approval/mutation language, prefer a declared capability whose business_effects produce approval.request, system.preview_mutation, or content.draft over a plain read-only summary.\n"
        "- Use app_glue and required_context hints as routing constraints: if the request needs app selection or derived target handling, choose the capability that owns that boundary rather than a harmless adjacent read capability.\n\n"
        "- Set unsupported=true only when the user explicitly asks for hard out-of-contract behavior such as raw data, full exports, debug/internal payloads, hidden underlying records, send-now behavior, or direct unsupported mutations.\n"
        "- Bounded explanation, rationale, evidence, and 'why' language is not the same as raw/internal/debug data. Treat it as supported when the selected capability can produce a bounded summary, recommendation, draft, or rationale, while still denying raw features, weights, training data, hidden records, or full exports.\n"
        "- Do not set unsupported=true just because the selected compound capability covers the primary business intent but not every informational sub-request; preserve the declared inputs and let the service return its bounded result or approval flow.\n"
        "- Do not set unsupported=true merely because required business scope is missing; let the service clarify missing declared inputs.\n\n"
        f"{guidance_block}"
        f"Capability brief:\n{capability_brief}\n\n"
        f"Conversation:\n{transcript}"
    )


def _parse_json_object(text: str) -> dict[str, Any]:
    raw = text.strip()
    if not raw:
        raise ValueError("Model returned an empty response")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("Model did not return valid JSON") from None
        parsed = json.loads(raw[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("Model returned JSON, but not an object")
    return parsed


def _fallback_model_enabled() -> bool:
    return bool(FALLBACK_MODEL and FALLBACK_API_KEY)


def _usage_int(usage: dict[str, Any], key: str) -> int:
    try:
        return int(usage.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def _sum_model_usage(*usages: dict[str, Any]) -> dict[str, Any]:
    prompt_tokens = sum(_usage_int(usage, "prompt_tokens") or _usage_int(usage, "input_tokens") for usage in usages)
    completion_tokens = sum(_usage_int(usage, "completion_tokens") or _usage_int(usage, "output_tokens") for usage in usages)
    total_tokens = sum(_usage_int(usage, "total_tokens") for usage in usages)
    prompt_details: dict[str, int] = {}
    completion_details: dict[str, int] = {}
    for usage in usages:
        raw_prompt_details = usage.get("prompt_tokens_details")
        if isinstance(raw_prompt_details, dict):
            for key, value in raw_prompt_details.items():
                prompt_details[str(key)] = prompt_details.get(str(key), 0) + int(value or 0)
        raw_completion_details = usage.get("completion_tokens_details")
        if isinstance(raw_completion_details, dict):
            for key, value in raw_completion_details.items():
                completion_details[str(key)] = completion_details.get(str(key), 0) + int(value or 0)
    result: dict[str, Any] = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens or prompt_tokens + completion_tokens,
    }
    if prompt_details:
        result["prompt_tokens_details"] = prompt_details
    if completion_details:
        result["completion_tokens_details"] = completion_details
    return result


def _retry_delay_seconds(response: httpx.Response, attempt: int) -> float:
    retry_after = response.headers.get("retry-after")
    if retry_after:
        try:
            return min(float(retry_after), 20.0)
        except ValueError:
            pass
    return min(1.0 * (2 ** attempt), 20.0)


async def _call_model_json(
    user_prompt: str,
    *,
    system_prompt: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    selected_model = (model or OPENAI_MODEL).strip()
    selected_base_url = (base_url or OPENAI_BASE_URL).rstrip("/")
    selected_api_key = (api_key or OPENAI_API_KEY).strip()
    if not selected_model:
        raise HTTPException(status_code=503, detail="ANIP_AGENT_MODEL or OPENAI_MODEL is not configured")
    if not selected_api_key:
        raise HTTPException(status_code=503, detail="ANIP_AGENT_API_KEY or OPENAI_API_KEY is not configured")

    body = {
        "model": selected_model,
        "messages": [
            {"role": "system", "content": system_prompt or SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": AGENT_TEMPERATURE,
        "response_format": {"type": "json_object"},
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {selected_api_key}"}

    async with httpx.AsyncClient(timeout=AGENT_TIMEOUT_SECONDS) as client:
        response: httpx.Response | None = None
        last_transport_error: httpx.TransportError | None = None
        for attempt in range(max(1, AGENT_MODEL_MAX_RETRIES)):
            try:
                response = await client.post(f"{selected_base_url}/chat/completions", headers=headers, json=body)
            except httpx.TransportError as exc:
                last_transport_error = exc
                if attempt < max(1, AGENT_MODEL_MAX_RETRIES) - 1:
                    await asyncio.sleep(min(1.0 * (2 ** attempt), 20.0))
                    continue
                raise HTTPException(
                    status_code=503,
                    detail=f"Planner model temporarily unavailable after retries: {exc.__class__.__name__}",
                ) from exc
            if response.status_code not in TRANSIENT_MODEL_STATUS_CODES:
                break
            if attempt < max(1, AGENT_MODEL_MAX_RETRIES) - 1:
                await asyncio.sleep(_retry_delay_seconds(response, attempt))
        if response is None:
            detail = (
                f"Planner model did not return a response: {last_transport_error.__class__.__name__}"
                if last_transport_error
                else "Planner model did not return a response"
            )
            raise HTTPException(status_code=503, detail=detail)
        if response.status_code in TRANSIENT_MODEL_STATUS_CODES:
            raise HTTPException(
                status_code=503,
                detail=f"Planner model temporarily unavailable after retries: HTTP {response.status_code}",
            )
        response.raise_for_status()
        data = response.json()

    content = data["choices"][0]["message"]["content"]
    if isinstance(content, list):
        content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    return _parse_json_object(str(content)), dict(usage)


def _normalize_planner_candidate(
    raw_plan: dict[str, Any],
    *,
    conversation: str,
    metadata: dict[str, dict[str, Any]],
    compact_stats: dict[str, Any],
) -> tuple[dict[str, Any], str | None]:
    selection_hints = APP_PROFILE.get("selection_hints") if isinstance(APP_PROFILE.get("selection_hints"), list) else []
    plan = normalize_invocation_plan(raw_plan, conversation, metadata, selection_hints=selection_hints)
    plan = _apply_app_plan_customization(plan, conversation, metadata)
    capability = str(plan.get("selected_capability") or "")
    if capability not in metadata:
        return plan, f"selected capability {capability!r} is not in discovered metadata"
    candidate_ids = compact_stats.get("compact_candidate_ids")
    if isinstance(candidate_ids, list) and candidate_ids and capability not in {str(item) for item in candidate_ids}:
        return plan, f"selected capability {capability!r} is outside compact candidate set"
    return plan, None


async def _plan_with_model(question: str, history: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    routing_brief, metadata, _ = _load_catalog()
    capability_brief, compact_stats = _planner_capability_brief(question, history, routing_brief, metadata)
    conversation = _conversation_text(question, history)
    user_prompt = _user_prompt(question, capability_brief, history)
    fallback_reason: str | None = None
    fallback_usage: dict[str, Any] | None = None
    fallback_raw_plan: dict[str, Any] | None = None
    usage: dict[str, Any] = {}
    if not fallback_reason:
        try:
            raw_plan, usage = await _call_model_json(user_prompt)
            plan, fallback_reason = _normalize_planner_candidate(
                raw_plan,
                conversation=conversation,
                metadata=metadata,
                compact_stats=compact_stats,
            )
        except ValueError as exc:
            if not _fallback_model_enabled():
                raise HTTPException(status_code=502, detail=str(exc)) from exc
            fallback_reason = f"primary planner response failed validation: {exc}"
            plan = {}
    else:
        plan = {}
    if fallback_reason and _fallback_model_enabled():
        try:
            fallback_raw_plan, fallback_usage = await _call_model_json(
                user_prompt,
                model=FALLBACK_MODEL,
                base_url=FALLBACK_BASE_URL,
                api_key=FALLBACK_API_KEY,
            )
            plan, second_reason = _normalize_planner_candidate(
                fallback_raw_plan,
                conversation=conversation,
                metadata=metadata,
                compact_stats=compact_stats,
            )
        except ValueError as exc:
            raise HTTPException(status_code=502, detail=f"{fallback_reason}; fallback planner failed validation: {exc}") from exc
        if second_reason:
            raise HTTPException(status_code=502, detail=f"{fallback_reason}; fallback planner failed validation: {second_reason}")
    elif fallback_reason:
        raise HTTPException(status_code=502, detail=fallback_reason)

    capability = str(plan["selected_capability"])
    catalog = CATALOG_CACHE.get("catalog")
    stats = catalog.get("stats", {}) if isinstance(catalog, dict) else {}
    stats = {**stats, **compact_stats}
    used_fallback = fallback_usage is not None
    total_usage = _sum_model_usage(usage, fallback_usage or {})
    return {
        "plan": plan,
        "metadata": metadata[capability],
        "capability_brief": capability_brief,
        "catalog_stats": stats,
        "model": FALLBACK_MODEL if used_fallback else OPENAI_MODEL,
        "base_url": FALLBACK_BASE_URL if used_fallback else OPENAI_BASE_URL,
        "planner_fallback": {
            "enabled": _fallback_model_enabled(),
            "used": used_fallback,
            "reason": fallback_reason if used_fallback else None,
            "primary_model": OPENAI_MODEL,
            "primary_base_url": OPENAI_BASE_URL,
            "fallback_model": FALLBACK_MODEL or None,
            "fallback_base_url": FALLBACK_BASE_URL if FALLBACK_MODEL else None,
        },
        "prompt_stats": {
            "system_prompt_chars": len(SYSTEM_PROMPT),
            "user_prompt_chars": len(user_prompt),
            "capability_brief_chars": len(capability_brief),
        },
        "usage": total_usage,
        "primary_usage": usage,
        "fallback_usage": fallback_usage or {},
        "raw_fallback_plan": fallback_raw_plan,
    }


async def _plan_clarification_continuation(
    question: str,
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    continuation = clarification_continuation_from_history(history)
    if continuation is None:
        return None

    capability = str(continuation.get("capability") or "").strip()
    capability_brief, metadata, _ = _load_catalog()
    if capability not in metadata:
        return None

    capability_metadata = metadata[capability]
    user_prompt = build_clarification_continuation_prompt(
        question=question,
        continuation=continuation,
        capability_metadata=capability_metadata,
    )
    conversation = _conversation_text(question, history)
    fallback_reason: str | None = None
    fallback_usage: dict[str, Any] | None = None
    usage: dict[str, Any] = {}
    if not fallback_reason:
        try:
            raw_plan, usage = await _call_model_json(user_prompt)
            plan = normalize_clarification_continuation_plan(
                raw_plan,
                conversation=conversation,
                continuation=continuation,
                capability_metadata=capability_metadata,
            )
        except ValueError as exc:
            if not _fallback_model_enabled():
                raise HTTPException(status_code=502, detail=str(exc)) from exc
            fallback_reason = f"primary clarification response failed validation: {exc}"
            plan = None
    else:
        plan = None
    if plan is None and _fallback_model_enabled():
        fallback_reason = fallback_reason or "primary clarification response did not produce a continuation plan"
        try:
            raw_plan, fallback_usage = await _call_model_json(
                user_prompt,
                model=FALLBACK_MODEL,
                base_url=FALLBACK_BASE_URL,
                api_key=FALLBACK_API_KEY,
            )
            plan = normalize_clarification_continuation_plan(
                raw_plan,
                conversation=conversation,
                continuation=continuation,
                capability_metadata=capability_metadata,
            )
        except ValueError as exc:
            raise HTTPException(status_code=502, detail=f"{fallback_reason}; fallback clarification failed validation: {exc}") from exc
    if plan is None:
        return None

    catalog = CATALOG_CACHE.get("catalog")
    stats = catalog.get("stats", {}) if isinstance(catalog, dict) else {}
    used_fallback = fallback_usage is not None
    return {
        "plan": plan,
        "metadata": capability_metadata,
        "capability_brief": capability_brief,
        "catalog_stats": stats,
        "planner_mode": "clarification_continuation",
        "model": FALLBACK_MODEL if used_fallback else OPENAI_MODEL,
        "base_url": FALLBACK_BASE_URL if used_fallback else OPENAI_BASE_URL,
        "planner_fallback": {
            "enabled": _fallback_model_enabled(),
            "used": used_fallback,
            "reason": fallback_reason if used_fallback else None,
            "primary_model": OPENAI_MODEL,
            "primary_base_url": OPENAI_BASE_URL,
            "fallback_model": FALLBACK_MODEL or None,
            "fallback_base_url": FALLBACK_BASE_URL if FALLBACK_MODEL else None,
        },
        "prompt_stats": {
            "system_prompt_chars": len(SYSTEM_PROMPT),
            "user_prompt_chars": len(user_prompt),
            "capability_brief_chars": 0,
        },
        "usage": _sum_model_usage(usage, fallback_usage or {}),
        "primary_usage": usage,
        "fallback_usage": fallback_usage or {},
    }


def _unsupported_result(plan: dict[str, Any]) -> dict[str, Any]:
    reason = str(plan.get("unsupported_reason") or "").strip()
    if not reason:
        reason = "The selected ANIP capability does not declare support for the requested output or action."
    return {
        "success": False,
        "failure": {
            "type": "denied",
            "detail": reason,
            "resolution": {
                "action": "request_declared_capability",
                "requires": "a capability that explicitly declares the requested output or action",
            },
        },
        "invocation_id": None,
        "client_reference_id": None,
        "task_id": None,
        "parent_invocation_id": None,
        "upstream_service": None,
    }


def _stream_event(event_type: str, payload: dict[str, Any]) -> str:
    return json.dumps({"type": event_type, **payload}, separators=(",", ":")) + "\n"


def _issue_token(service_url: str, capability: str, scope: list[str], actor_id: str | None = None) -> tuple[str, str]:
    resolved_actor_id, bearer = _actor_bearer(actor_id)
    response = httpx.post(
        f"{service_url}/anip/tokens",
        json={
            "subject": "agent:anip-generic-llm-runtime",
            "scope": scope,
            "capability": capability,
            "purpose_parameters": {"source": "anip_generic_llm_runtime", "actor_id": resolved_actor_id},
        },
        headers={"Authorization": f"Bearer {bearer}"},
        timeout=20.0,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("issued"):
        raise RuntimeError(f"Token issuance failed: {payload}")
    return payload["token"], resolved_actor_id or "default"


def _invoke(service_url: str, capability: str, parameters: dict[str, Any], scope: list[str], actor_id: str | None = None) -> tuple[dict[str, Any], str]:
    token, resolved_actor_id = _issue_token(service_url=service_url, capability=capability, scope=scope, actor_id=actor_id)
    response = httpx.post(
        f"{service_url}/anip/invoke/{capability}",
        json={"parameters": parameters},
        headers={"Authorization": f"Bearer {token}"},
        timeout=20.0,
    )
    payload = response.json()
    if response.is_error and "failure" not in payload:
        response.raise_for_status()
    return payload, resolved_actor_id


def _service_by_name(service_name: str) -> dict[str, str]:
    _, _, services = _load_catalog()
    for service in services:
        if service["name"] == service_name:
            return service
    raise HTTPException(status_code=400, detail=f"Unknown service: {service_name}")


def _query_audit(service_url: str, actor_id: str, capability: str | None = None, limit: int = 20) -> dict[str, Any]:
    token, _ = _issue_token(
        service_url=service_url,
        capability=capability or "audit",
        scope=["audit:full"],
        actor_id=actor_id,
    )
    params = {"limit": str(limit)}
    if capability:
        params["capability"] = capability
    response = httpx.post(
        f"{service_url}/anip/audit",
        params=params,
        headers={"Authorization": f"Bearer {token}"},
        timeout=20.0,
    )
    payload = response.json()
    if response.is_error and "failure" not in payload:
        response.raise_for_status()
    return payload


def _join_service_path(service_url: str, path: str) -> str:
    normalized_path = path if path.startswith("/") else f"/{path}"
    return f"{service_url.rstrip('/')}{normalized_path}"


def _query_approvals(service: dict[str, Any], actor_id: str, status: str | None = None) -> dict[str, Any]:
    list_path = str(service.get("approval_list_path") or "").strip()
    if not list_path:
        raise HTTPException(status_code=501, detail=f"Service {service['name']} does not configure approval listing.")
    _, bearer = _actor_bearer(actor_id)
    params = {"status": status} if status else None
    response = httpx.get(
        _join_service_path(service["url"], list_path),
        params=params,
        headers={"Authorization": f"Bearer {bearer}"},
        timeout=20.0,
    )
    payload = response.json()
    if response.is_error:
        response.raise_for_status()
    return payload


def _approval_services() -> list[dict[str, Any]]:
    _, _, services = _load_catalog()
    return [service for service in services if str(service.get("approval_list_path") or "").strip()]


def _query_approvals_across_services(actor_id: str, status: str | None = None) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    services: list[dict[str, Any]] = []
    for service in _approval_services():
        payload = _query_approvals(service, actor_id, status=status)
        service_entries = payload.get("entries") if isinstance(payload, dict) else None
        if not isinstance(service_entries, list):
            service_entries = []
        services.append({"service": service["name"], "entry_count": len(service_entries)})
        for entry in service_entries:
            if isinstance(entry, dict):
                entries.append({"service": service["name"], **entry})
    entries.sort(key=lambda item: str(item.get("requested_at") or ""), reverse=True)
    return {"entries": entries, "services": services}


def _approve_request(service: dict[str, Any], actor_id: str, approval_request_id: str) -> dict[str, Any]:
    path_template = str(service.get("approval_approve_path_template") or "").strip()
    if not path_template:
        raise HTTPException(status_code=501, detail=f"Service {service['name']} does not configure approval mutation.")
    _, bearer = _actor_bearer(actor_id)
    approval_path = path_template.replace("{approval_request_id}", approval_request_id)
    response = httpx.post(
        _join_service_path(service["url"], approval_path),
        headers={"Authorization": f"Bearer {bearer}"},
        timeout=20.0,
    )
    payload = response.json()
    if response.is_error:
        response.raise_for_status()
    return payload


def _approve_request_across_services(actor_id: str, approval_request_id: str) -> dict[str, Any]:
    for service in _approval_services():
        payload = _query_approvals(service, actor_id, status="pending")
        entries = payload.get("entries") if isinstance(payload, dict) else []
        if any(isinstance(entry, dict) and entry.get("approval_request_id") == approval_request_id for entry in entries):
            return {"service": service["name"], "approval": _approve_request(service, actor_id, approval_request_id)}
    raise HTTPException(status_code=404, detail=f"Pending approval request not found: {approval_request_id}")


def _approval_request_id_from_failure(failure: dict[str, Any]) -> str | None:
    metadata = failure.get("approval_required")
    if isinstance(metadata, dict):
        value = str(metadata.get("approval_request_id") or "").strip()
        if value:
            return value
    resolution = failure.get("resolution")
    if isinstance(resolution, dict):
        value = str(resolution.get("approval_request_id") or "").strip()
        if value:
            return value
    return None


def _enrich_approval_required_result(result: dict[str, Any], actor_id: str | None) -> dict[str, Any]:
    failure = result.get("failure")
    if not isinstance(failure, dict) or failure.get("type") != "approval_required":
        return result
    approval_request_id = _approval_request_id_from_failure(failure)
    if not approval_request_id:
        return result
    try:
        resolved_actor_id, _ = _actor_bearer(actor_id)
        approvals = _query_approvals_across_services(resolved_actor_id or "default", status="pending")
    except Exception:
        return result
    entries = approvals.get("entries") if isinstance(approvals, dict) else []
    for entry in entries if isinstance(entries, list) else []:
        if isinstance(entry, dict) and entry.get("approval_request_id") == approval_request_id:
            enriched = dict(result)
            enriched_failure = dict(failure)
            enriched_failure["approval"] = entry
            resolution = dict(enriched_failure.get("resolution") or {})
            if "preview" not in resolution and isinstance(entry.get("preview"), dict):
                resolution["preview"] = entry["preview"]
            if entry.get("required_role") and "approval_role_required" not in resolution:
                resolution["approval_role_required"] = entry["required_role"]
            enriched_failure["resolution"] = resolution
            enriched["failure"] = enriched_failure
            return enriched
    return result


app = FastAPI(title=RUNTIME_TITLE)


@app.get("/")
def index():
    return FileResponse(ENTRY_PATH)


@app.get("/agent")
def agent_ui():
    return FileResponse(UI_PATH)


@app.get("/metabase")
def metabase_ui():
    return FileResponse(METABASE_PATH)


@app.get("/questions")
def questions_ui():
    return FileResponse(QUESTIONS_PATH)


@app.get("/runbook")
def runbook_ui():
    return FileResponse(RUNBOOK_PATH)


@app.get("/approvals")
def approvals_ui():
    return FileResponse(APPROVALS_PATH)


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)


@app.get("/api/runtime")
def runtime_info():
    brief, metadata, services = _load_catalog()
    catalog = CATALOG_CACHE.get("catalog")
    catalog_stats = catalog.get("stats", {}) if isinstance(catalog, dict) else {}
    return {
        "runtime": RUNTIME_NAME,
        "title": RUNTIME_TITLE,
        "services": services,
        "actors": _public_actor_profiles(),
        "model": OPENAI_MODEL or None,
        "base_url": OPENAI_BASE_URL,
        "model_optimization": {
            "compact_catalog": {
                "enabled": COMPACT_CATALOG_ENABLED,
                "top_n": COMPACT_CATALOG_TOP_N,
            },
            "fallback": {
                "enabled": _fallback_model_enabled(),
                "model": FALLBACK_MODEL or None,
                "base_url": FALLBACK_BASE_URL if FALLBACK_MODEL else None,
            },
        },
        "capabilities": metadata,
        "capability_brief": brief,
        "catalog_stats": catalog_stats,
        "showcase": {
            "language": SHOWCASE_LANGUAGE or None,
            "links": {
                "agent": "/",
                "metabase": SHOWCASE_METABASE_URL or None,
                "readme": SHOWCASE_README_URL or None,
                "docs": f"{SHOWCASE_DOCS_BASE_URL}/docs/showcases/gtm-agent/overview",
                "architecture": f"{SHOWCASE_DOCS_BASE_URL}/docs/showcases/gtm-agent/architecture",
                "capability_map": f"{SHOWCASE_DOCS_BASE_URL}/docs/showcases/gtm-agent/capability-map",
                "questions": f"{SHOWCASE_DOCS_BASE_URL}/docs/showcases/gtm-agent/questions-and-extensions",
                "question_bank": f"{SHOWCASE_DOCS_BASE_URL}/docs/showcases/gtm-agent/testing#490-question-bank",
                "docker_compose": f"{SHOWCASE_DOCS_BASE_URL}/docs/showcases/gtm-agent/docker-compose",
                "generated_services": f"{SHOWCASE_DOCS_BASE_URL}/docs/showcases/gtm-agent/generated-services",
                "testing": f"{SHOWCASE_DOCS_BASE_URL}/docs/showcases/gtm-agent/testing",
            },
        },
        "app_profile": {
            "module": (os.getenv("ANIP_AGENT_APP_MODULE") or "").strip() or None,
            "planning_guidance": bool(str(APP_PROFILE.get("planning_guidance") or "").strip()),
            "capability_metadata": bool(APP_PROFILE.get("capability_metadata")),
            "agent_consumption_kit_dir": AGENT_CONSUMPTION_KIT_DIR or None,
            "agent_consumption_kit": _agent_consumption_kit_available(),
        },
        "configured": bool(OPENAI_MODEL and OPENAI_API_KEY),
    }


@app.get("/api/actors")
def actors():
    return {"actors": _public_actor_profiles()}


@app.post("/api/audit")
def audit(req: AuditRequest):
    if req.service:
        service = _service_by_name(req.service)
        payload = _query_audit(service_url=service["url"], actor_id=req.actor_id, capability=req.capability, limit=req.limit)
        return {
            "actor_id": req.actor_id,
            "service": req.service,
            "capability": req.capability,
            "audit": payload,
        }
    _, _, services = _load_catalog()
    service_payloads = []
    for service in services:
        service_payloads.append(
            {
                "service": service["name"],
                "audit": _query_audit(service_url=service["url"], actor_id=req.actor_id, capability=req.capability, limit=req.limit),
            }
        )
    return {
        "actor_id": req.actor_id,
        "capability": req.capability,
        "services": service_payloads,
    }


@app.get("/api/approvals")
def approvals(actor_id: str, service: str | None = None, status: str | None = None):
    if service:
        selected = _service_by_name(service)
        return {"actor_id": actor_id, "service": service, "approvals": _query_approvals(selected, actor_id, status=status)}
    return {"actor_id": actor_id, "approvals": _query_approvals_across_services(actor_id, status=status)}


@app.post("/api/approvals/approve")
def approve(req: ApprovalActionRequest):
    if not req.service:
        return {
            "actor_id": req.actor_id,
            **_approve_request_across_services(req.actor_id, req.approval_request_id),
        }
    selected = _service_by_name(req.service)
    return {
        "actor_id": req.actor_id,
        "service": req.service,
        "approval": _approve_request(selected, req.actor_id, req.approval_request_id),
    }


@app.post("/api/ask")
async def ask(req: AskRequest):
    preflight_result = _preflight_denial_result(req.question, req.history, req.actor_id)
    if preflight_result is not None:
        return preflight_result

    planned = await _plan_clarification_continuation(req.question, req.history)
    if planned is None:
        planned = await _plan_with_model(req.question, req.history)
    plan = planned["plan"]
    capability = str(plan["selected_capability"])
    metadata = planned["metadata"]
    parameters = plan["parameters"]
    if plan.get("unsupported") is True:
        result = _unsupported_result(plan)
        resolved_actor_id, _ = _actor_bearer(req.actor_id)
        resolved_actor_id = resolved_actor_id or "default"
    else:
        result, resolved_actor_id = _invoke(
            service_url=metadata["service_url"],
            capability=capability,
            parameters=parameters,
            scope=metadata.get("minimum_scope", []),
            actor_id=req.actor_id,
        )
        result = _enrich_approval_required_result(result, resolved_actor_id)
    continuation = build_clarification_continuation(
        capability=capability,
        parameters=parameters,
        anip_result=result,
        capability_metadata=metadata,
    )
    return {
        "runtime": RUNTIME_NAME,
        "question": req.question,
        "actor_id": resolved_actor_id,
        "history": req.history or [],
        "loop_counts": {
            "planner_loops": PLANNER_LOOP_COUNT,
            "service_invoke_loops": SERVICE_INVOKE_LOOP_COUNT,
            "total_loops": PLANNER_LOOP_COUNT + SERVICE_INVOKE_LOOP_COUNT,
        },
        "planner": {
            "model": planned.get("model") or OPENAI_MODEL,
            "base_url": planned.get("base_url") or OPENAI_BASE_URL,
            "mode": planned.get("planner_mode") or "selection",
            "rationale": plan.get("rationale"),
            "user_message": plan.get("user_message"),
            "prompt_stats": planned.get("prompt_stats"),
            "catalog_stats": planned.get("catalog_stats"),
            "usage": planned.get("usage") or {},
            "primary_usage": planned.get("primary_usage") or {},
            "fallback_usage": planned.get("fallback_usage") or {},
            "fallback": planned.get("planner_fallback") or {},
        },
        "usage": planned.get("usage") or {},
        "planned_capability": capability,
        "selected_capability": capability,
        "selected_service": metadata.get("service_name"),
        "parameters": parameters,
        "capability_metadata": metadata,
        "continuation": continuation,
        "anip_result": result,
    }


@app.post("/api/ask/stream")
async def ask_stream(req: AskRequest):
    async def events():
        try:
            yield _stream_event("status", {"message": "Checking app preflight boundaries."})
            preflight_result = _preflight_denial_result(req.question, req.history, req.actor_id)
            if preflight_result is not None:
                yield _stream_event("final", {"payload": preflight_result})
                return

            yield _stream_event("status", {"message": "Loading ANIP capability catalog."})
            yield _stream_event("status", {"message": "Planning one bounded ANIP invocation."})
            planned = await _plan_clarification_continuation(req.question, req.history)
            if planned is None:
                planned = await _plan_with_model(req.question, req.history)

            plan = planned["plan"]
            capability = str(plan["selected_capability"])
            metadata = planned["metadata"]
            parameters = plan["parameters"]
            yield _stream_event(
                "planner",
                {
                    "mode": planned.get("planner_mode") or "selection",
                    "model": planned.get("model") or OPENAI_MODEL,
                    "base_url": planned.get("base_url") or OPENAI_BASE_URL,
                    "selected_capability": capability,
                    "selected_service": metadata.get("service_name"),
                    "parameters": parameters,
                    "rationale": plan.get("rationale"),
                    "prompt_stats": planned.get("prompt_stats"),
                    "catalog_stats": planned.get("catalog_stats"),
                    "usage": planned.get("usage") or {},
                    "primary_usage": planned.get("primary_usage") or {},
                    "fallback_usage": planned.get("fallback_usage") or {},
                    "fallback": planned.get("planner_fallback") or {},
                },
            )

            if plan.get("unsupported") is True:
                yield _stream_event("status", {"message": "Request is outside the declared ANIP capability boundary."})
                result = _unsupported_result(plan)
                resolved_actor_id, _ = _actor_bearer(req.actor_id)
                resolved_actor_id = resolved_actor_id or "default"
            else:
                yield _stream_event(
                    "status",
                    {
                        "message": "Invoking selected ANIP service.",
                        "selected_service": metadata.get("service_name"),
                        "selected_capability": capability,
                    },
                )
                result, resolved_actor_id = _invoke(
                    service_url=metadata["service_url"],
                    capability=capability,
                    parameters=parameters,
                    scope=metadata.get("minimum_scope", []),
                    actor_id=req.actor_id,
                )
                result = _enrich_approval_required_result(result, resolved_actor_id)
                yield _stream_event(
                    "anip_result",
                    {
                        "success": result.get("success"),
                        "failure_type": (result.get("failure") or {}).get("type") if isinstance(result.get("failure"), dict) else None,
                        "invocation_id": result.get("invocation_id"),
                    },
                )

            continuation = build_clarification_continuation(
                capability=capability,
                parameters=parameters,
                anip_result=result,
                capability_metadata=metadata,
            )
            payload = {
                "runtime": RUNTIME_NAME,
                "question": req.question,
                "actor_id": resolved_actor_id,
                "history": req.history or [],
                "loop_counts": {
                    "planner_loops": PLANNER_LOOP_COUNT,
                    "service_invoke_loops": SERVICE_INVOKE_LOOP_COUNT,
                    "total_loops": PLANNER_LOOP_COUNT + SERVICE_INVOKE_LOOP_COUNT,
                },
                "planner": {
                    "model": planned.get("model") or OPENAI_MODEL,
                    "base_url": planned.get("base_url") or OPENAI_BASE_URL,
                    "mode": planned.get("planner_mode") or "selection",
                    "rationale": plan.get("rationale"),
                    "user_message": plan.get("user_message"),
                    "prompt_stats": planned.get("prompt_stats"),
                    "catalog_stats": planned.get("catalog_stats"),
                    "usage": planned.get("usage") or {},
                    "primary_usage": planned.get("primary_usage") or {},
                    "fallback_usage": planned.get("fallback_usage") or {},
                    "fallback": planned.get("planner_fallback") or {},
                },
                "usage": planned.get("usage") or {},
                "planned_capability": capability,
                "selected_capability": capability,
                "selected_service": metadata.get("service_name"),
                "parameters": parameters,
                "capability_metadata": metadata,
                "continuation": continuation,
                "anip_result": result,
            }
            yield _stream_event("final", {"payload": payload})
        except HTTPException as exc:
            yield _stream_event("error", {"status_code": exc.status_code, "detail": exc.detail})
        except Exception as exc:
            yield _stream_event("error", {"status_code": 500, "detail": str(exc)})

    return StreamingResponse(events(), media_type="application/x-ndjson")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "9300")))
