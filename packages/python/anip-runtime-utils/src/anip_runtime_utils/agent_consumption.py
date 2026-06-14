"""Helpers for consuming ANIP agent-consumability metadata."""

from __future__ import annotations

import re
import json
from typing import Any

DEICTIC_REFERENCE_KEYS = {
    "it",
    "that",
    "thatone",
    "this",
    "thisone",
    "those",
    "these",
    "them",
    "theone",
}

GENERIC_CATALOG_TOKENS = {
    "account",
    "accounts",
    "add",
    "after",
    "and",
    "before",
    "candidate",
    "candidates",
    "cohort",
    "company",
    "companies",
    "content",
    "customer",
    "customers",
    "data",
    "deal",
    "deals",
    "draft",
    "drafting",
    "email",
    "enrich",
    "enrichment",
    "entity",
    "entities",
    "for",
    "follow",
    "followup",
    "highest",
    "in",
    "lead",
    "leads",
    "list",
    "linkedin",
    "opportunity",
    "opportunities",
    "outreach",
    "plan",
    "prepare",
    "preview",
    "prioritize",
    "prioritization",
    "priority",
    "record",
    "records",
    "recommendation",
    "recommendations",
    "reference",
    "route",
    "routed",
    "routing",
    "suggest",
    "suggested",
    "summary",
    "show",
    "target",
    "targets",
    "that",
    "the",
    "this",
    "those",
    "three",
    "these",
    "top",
    "to",
    "up",
    "with",
}

TEMPORAL_REFERENCE_TOKENS = {"fiscal", "fy", "q1", "q2", "q3", "q4", "quarter", "quarters"}

UNSUPPORTED_EFFECT_TERMS = {
    "approval.execute": {"approve", "apply", "commit", "execute", "perform"},
    "external_dispatch": {"deliver", "dispatch", "publish", "send", "ship"},
    "raw_data_export": {"csv", "download", "dump", "export", "raw", "spreadsheet"},
    "system.mutation": {"apply", "commit", "delete", "mutate", "update"},
}

APPROVAL_INTENT_TERMS = {
    "approval",
    "approve",
    "draft",
    "governed",
    "message",
    "plan",
    "prepare",
    "preview",
    "reassign",
    "reassignment",
    "recommendation",
    "recommendations",
    "route",
    "routing",
    "task",
    "tasks",
}

NEGATION_TERMS = {"avoid", "do", "dont", "do not", "exclude", "no", "not", "without"}


def semantic_text_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def text_tokens(value: Any) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", str(value or "").lower().replace("_", " "))
        if len(token) > 1
    }


def ordered_text_tokens(value: Any) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9]+", str(value or "").lower().replace("_", " "))
        if len(token) > 1
    ]


def content_tokens(value: Any) -> set[str]:
    return {
        token
        for token in text_tokens(value)
        if token not in GENERIC_CATALOG_TOKENS
        and token not in TEMPORAL_REFERENCE_TOKENS
        and not re.fullmatch(r"(?:19|20)\d{2}", token)
    }


def runtime_customization_for(capability_metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(capability_metadata, dict):
        return {}
    direct = capability_metadata.get("runtime_customization")
    if isinstance(direct, dict):
        return direct
    app_profile = capability_metadata.get("app_profile")
    if isinstance(app_profile, dict) and isinstance(app_profile.get("runtime_customization"), dict):
        return app_profile["runtime_customization"]
    return {}


def _normalization_customization(customization: dict[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(customization, dict):
        return {}
    value = customization.get("normalization")
    return value if isinstance(value, dict) else {}


def _configured_deictic_terms(customization: dict[str, Any] | None = None) -> set[str]:
    terms = set(DEICTIC_REFERENCE_KEYS)
    raw_terms = _normalization_customization(customization).get("deictic_terms")
    if isinstance(raw_terms, list):
        terms.update(semantic_text_key(item) for item in raw_terms if str(item or "").strip())
    return terms


def _configured_token_variant_rules(customization: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    raw_rules = _normalization_customization(customization).get("token_variant_rules")
    return [rule for rule in raw_rules if isinstance(rule, dict)] if isinstance(raw_rules, list) else []


def _apply_token_variant_rules(tokens: set[str], customization: dict[str, Any] | None = None) -> set[str]:
    variants = set(tokens)
    for token in list(tokens):
        for rule in _configured_token_variant_rules(customization):
            suffix = str(rule.get("suffix") or "").strip().lower()
            replacement = str(rule.get("replacement") or "")
            try:
                min_length = int(rule.get("min_length") or 0)
            except (TypeError, ValueError):
                min_length = 0
            if not suffix or len(token) < min_length or not token.endswith(suffix):
                continue
            variants.add(f"{token[:-len(suffix)]}{replacement}")
    return variants


def _apply_basic_inflection_variants(tokens: set[str]) -> set[str]:
    variants = set(tokens)
    for token in list(tokens):
        if len(token) <= 3:
            continue
        if token.endswith("ies") and len(token) > 4:
            variants.add(f"{token[:-3]}y")
        if token.endswith("es") and len(token) > 4:
            variants.add(token[:-2])
        if token.endswith("s") and len(token) > 4:
            variants.add(token[:-1])
        else:
            variants.add(f"{token}s")
    return variants


def _capability_selection_customization(customization: dict[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(customization, dict):
        return {}
    value = customization.get("capability_selection")
    return value if isinstance(value, dict) else {}


def _runtime_capability_selection_for(capability_metadata: dict[str, Any]) -> dict[str, Any]:
    return _capability_selection_customization(runtime_customization_for(capability_metadata))


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _capability_id_for_metadata(capability_metadata: dict[str, Any]) -> str:
    return str(capability_metadata.get("capability_id") or capability_metadata.get("id") or "").strip()


def _rule_applies_to_capability(rule: dict[str, Any], capability_id: str) -> bool:
    rule_capability = str(rule.get("capability") or rule.get("capability_id") or "").strip()
    return not rule_capability or not capability_id or rule_capability == capability_id


def runtime_business_language_rules_for(capability_metadata: dict[str, Any]) -> list[dict[str, Any]]:
    capability_id = _capability_id_for_metadata(capability_metadata)
    rules = _list_of_dicts(_runtime_capability_selection_for(capability_metadata).get("business_language_rules"))
    return [rule for rule in rules if _rule_applies_to_capability(rule, capability_id)]


def runtime_selection_hints_for(metadata: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    hints: list[dict[str, Any]] = []
    seen: set[str] = set()
    for capability_metadata in metadata.values():
        for hint in _list_of_dicts(_runtime_capability_selection_for(capability_metadata).get("selection_hints")):
            key = repr(sorted(hint.items()))
            if key in seen:
                continue
            seen.add(key)
            hints.append(hint)
    return hints


def _configured_float(
    customization: dict[str, Any] | None,
    key: str,
    default: float,
) -> float:
    raw_value = _capability_selection_customization(customization).get(key)
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return default


def content_token_variants(value: Any, customization: dict[str, Any] | None = None) -> set[str]:
    variants = set(content_tokens(value))
    variants = _apply_basic_inflection_variants(variants)
    return _apply_token_variant_rules(variants, customization)


def exact_value_token_variants(value: Any, customization: dict[str, Any] | None = None) -> set[str]:
    variants = text_tokens(value)
    return _apply_token_variant_rules(variants, customization)


def temporal_tokens(value: Any) -> set[str]:
    return text_tokens(value) & TEMPORAL_REFERENCE_TOKENS


def candidate_temporal_context_is_supported(candidate_text: str, source_text: str) -> bool:
    candidate_temporal = temporal_tokens(candidate_text)
    if not candidate_temporal:
        return True
    source_temporal = temporal_tokens(source_text)
    if candidate_temporal & source_temporal:
        return True
    return quarter_label_from_text(source_text) is not None


def token_score(candidate_text: str, source_text: str) -> float:
    candidate_tokens = text_tokens(candidate_text)
    source_tokens = text_tokens(source_text)
    if not candidate_tokens or not source_tokens:
        return 0.0
    overlap = candidate_tokens & source_tokens
    if not overlap:
        return 0.0
    return len(overlap) / len(candidate_tokens)


def conversation_contains_value(conversation: str, value: Any) -> bool:
    if not isinstance(value, str):
        return True
    raw_value = value.strip()
    if not raw_value:
        return False
    if raw_value.lower() in conversation.lower():
        return True
    return semantic_text_key(raw_value) in semantic_text_key(conversation)


def is_deictic_reference(value: Any) -> bool:
    return semantic_text_key(value) in DEICTIC_REFERENCE_KEYS


def contains_deictic_reference(value: Any, customization: dict[str, Any] | None = None) -> bool:
    tokens = text_tokens(value)
    deictic_terms = _configured_deictic_terms(customization)
    return bool({semantic_text_key(token) for token in tokens} & deictic_terms) or semantic_text_key(value) in deictic_terms


def input_semantics_for(capability_metadata: dict[str, Any], input_name: str) -> dict[str, Any]:
    items = capability_metadata.get("input_semantics")
    if not isinstance(items, list):
        return {}
    for item in items:
        if isinstance(item, dict) and str(item.get("input_name") or "") == input_name:
            return item
    return {}


def input_resolution_for(
    capability_metadata: dict[str, Any],
    input_name: str,
    input_spec: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return v0.24 input-resolution metadata from the strongest available source."""
    if isinstance(input_spec, dict) and isinstance(input_spec.get("resolution"), dict):
        return input_spec["resolution"]
    semantics = input_semantics_for(capability_metadata, input_name)
    if isinstance(semantics.get("resolution"), dict):
        return semantics["resolution"]
    for item in capability_metadata.get("input_specs") or []:
        if isinstance(item, dict) and str(item.get("name") or item.get("input_name") or "") == input_name:
            if isinstance(item.get("resolution"), dict):
                return item["resolution"]
    return {}


def input_resolution_mode_for(
    capability_metadata: dict[str, Any],
    input_name: str,
    input_spec: dict[str, Any] | None = None,
) -> str:
    return str(input_resolution_for(capability_metadata, input_name, input_spec).get("mode") or "")


def input_meanings_for(capability_metadata: dict[str, Any], input_name: str) -> dict[str, Any]:
    meanings = capability_metadata.get("app_profile", {}).get("input_meanings")
    if not isinstance(meanings, dict):
        return {}
    value = meanings.get(input_name)
    return value if isinstance(value, dict) else {}


def reference_catalog_for(capability_metadata: dict[str, Any], input_name: str) -> list[str]:
    catalogs = capability_metadata.get("app_profile", {}).get("reference_catalogs")
    if not isinstance(catalogs, dict):
        return []
    values = catalogs.get(input_name)
    if not isinstance(values, list):
        return []
    return [str(item) for item in values if str(item or "").strip()]


def required_context_for(capability_metadata: dict[str, Any], input_name: str) -> dict[str, Any]:
    items = capability_metadata.get("app_profile", {}).get("required_context") or capability_metadata.get("required_context")
    if not isinstance(items, list):
        return {}
    for item in items:
        if isinstance(item, dict) and str(item.get("input") or "") == input_name:
            return item
    return {}


def candidate_map_for_input(capability_metadata: dict[str, Any], input_name: str) -> dict[str, str]:
    candidates = {
        str(candidate): str(meaning)
        for candidate, meaning in input_meanings_for(capability_metadata, input_name).items()
    }
    for catalog_value in reference_catalog_for(capability_metadata, input_name):
        candidates.setdefault(catalog_value, catalog_value.replace("_", " "))
    return candidates


def semantic_candidate_values_for_input(capability_metadata: dict[str, Any], input_name: str) -> dict[str, str]:
    candidates: dict[str, str] = {}
    for item in capability_metadata.get("input_semantics") or []:
        if not isinstance(item, dict) or str(item.get("input_name") or "") != input_name:
            continue
        for allowed in item.get("allowed_values") or []:
            if not isinstance(allowed, dict):
                continue
            value = str(allowed.get("value") or "").strip()
            if value:
                candidates.setdefault(value, str(allowed.get("meaning") or value))
    app_profile = capability_metadata.get("app_profile")
    if isinstance(app_profile, dict):
        for item in app_profile.get("input_semantics") or []:
            if not isinstance(item, dict) or str(item.get("input_name") or "") != input_name:
                continue
            for allowed in item.get("allowed_values") or []:
                if not isinstance(allowed, dict):
                    continue
                value = str(allowed.get("value") or "").strip()
                if value:
                    candidates.setdefault(value, str(allowed.get("meaning") or value))
    return candidates


def all_candidate_values_for_input(capability_metadata: dict[str, Any], input_spec: dict[str, Any]) -> dict[str, str]:
    input_name = str(input_spec.get("name") or "")
    candidates = candidate_map_for_input(capability_metadata, input_name)
    candidates.update(semantic_candidate_values_for_input(capability_metadata, input_name))
    if not candidates:
        candidates.update({allowed: allowed.replace("_", " ") for allowed in declared_input_candidate_values(input_spec)})
    return candidates


def declared_input_candidate_values(input_spec: dict[str, Any]) -> list[str]:
    allowed_values = [str(value) for value in input_spec.get("allowed_values") or [] if str(value or "").strip()]
    if allowed_values:
        return allowed_values

    description = str(input_spec.get("description") or "")
    default = input_spec.get("default")
    if not isinstance(default, str) or not default.strip() or "," not in description:
        return []

    candidates: list[str] = []
    for raw_part in re.split(r",|\bor\b", description):
        candidate = raw_part.strip().strip(".;:")
        if not candidate:
            continue
        if len(text_tokens(candidate)) > 3:
            continue
        if "_" in candidate or semantic_text_key(candidate) == semantic_text_key(default):
            candidates.append(candidate.replace(" ", "_"))

    deduped: list[str] = []
    for candidate in candidates:
        if candidate not in deduped:
            deduped.append(candidate)
    return deduped


def canonical_from_candidates(
    value: str,
    conversation: str,
    candidates: dict[str, str],
    customization: dict[str, Any] | None = None,
) -> str | None:
    raw_value = value.strip()
    if not raw_value or not candidates:
        return None
    normalized_value = semantic_text_key(raw_value)
    for candidate in candidates:
        if normalized_value == semantic_text_key(candidate):
            return candidate

    source_text = f"{raw_value}\n{conversation}"
    best_candidate = None
    best_score = 0.0
    second_best_score = 0.0
    value_tokens = content_token_variants(raw_value, customization)
    if not value_tokens:
        return None
    for candidate, meaning in candidates.items():
        candidate_text = f"{candidate} {meaning}"
        if not candidate_temporal_context_is_supported(candidate_text, source_text):
            continue
        candidate_tokens = content_token_variants(candidate_text, customization)
        if not (value_tokens & candidate_tokens):
            continue
        value_score = (len(value_tokens & candidate_tokens) / len(value_tokens)) if value_tokens else 0.0
        score = max(token_score(candidate, raw_value), token_score(candidate_text, source_text), value_score)
        if score > best_score:
            second_best_score = best_score
            best_candidate = candidate
            best_score = score
        elif score > second_best_score:
            second_best_score = score

    if best_candidate is None:
        return None
    if best_score >= 0.5:
        return best_candidate
    # Short business phrases often provide one discriminating token ("sales",
    # "SDR", "webinar"). Accept that only when it is unambiguous.
    return best_candidate if best_score >= 0.3 and second_best_score == 0.0 else None


def conversation_supports_canonical_value(
    conversation: str,
    value: str,
    candidates: dict[str, str],
    customization: dict[str, Any] | None = None,
) -> bool:
    if contains_deictic_reference(value, customization):
        return False
    if conversation_contains_value(conversation, value):
        return True
    if contains_deictic_reference(conversation, customization):
        return False
    return canonical_from_candidates(conversation, conversation, candidates, customization) == value


def normalize_reference_value(
    input_spec: dict[str, Any],
    value: Any,
    conversation: str,
    capability_metadata: dict[str, Any],
) -> Any:
    if not isinstance(value, str) or not value.strip():
        return value

    input_name = str(input_spec.get("name") or "")
    customization = runtime_customization_for(capability_metadata)
    if contains_deictic_reference(value, customization):
        return value

    normalized = canonical_from_candidates(
        value,
        conversation,
        candidate_map_for_input(capability_metadata, input_name),
        customization,
    )
    return normalized if normalized is not None else value


def looks_like_quarter_input(input_spec: dict[str, Any]) -> bool:
    name = str(input_spec.get("name") or "").strip().lower()
    description = str(input_spec.get("description") or "").strip().lower()
    return name in {"quarter", "fiscal_quarter"} or "quarter label" in description or "yyyy-q" in description


def quarter_label_from_text(text: str) -> str | None:
    raw = str(text or "")
    if not raw.strip():
        return None
    year_first = re.search(r"\b((?:19|20)\d{2})\s*[-_/ ]?\s*[Qq]([1-4])\b", raw)
    if year_first:
        return f"{year_first.group(1)}-Q{year_first.group(2)}"
    quarter_first = re.search(r"\b[Qq]([1-4])\s*(?:FY\s*)?((?:19|20)\d{2})\b", raw)
    if quarter_first:
        return f"{quarter_first.group(2)}-Q{quarter_first.group(1)}"
    return None


def normalize_declared_input_value(input_spec: dict[str, Any], value: Any, conversation: str) -> Any:
    if not looks_like_quarter_input(input_spec) or not isinstance(value, str):
        return value
    return quarter_label_from_text(value) or quarter_label_from_text(conversation) or value


def is_supported_quarter_input_value(input_spec: dict[str, Any], value: Any, conversation: str) -> bool:
    if not looks_like_quarter_input(input_spec) or not isinstance(value, str):
        return True
    return quarter_label_from_text(conversation) is not None


def infer_declared_input_value(
    input_spec: dict[str, Any],
    conversation: str,
    capability_metadata: dict[str, Any],
) -> Any:
    if looks_like_quarter_input(input_spec):
        explicit_quarter = quarter_label_from_text(conversation)
        if explicit_quarter is not None:
            return explicit_quarter
    input_name = str(input_spec.get("name") or "")
    customization = runtime_customization_for(capability_metadata)
    candidates = all_candidate_values_for_input(capability_metadata, input_spec)
    if looks_like_quarter_input(input_spec) and not candidates:
        return None
    if (
        not looks_like_quarter_input(input_spec)
        and contains_deictic_reference(conversation, customization)
        and requires_declared_grounding(input_spec, capability_metadata)
    ):
        conversation_tokens = content_token_variants(conversation, customization)
        candidates = {
            candidate: meaning
            for candidate, meaning in candidates.items()
            if content_token_variants(candidate, customization) & conversation_tokens
        }
    normalized = canonical_from_candidates(conversation, conversation, candidates, customization)
    if normalized is not None:
        return normalized

    # For reviewed enum/allowed values, the value identifiers themselves are
    # part of the contract. Allow a unique exact-token match even when the token
    # is too generic for free-form catalog matching, e.g. account_risk from
    # "account reassignment".
    conversation_tokens = exact_value_token_variants(conversation, customization)
    exact_matches = [
        candidate
        for candidate in candidates
        if exact_value_token_variants(candidate, customization) & conversation_tokens
        and candidate_temporal_context_is_supported(f"{candidate} {candidates.get(candidate, '')}", conversation)
    ]
    if len(exact_matches) == 1:
        return exact_matches[0]
    input_name = str(input_spec.get("name") or "")
    has_reviewed_candidates = bool(
        input_meanings_for(capability_metadata, input_name)
        or reference_catalog_for(capability_metadata, input_name)
    )
    if (
        requires_declared_grounding(input_spec, capability_metadata)
        and not candidates
        and not has_reviewed_candidates
        and allows_open_text_reference_inference(input_spec, capability_metadata)
    ):
        return concrete_reference_value_from_text(conversation)
    return None


def requires_declared_grounding(input_spec: dict[str, Any], capability_metadata: dict[str, Any]) -> bool:
    input_name = str(input_spec.get("name") or "")
    input_description = str(input_spec.get("description") or "")
    if not input_name or input_spec.get("default") is not None:
        return False
    resolution_mode = input_resolution_mode_for(capability_metadata, input_name, input_spec)
    if resolution_mode:
        return resolution_mode in {
            "closed_values",
            "backend_resolved",
            "app_selected",
            "actor_policy",
            "actor_policy_or_explicit",
            "explicit_only",
            "clarify",
        }
    input_key = semantic_text_key(f"{input_name} {input_description}")
    semantics = input_semantics_for(capability_metadata, input_name)
    required_context = required_context_for(capability_metadata, input_name)
    input_meanings = input_meanings_for(capability_metadata, input_name)
    reference_catalog = reference_catalog_for(capability_metadata, input_name)
    missing_behavior = str(required_context.get("missing_behavior") or "")
    semantic_type = str(semantics.get("semantic_type") or "")
    if input_meanings or reference_catalog:
        return True
    if any(marker in input_key for marker in ("reference", "target", "entity", "subject")) or input_name.endswith("_ref"):
        return True
    if semantic_type.endswith("_reference") or semantic_type in {"entity_reference", "business_context"}:
        return True
    return missing_behavior in {"clarify", "clarify_or_app_select"}


def allows_open_text_reference_inference(input_spec: dict[str, Any], capability_metadata: dict[str, Any]) -> bool:
    """Allow open-text inference only for fields that are explicitly reference-like."""
    input_name = str(input_spec.get("name") or "")
    resolution_mode = input_resolution_mode_for(capability_metadata, input_name, input_spec)
    if resolution_mode:
        return resolution_mode == "backend_resolved"
    input_description = str(input_spec.get("description") or "")
    input_key = semantic_text_key(f"{input_name} {input_description}")
    semantics = input_semantics_for(capability_metadata, input_name)
    semantic_type = str(semantics.get("semantic_type") or "")
    if any(marker in input_key for marker in ("reference", "target", "entity", "subject")) or input_name.endswith("_ref"):
        return True
    return (semantic_type.endswith("_reference") and semantic_type != "scope_reference") or semantic_type == "entity_reference"


def is_ungrounded_declared_context(
    input_spec: dict[str, Any],
    value: Any,
    conversation: str,
    capability_metadata: dict[str, Any],
) -> bool:
    if not isinstance(value, str) or not requires_declared_grounding(input_spec, capability_metadata):
        return False
    customization = runtime_customization_for(capability_metadata)
    if contains_deictic_reference(value, customization):
        return True
    input_name = str(input_spec.get("name") or "")
    candidates = candidate_map_for_input(capability_metadata, input_name)
    if not candidates:
        if not allows_open_text_reference_inference(input_spec, capability_metadata):
            return True
        # Open-ended entity/reference inputs are validated by the service or
        # backend. The app should pass concrete names through instead of
        # requiring Studio to enumerate every possible business entity.
        return not looks_like_concrete_reference_value(value)
    if conversation_supports_canonical_value(conversation, value, candidates, customization):
        return False
    return True


def looks_like_concrete_reference_value(value: Any) -> bool:
    if not isinstance(value, str):
        return True
    raw_value = value.strip()
    if not raw_value:
        return False
    lowered = raw_value.lower()
    vague_phrases = {
        "best customer",
        "top account",
        "top customer",
        "best account",
        "selected account",
        "recommended account",
        "highest priority account",
        "our best customer",
        "our top account",
    }
    if lowered in vague_phrases:
        return False
    if contains_deictic_reference(raw_value):
        return False
    tokens = re.findall(r"[A-Za-z0-9]+", raw_value)
    if not tokens:
        return False
    non_entity_tokens = {
        "draft",
        "east",
        "find",
        "for",
        "north",
        "prioritize",
        "q1",
        "q2",
        "q3",
        "q4",
        "review",
        "show",
        "south",
        "use",
        "west",
    }
    if all(token.lower() in non_entity_tokens or re.fullmatch(r"(?:19|20)\d{2}", token) for token in tokens):
        return False
    if any(any(character.isupper() for character in token) for token in tokens):
        return True
    # Stable business identifiers such as account_123 or acme-corp are concrete
    # even when they arrive lower-cased.
    return bool(re.search(r"[_-]|\d", raw_value)) and len(content_tokens(raw_value)) >= 1


def concrete_reference_value_from_text(text: str) -> str | None:
    stop_terms = {
        "A",
        "An",
        "And",
        "CRM",
        "CSV",
        "East",
        "Find",
        "For",
        "GTM",
        "North",
        "Q1",
        "Q2",
        "Q3",
        "Q4",
        "Route",
        "Show",
        "South",
        "West",
    }
    for match in re.finditer(r"\b[A-Z][A-Za-z0-9]*(?:\s+[A-Z][A-Za-z0-9]*){0,3}\b", str(text or "")):
        candidate = match.group(0).strip()
        if not candidate or candidate in stop_terms:
            continue
        if re.fullmatch(r"Q[1-4]|FY\d{2,4}|\d{4}", candidate):
            continue
        if looks_like_concrete_reference_value(candidate):
            return candidate
    return None


def capability_produces(capability_metadata: dict[str, Any]) -> set[str]:
    effects = capability_metadata.get("business_effects")
    if not isinstance(effects, dict):
        return set()
    values = effects.get("produces")
    return {str(item) for item in values} if isinstance(values, list) else set()


def capability_does_not_produce(capability_metadata: dict[str, Any]) -> set[str]:
    effects = capability_metadata.get("business_effects")
    if not isinstance(effects, dict):
        return set()
    values = effects.get("does_not_produce")
    blocked = {str(item) for item in values} if isinstance(values, list) else set()
    app_boundaries = capability_metadata.get("app_profile", {}).get("app_boundaries")
    if isinstance(app_boundaries, dict) and isinstance(app_boundaries.get("unsupported_effects"), list):
        blocked.update(str(item) for item in app_boundaries["unsupported_effects"])
    return blocked


def effective_business_effects(*sources: dict[str, Any]) -> dict[str, Any]:
    effects: dict[str, Any] = {}
    for source in sources:
        candidate = source.get("business_effects")
        if isinstance(candidate, dict):
            effects = dict(candidate)
            break
    if any(isinstance(source.get("grant_policy"), dict) for source in sources):
        produces = {str(item) for item in effects.get("produces") or []}
        does_not_produce = {str(item) for item in effects.get("does_not_produce") or []}
        produces.discard("data.read")
        produces.update({"approval.request", "system.preview_mutation"})
        does_not_produce.add("approval.execute")
        effects["produces"] = sorted(produces)
        effects["does_not_produce"] = sorted(does_not_produce)
    return effects


def metadata_with_manifest_controls(profile_metadata: dict[str, Any], manifest_capability: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(manifest_capability.get("grant_policy"), dict):
        return profile_metadata
    metadata = dict(profile_metadata)
    approval = dict(metadata.get("approval")) if isinstance(metadata.get("approval"), dict) else {}
    approval.setdefault("required", True)
    approval.setdefault("grant_types", manifest_capability["grant_policy"].get("allowed_grant_types") or [])
    approval.setdefault("approval_effect", "approval.request")
    metadata["approval"] = approval
    app_boundaries = dict(metadata.get("app_boundaries")) if isinstance(metadata.get("app_boundaries"), dict) else {}
    app_boundaries.setdefault(
        "guidance",
        "This capability is approval-governed. Invoke it to produce the service-owned preview/request; do not execute the governed action in app code.",
    )
    metadata["app_boundaries"] = app_boundaries
    return metadata


def compact_agent_json(value: Any) -> str:
    """Render compact deterministic JSON for prompt-safe metadata fragments."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def render_agent_input_spec(item: dict[str, Any]) -> str:
    name = str(item.get("name") or "").strip()
    if not name:
        return ""
    fragments = [name]
    description = str(item.get("description") or "").strip()
    input_type = str(item.get("type") or "").strip()
    if input_type:
        fragments.append(f"type={input_type}")
    if item.get("required") is not None:
        fragments.append(f"required={bool(item.get('required'))}")
    if item.get("default") is not None:
        fragments.append(f"default={item.get('default')}")
    allowed_values = item.get("allowed_values")
    if isinstance(allowed_values, list) and allowed_values:
        fragments.append(f"allowed={','.join(str(value) for value in allowed_values)}")
    if description:
        fragments.append(f"description={description}")
    return f"{name}[{' | '.join(fragments[1:])}]" if len(fragments) > 1 else name


def render_agent_business_effects(effects: dict[str, Any]) -> str:
    if not effects:
        return ""
    fragments: list[str] = []
    for key in ("produces", "does_not_produce"):
        values = effects.get(key)
        if isinstance(values, list) and values:
            fragments.append(f"{key}={','.join(str(value) for value in values)}")
    return " | business_effects=" + "; ".join(fragments) if fragments else ""


def _render_agent_profile_fragment(metadata: dict[str, Any], *, keys: tuple[str, ...]) -> str:
    fragments: list[str] = []
    framing = str(metadata.get("capability_framing") or "").strip()
    if framing:
        fragments.append(f"capability_framing={framing}")
    for key in keys:
        value = metadata.get(key)
        if isinstance(value, (dict, list)) and value:
            fragments.append(f"{key}={compact_agent_json(value)}")
    return " | app_profile=" + " ; ".join(fragments) if fragments else ""


def render_agent_routing_metadata(metadata: dict[str, Any]) -> str:
    """Render metadata useful for capability selection without dumping full app profile state."""
    return _render_agent_profile_fragment(
        metadata,
        keys=(
            "app_boundaries",
            "approval",
            "required_context",
            "app_glue",
            "derived_target_owner",
        ),
    )


def render_agent_detail_metadata(metadata: dict[str, Any]) -> str:
    """Render full per-capability planning metadata for optional second-stage prompts/debugging."""
    return _render_agent_profile_fragment(
        metadata,
        keys=(
            "input_meanings",
            "input_semantics",
            "reference_catalogs",
            "result_display",
            "app_boundaries",
            "approval",
            "required_context",
            "app_glue",
            "derived_target_owner",
            "intent_rules",
            "business_language_rules",
        ),
    )


def render_compact_agent_input_summary(input_specs: list[Any]) -> str:
    """Render input specs for compact routing prompts.

    This is intentionally smaller than `render_agent_input_spec`: compact
    profile prompts need enough structure for routing and obvious parameter
    binding, while full contract validation still happens against the complete
    metadata after selection.
    """
    rendered: list[str] = []
    for raw_spec in input_specs:
        if not isinstance(raw_spec, dict):
            continue
        name = str(raw_spec.get("name") or "").strip()
        if not name:
            continue
        marker = "req" if raw_spec.get("required") is True else "opt"
        allowed = raw_spec.get("allowed_values")
        allowed_text = ""
        if isinstance(allowed, list) and allowed:
            allowed_text = f"={ '/'.join(str(item) for item in allowed[:8]) }"
        rendered.append(f"{name}({marker}{allowed_text})")
    return ", ".join(rendered) or "none"


def _metadata_effect_values(metadata: dict[str, Any], key: str) -> list[str]:
    effects = metadata.get("business_effects")
    values = effects.get(key) if isinstance(effects, dict) else None
    return [str(item) for item in values if str(item).strip()] if isinstance(values, list) else []


def render_compact_agent_capability_line(capability_id: str, metadata: dict[str, Any]) -> str:
    """Render one compact capability candidate line for model routing."""
    produces = _metadata_effect_values(metadata, "produces")
    forbidden = _metadata_effect_values(metadata, "does_not_produce")
    grant_policy = metadata.get("grant_policy")
    approval = " approval" if isinstance(grant_policy, dict) and grant_policy else ""
    input_specs = metadata.get("input_specs") if isinstance(metadata.get("input_specs"), list) else []
    return (
        f"- {capability_id}: {metadata.get('description') or 'No description provided.'} "
        f"| service={metadata.get('service_name') or 'unknown'} "
        f"| inputs={render_compact_agent_input_summary(input_specs)} "
        f"| side_effect={metadata.get('side_effect') or 'unknown'}{approval} "
        f"| produces={','.join(produces) or 'none'} "
        f"| forbids={','.join(forbidden) or 'none'}"
    )


def build_compact_agent_capability_brief(
    conversation: str,
    metadata: dict[str, dict[str, Any]],
    *,
    top_n: int = 10,
) -> tuple[str, dict[str, Any]]:
    """Build a compact top-N routing brief from full runtime metadata.

    The returned brief is an optimization artifact only. Callers must retain the
    full metadata for normalization, invocation, permission, approval, denial,
    recovery, and audit behavior.
    """
    bounded_top_n = max(1, int(top_n or 1))
    scored = sorted(
        (
            (
                compact_capability_match_score(conversation, capability_id, capability_metadata),
                capability_id,
                capability_metadata,
            )
            for capability_id, capability_metadata in metadata.items()
        ),
        key=lambda item: (-item[0], item[1]),
    )
    selected = scored[: min(bounded_top_n, len(scored))]
    lines = [
        "Compact ANIP capability candidates selected by local retrieval.",
        "The model must choose only from these candidate capability IDs.",
    ]
    lines.extend(render_compact_agent_capability_line(capability_id, capability_metadata) for _, capability_id, capability_metadata in selected)
    brief = "\n".join(lines)
    return brief, {
        "compact_catalog": True,
        "compact_top_n": len(selected),
        "compact_candidate_ids": [capability_id for _, capability_id, _ in selected],
        "compact_candidate_scores": {capability_id: round(score, 4) for score, capability_id, _ in selected},
        "compact_brief_chars": len(brief),
    }


def _capability_map(raw_value: Any) -> dict[str, dict[str, Any]]:
    if isinstance(raw_value, dict):
        return {str(key): value for key, value in raw_value.items() if isinstance(value, dict)}
    if isinstance(raw_value, list):
        return {
            str(item.get("name")): item
            for item in raw_value
            if isinstance(item, dict) and str(item.get("name") or "").strip()
        }
    return {}


def build_agent_capability_catalog(
    service_payloads: list[dict[str, Any]],
    profile_capability_metadata: dict[str, dict[str, Any]] | None = None,
    *,
    allow_duplicate_service_urls: bool = False,
) -> dict[str, Any]:
    """Build compact prompt briefs and full runtime metadata from ANIP discovery payloads.

    Network discovery remains outside this helper. Callers pass already-fetched
    `.well-known/anip` and manifest payloads, so the shared runtime utility stays
    dependency-free and usable across app runtimes.
    """
    profile_capability_metadata = profile_capability_metadata or {}
    metadata: dict[str, dict[str, Any]] = {}
    routing_lines: list[str] = []
    detail_lines: list[str] = []
    details_by_capability: dict[str, str] = {}
    services: list[dict[str, Any]] = []
    seen_urls: dict[str, str] = {}

    for index, service in enumerate(service_payloads):
        service_name = str(service.get("name") or service.get("service") or f"service-{index + 1}").strip()
        service_url = str(service.get("url") or "").strip().rstrip("/")
        if not service_name or not service_url:
            continue
        if not allow_duplicate_service_urls and service_url in seen_urls:
            raise ValueError(
                "Duplicate ANIP service URL discovered "
                f"({service_url!r} for {seen_urls[service_url]!r} and {service_name!r}). "
                "Use distinct service endpoints or explicitly allow duplicate URLs."
            )
        seen_urls[service_url] = service_name
        normalized_service = {"name": service_name, "url": service_url}
        for field in ("approval_list_path", "approval_approve_path_template"):
            value = str(service.get(field) or "").strip()
            if value:
                normalized_service[field] = value
        services.append(normalized_service)

        discovery_payload = service.get("discovery")
        discovery = discovery_payload.get("anip_discovery", discovery_payload) if isinstance(discovery_payload, dict) else {}
        manifest = service.get("manifest") if isinstance(service.get("manifest"), dict) else {}
        discovery_caps = _capability_map(discovery.get("capabilities") if isinstance(discovery, dict) else None)
        manifest_caps = _capability_map(manifest.get("capabilities"))

        for capability_id in sorted(set(discovery_caps) | set(manifest_caps)):
            discovery_cap = discovery_caps.get(capability_id, {})
            manifest_cap = manifest_caps.get(capability_id, {})
            input_specs = [
                item
                for item in manifest_cap.get("inputs", [])
                if isinstance(item, dict) and item.get("name")
            ]
            input_names = [str(item.get("name")) for item in input_specs]
            rendered_inputs = [render_agent_input_spec(item) for item in input_specs]
            side_effect = discovery_cap.get("side_effect") or manifest_cap.get("side_effect", {}).get("type") or "unknown"
            minimum_scope = discovery_cap.get("minimum_scope") or manifest_cap.get("minimum_scope") or []
            description = str(discovery_cap.get("description") or manifest_cap.get("description") or "").strip()
            profile_metadata = profile_capability_metadata.get(capability_id)
            if not isinstance(profile_metadata, dict):
                profile_metadata = {}
            profile_metadata = metadata_with_manifest_controls(profile_metadata, manifest_cap)
            business_effects = effective_business_effects(discovery_cap, manifest_cap, profile_metadata)
            app_profile = {
                key: value
                for key, value in profile_metadata.items()
                if key
                in {
                    "capability_framing",
                    "input_meanings",
                    "input_semantics",
                    "reference_catalogs",
                    "result_display",
                    "app_boundaries",
                    "approval",
                    "required_context",
                    "app_glue",
                    "derived_target_owner",
                    "intent_rules",
                    "business_language_rules",
                }
            }
            metadata[capability_id] = {
                "capability_id": capability_id,
                "description": description,
                "minimum_scope": minimum_scope,
                "inputs": input_names,
                "input_specs": input_specs,
                "side_effect": side_effect,
                "grant_policy": manifest_cap.get("grant_policy") if isinstance(manifest_cap.get("grant_policy"), dict) else None,
                "business_effects": business_effects,
                "input_semantics": profile_metadata.get("input_semantics") if isinstance(profile_metadata.get("input_semantics"), list) else [],
                "app_profile": app_profile,
                "runtime_customization": profile_metadata.get("runtime_customization")
                if isinstance(profile_metadata.get("runtime_customization"), dict)
                else None,
                "service_name": service_name,
                "service_url": service_url,
            }
            base_line = (
                f"- {capability_id}: {description or 'No description provided.'} "
                f"| service={service_name} "
                f"| inputs={', '.join(rendered_inputs) or 'none'} "
                f"| minimum_scope={', '.join(str(scope) for scope in minimum_scope) or 'none'} "
                f"| side_effect={side_effect}"
                f"{render_agent_business_effects(business_effects)}"
            )
            routing_line = f"{base_line}{render_agent_routing_metadata(profile_metadata)}"
            detail_line = f"{base_line}{render_agent_detail_metadata(profile_metadata)}"
            routing_lines.append(routing_line)
            detail_lines.append(detail_line)
            details_by_capability[capability_id] = detail_line

    if not metadata:
        raise ValueError("No ANIP capabilities were discovered from configured services")

    routing_brief = "\n".join(routing_lines)
    detail_brief = "\n".join(detail_lines)
    return {
        "routing_brief": routing_brief,
        "detail_brief": detail_brief,
        "details_by_capability": details_by_capability,
        "metadata": metadata,
        "services": services,
        "stats": {
            "service_count": len(services),
            "capability_count": len(metadata),
            "routing_brief_chars": len(routing_brief),
            "detail_brief_chars": len(detail_brief),
        },
    }


def selected_agent_capability_detail(catalog: dict[str, Any], capability_id: str) -> str:
    details = catalog.get("details_by_capability")
    if isinstance(details, dict):
        value = details.get(capability_id)
        if isinstance(value, str):
            return value
    return ""


def app_boundaries_for(capability_metadata: dict[str, Any]) -> dict[str, Any]:
    app_profile = capability_metadata.get("app_profile")
    profile_boundaries = app_profile.get("app_boundaries") if isinstance(app_profile, dict) else None
    if isinstance(profile_boundaries, dict):
        return profile_boundaries
    direct_boundaries = capability_metadata.get("app_boundaries")
    return direct_boundaries if isinstance(direct_boundaries, dict) else {}


def business_language_rules_for(capability_metadata: dict[str, Any]) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    app_profile = capability_metadata.get("app_profile")
    profile_rules = app_profile.get("business_language_rules") if isinstance(app_profile, dict) else None
    if isinstance(profile_rules, list):
        rules.extend(rule for rule in profile_rules if isinstance(rule, dict))
    direct_rules = capability_metadata.get("business_language_rules")
    if isinstance(direct_rules, list):
        rules.extend(rule for rule in direct_rules if isinstance(rule, dict))
    rules.extend(runtime_business_language_rules_for(capability_metadata))
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for rule in rules:
        key = str(rule.get("id") or repr(sorted(rule.items())))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(rule)
    return deduped


def _condition_terms(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip().lower() for item in value if str(item or "").strip()]


def business_language_rule_matches(conversation: str, rule: dict[str, Any]) -> bool:
    condition = rule.get("applies_when")
    if not isinstance(condition, dict):
        return False
    lowered = str(conversation or "").lower()
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


def matching_business_language_rules(
    conversation: str,
    capability_metadata: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        rule
        for rule in business_language_rules_for(capability_metadata)
        if business_language_rule_matches(conversation, rule)
    ]


def rule_suppressed_effects(rule: dict[str, Any]) -> set[str]:
    values = rule.get("suppress_unsupported_effects")
    if isinstance(values, list):
        return {str(value) for value in values if str(value or "").strip()}
    if str(rule.get("agent_action") or "") in {"treat_as_supported", "treat_as_purpose"}:
        return {"*"}
    return set()


def supported_by_business_language_rule(
    conversation: str,
    capability_metadata: dict[str, Any],
    unsupported_effects: set[str] | None = None,
) -> bool:
    effects = unsupported_effects or set()
    for rule in matching_business_language_rules(conversation, capability_metadata):
        suppressed = rule_suppressed_effects(rule)
        if "*" in suppressed:
            return True
        if effects and effects <= suppressed:
            return True
    return False


def conditional_approval_boundary(capability_metadata: dict[str, Any]) -> dict[str, Any]:
    boundary = app_boundaries_for(capability_metadata).get("conditional_approval_boundary")
    return boundary if isinstance(boundary, dict) else {}


def conditional_approval_missing_inputs(capability_metadata: dict[str, Any]) -> set[str]:
    when_missing = conditional_approval_boundary(capability_metadata).get("when_missing")
    return {str(item) for item in when_missing if str(item or "").strip()} if isinstance(when_missing, list) else set()


def conditional_approval_produces(capability_metadata: dict[str, Any]) -> set[str]:
    produces = conditional_approval_boundary(capability_metadata).get("produces")
    return {str(item) for item in produces if str(item or "").strip()} if isinstance(produces, list) else set()


def has_conditional_approval_boundary(capability_metadata: dict[str, Any]) -> bool:
    return bool(
        conditional_approval_missing_inputs(capability_metadata)
        and ({"approval.request", "system.preview_mutation"} & conditional_approval_produces(capability_metadata))
    )


def is_conditional_approval_boundary_active(
    capability_metadata: dict[str, Any],
    parameter_values: dict[str, Any] | None,
) -> bool:
    missing_inputs = conditional_approval_missing_inputs(capability_metadata)
    if not missing_inputs:
        return False
    values = parameter_values if isinstance(parameter_values, dict) else {}
    for input_name in missing_inputs:
        value = values.get(input_name)
        if value is None or value == "" or value == []:
            return True
    return False


def requested_unsupported_effects(conversation: str, capability_metadata: dict[str, Any]) -> set[str]:
    tokens = text_tokens(conversation)
    ordered_tokens = ordered_text_tokens(conversation)
    blocked = capability_does_not_produce(capability_metadata)
    produced = capability_produces(capability_metadata)
    requested: set[str] = set()
    if "approval.execute" in blocked and requests_approval_bypass(conversation):
        requested.add("approval.execute")
    unsupported_terms = app_boundaries_for(capability_metadata).get("unsupported_terms")
    if isinstance(unsupported_terms, dict):
        lowered = str(conversation or "").lower()
        for effect, terms in unsupported_terms.items():
            if not isinstance(terms, list):
                continue
            for term in terms:
                term_text = str(term or "").strip().lower()
                if term_text and term_text in lowered:
                    requested.add(str(effect))
    matching_rules = matching_business_language_rules(conversation, capability_metadata)
    for effect, terms in UNSUPPORTED_EFFECT_TERMS.items():
        matched_terms = tokens & terms
        if not matched_terms:
            continue
        if all(_term_is_negated(ordered_tokens, term) for term in matched_terms):
            continue
        if (
            effect in blocked
            or (effect == "raw_data_export" and "raw_data_export" not in produced)
            or (effect == "external_dispatch" and "content.draft" in produced)
        ):
            requested.add(effect)
    for rule in matching_rules:
        suppressed = rule_suppressed_effects(rule)
        if "*" in suppressed:
            requested.clear()
            break
        requested -= suppressed
    return requested


def requests_approval_bypass(conversation: str) -> bool:
    lowered = str(conversation or "").lower()
    return bool(
        re.search(r"\b(?:without|no|skip|bypass|ignore|omit)\s+(?:any\s+)?approval\b", lowered)
        or re.search(r"\bapproval\s+(?:not\s+)?(?:needed|required|necessary)\b", lowered)
        or re.search(r"\bdon'?t\s+(?:ask for|request|require)\s+approval\b", lowered)
    )


def requested_primary_content_effect(conversation: str) -> str | None:
    tokens = text_tokens(conversation)
    if tokens & {"recommend", "recommendation", "recommendations", "variant", "variants", "option", "options"}:
        return "content.recommendation"
    if tokens & {"draft", "email", "outreach", "message"}:
        return "content.draft"
    if tokens & {"summarize", "summary"}:
        return "content.summary"
    return None


def should_clear_planner_unsupported_for_approval_boundary(
    conversation: str,
    capability_metadata: dict[str, Any],
    *,
    parameter_values: dict[str, Any] | None = None,
    requested_effects: set[str] | None = None,
) -> bool:
    """Allow approval-boundary capabilities to own safe compound requests.

    Planner models sometimes mark a compound request unsupported because a
    secondary sub-intent is outside the selected approval capability. If the
    selected capability is itself the governed approval boundary and no
    explicitly blocked effect was detected from metadata, the service should
    respond with its declared approval/preview outcome instead of the agent
    denying the request pre-invocation.
    """

    conditional_active = is_conditional_approval_boundary_active(capability_metadata, parameter_values)
    if not conditional_active and (not is_approval_capability(capability_metadata) or not has_approval_intent(conversation)):
        return False
    return not (requested_effects or requested_unsupported_effects(conversation, capability_metadata))


def should_clear_planner_unsupported_for_declared_effect(
    conversation: str,
    capability_metadata: dict[str, Any],
    *,
    requested_effects: set[str] | None = None,
) -> bool:
    """Prefer deterministic contract effects over a model-only unsupported flag."""

    if requested_effects or requested_unsupported_effects(conversation, capability_metadata):
        return False
    requested_effect = requested_primary_content_effect(conversation)
    if not requested_effect:
        return False
    return requested_effect in capability_produces(capability_metadata)


def _term_is_negated(tokens: list[str], term: str) -> bool:
    for index, token in enumerate(tokens):
        if token != term:
            continue
        window = tokens[max(0, index - 3):index]
        if "without" in window or "not" in window or "no" in window or "exclude" in window or "avoid" in window:
            return True
        if len(window) >= 2 and window[-2:] == ["do", "not"]:
            return True
    return False


def has_approval_intent(conversation: str) -> bool:
    tokens = text_tokens(conversation)
    matched_terms = tokens & APPROVAL_INTENT_TERMS
    if not matched_terms:
        return False
    ordered_tokens = ordered_text_tokens(conversation)
    return any(not _term_is_negated(ordered_tokens, term) for term in matched_terms)


def is_approval_capability(capability_metadata: dict[str, Any]) -> bool:
    produced = capability_produces(capability_metadata)
    if {"approval.request", "system.preview_mutation"} & produced:
        return True
    approval = capability_metadata.get("app_profile", {}).get("approval") or capability_metadata.get("approval")
    return isinstance(approval, dict) and approval.get("required") is True


def capability_match_score(conversation: str, capability_id: str, capability_metadata: dict[str, Any]) -> float:
    input_fragments: list[str] = []
    for item in capability_metadata.get("input_specs") or []:
        if not isinstance(item, dict):
            continue
        input_fragments.append(str(item.get("name") or ""))
        input_fragments.extend(str(value) for value in item.get("allowed_values") or [])
    input_names = " ".join(input_fragments)
    intent = capability_metadata.get("app_profile", {}).get("intent")
    intent_text = ""
    if isinstance(intent, dict):
        intent_text = f"{intent.get('category', '')} {intent.get('summary', '')}"
    profile_text = ""
    app_profile = capability_metadata.get("app_profile")
    if isinstance(app_profile, dict):
        profile_text = " ".join(
            str(value)
            for key in ("input_meanings", "reference_catalogs", "app_boundaries")
            for value in [app_profile.get(key)]
            if value is not None
        )
    haystack = f"{capability_id} {capability_metadata.get('description', '')} {input_names} {intent_text} {profile_text}"
    customization = runtime_customization_for(capability_metadata)
    source_tokens = content_token_variants(conversation, customization)
    target_tokens = content_token_variants(haystack, customization)
    if not source_tokens or not target_tokens:
        return 0.0
    overlap = source_tokens & target_tokens
    return len(overlap) / max(1, len(source_tokens))


READ_INTENT_TOKENS = {
    "biggest",
    "breakdown",
    "explain",
    "forecast",
    "health",
    "list",
    "rank",
    "ranking",
    "review",
    "show",
    "summarize",
    "summary",
    "top",
    "why",
}


def _conversation_has_read_intent(conversation: str) -> bool:
    tokens = text_tokens(conversation)
    return bool(tokens & READ_INTENT_TOKENS)


def compact_capability_match_score(conversation: str, capability_id: str, capability_metadata: dict[str, Any]) -> float:
    """Score a capability for compact retrieval.

    Compact retrieval has a stronger obligation than ordinary ranking: if it
    omits the right capability, the planner cannot recover. This score keeps
    the base semantic overlap but adds small contract-posture adjustments so
    read-only requests prefer read/summary capabilities over approval or
    mutation-preparation capabilities unless the conversation itself contains
    approval/write-adjacent intent.
    """

    score = capability_match_score(conversation, capability_id, capability_metadata)
    produced = capability_produces(capability_metadata)
    read_intent = _conversation_has_read_intent(conversation)
    approval_intent = has_approval_intent(conversation)
    unsupported_effects = requested_unsupported_effects(conversation, capability_metadata)
    if read_intent and "content.summary" in produced and not is_approval_capability(capability_metadata):
        score += 0.12
    if read_intent and is_approval_capability(capability_metadata) and not approval_intent:
        score -= 0.08
    if unsupported_effects:
        score += 0.03
    return max(0.0, score)


def missing_required_input_names(conversation: str, capability_metadata: dict[str, Any]) -> set[str]:
    inferred_parameters = normalize_declared_parameters({}, conversation, capability_metadata)
    return {
        str(input_spec.get("name") or "")
        for input_spec in capability_metadata.get("input_specs", [])
        if isinstance(input_spec, dict)
        and input_spec.get("required") is True
        and str(input_spec.get("name") or "")
        and str(input_spec.get("name") or "") not in inferred_parameters
    }


def _same_effect_class(first: dict[str, Any], second: dict[str, Any]) -> bool:
    first_produces = capability_produces(first)
    second_produces = capability_produces(second)
    if is_approval_capability(first) and is_approval_capability(second):
        return True
    return bool(first_produces & second_produces)


def select_grounded_capability(
    conversation: str,
    selected_capability: str,
    metadata: dict[str, dict[str, Any]],
) -> str:
    """Prefer a grounded peer when the model picked an ungrounded capability.

    This is intentionally generic: if the selected capability cannot bind its
    required reviewed inputs from the user-authored conversation, do not keep it
    solely because the model chose it. A peer with the same effect class and
    grounded required inputs is safer because it can produce an executable ANIP
    invocation instead of falling through to avoidable clarification.
    """

    selected_metadata = metadata[selected_capability]
    selected_missing = missing_required_input_names(conversation, selected_metadata)
    if not selected_missing:
        return selected_capability

    selected_score = capability_match_score(conversation, selected_capability, selected_metadata)
    customization = runtime_customization_for(selected_metadata)
    min_score = _configured_float(customization, "grounded_peer_min_score", 0.12)
    margin = _configured_float(customization, "grounded_peer_margin", 0.02)
    best_capability = selected_capability
    best_score = 0.0
    best_missing_count = len(selected_missing)

    for capability_id, capability_metadata in metadata.items():
        if capability_id == selected_capability:
            continue
        if not _same_effect_class(selected_metadata, capability_metadata):
            continue
        missing = missing_required_input_names(conversation, capability_metadata)
        if len(missing) >= best_missing_count:
            continue
        score = capability_match_score(conversation, capability_id, capability_metadata)
        if score > best_score:
            best_capability = capability_id
            best_score = score
            best_missing_count = len(missing)

    if best_capability != selected_capability and best_score >= max(min_score, selected_score + margin):
        return best_capability
    return selected_capability


def select_approval_boundary_capability(
    conversation: str,
    selected_capability: str,
    metadata: dict[str, dict[str, Any]],
) -> str:
    selected_metadata = metadata[selected_capability]
    if (
        is_approval_capability(selected_metadata)
        or "content.draft" in capability_produces(selected_metadata)
        or not has_approval_intent(conversation)
    ):
        return selected_capability

    best_capability = selected_capability
    best_score = 0.0
    customization = runtime_customization_for(selected_metadata)
    min_score = _configured_float(customization, "approval_boundary_min_score", 0.12)
    for capability_id, capability_metadata in metadata.items():
        if not is_approval_capability(capability_metadata):
            continue
        score = capability_match_score(conversation, capability_id, capability_metadata)
        if score > best_score:
            best_capability = capability_id
            best_score = score

    return best_capability if best_score >= min_score else selected_capability


def select_declared_effect_capability(
    conversation: str,
    selected_capability: str,
    metadata: dict[str, dict[str, Any]],
) -> str:
    requested_effect = requested_primary_content_effect(conversation)
    if (
        not requested_effect
        or requested_effect in capability_produces(metadata[selected_capability])
        or is_approval_capability(metadata[selected_capability])
        or has_conditional_approval_boundary(metadata[selected_capability])
    ):
        return selected_capability

    best_capability = selected_capability
    best_score = 0.0
    selected_metadata = metadata[selected_capability]
    selected_score = capability_match_score(conversation, selected_capability, selected_metadata)
    customization = runtime_customization_for(selected_metadata)
    min_score = _configured_float(customization, "effect_rewrite_min_score", 0.12)
    margin = _configured_float(customization, "effect_rewrite_margin", 0.1)
    for capability_id, capability_metadata in metadata.items():
        if requested_effect not in capability_produces(capability_metadata):
            continue
        score = capability_match_score(conversation, capability_id, capability_metadata)
        if score > best_score:
            best_capability = capability_id
            best_score = score

    if best_capability != selected_capability and best_score >= max(min_score, selected_score + margin):
        return best_capability
    return selected_capability


def select_requested_effect_floor_capability(
    conversation: str,
    selected_capability: str,
    metadata: dict[str, dict[str, Any]],
) -> str:
    """Avoid keeping a higher-effect capability when the user did not ask for it."""

    selected_metadata = metadata[selected_capability]
    selected_produces = capability_produces(selected_metadata)
    requested_effect = requested_primary_content_effect(conversation)
    selected_needs_explicit_effect = (
        ("content.draft" in selected_produces and requested_effect != "content.draft")
        or (is_approval_capability(selected_metadata) and not has_approval_intent(conversation))
    )
    if is_approval_capability(selected_metadata) and requests_approval_bypass(conversation):
        return selected_capability
    if not selected_needs_explicit_effect:
        return selected_capability

    selected_score = capability_match_score(conversation, selected_capability, selected_metadata)
    customization = runtime_customization_for(selected_metadata)
    min_score = _configured_float(customization, "effect_floor_min_score", 0.12)
    margin = _configured_float(customization, "effect_floor_margin", 0.02)
    preferred_effects = {requested_effect} if requested_effect else {"content.summary", "data.aggregate", "data.read"}
    best_capability = selected_capability
    best_score = 0.0
    for capability_id, capability_metadata in metadata.items():
        if capability_id == selected_capability:
            continue
        produces = capability_produces(capability_metadata)
        if "content.draft" in produces or is_approval_capability(capability_metadata) or has_conditional_approval_boundary(capability_metadata):
            continue
        if preferred_effects and not (produces & preferred_effects):
            continue
        score = capability_match_score(conversation, capability_id, capability_metadata)
        if score > best_score:
            best_capability = capability_id
            best_score = score

    if best_capability != selected_capability and best_score >= max(min_score, selected_score + margin):
        return best_capability
    return selected_capability


def matching_profile_hint(
    conversation: str,
    metadata: dict[str, dict[str, Any]],
    selection_hints: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    lowered = conversation.lower()
    for hint in selection_hints or []:
        if not isinstance(hint, dict):
            continue
        capability_id = str(hint.get("capability") or "")
        if capability_id not in metadata:
            continue
        all_terms = [str(term).lower() for term in hint.get("all_terms") or []]
        any_terms = [str(term).lower() for term in hint.get("any_terms") or []]
        exclude_terms = [str(term).lower() for term in hint.get("exclude_terms") or []]
        if all_terms and not all(term in lowered for term in all_terms):
            continue
        if any_terms and not any(term in lowered for term in any_terms):
            continue
        if exclude_terms and any(term in lowered for term in exclude_terms):
            continue
        return hint
    return None


def select_profile_hint_capability(
    conversation: str,
    selected_capability: str,
    metadata: dict[str, dict[str, Any]],
    selection_hints: list[dict[str, Any]] | None = None,
) -> str:
    hint = matching_profile_hint(conversation, metadata, selection_hints)
    if hint is not None:
        return str(hint.get("capability") or selected_capability)
    return selected_capability


def select_consumable_capability(
    conversation: str,
    selected_capability: str,
    metadata: dict[str, dict[str, Any]],
    selection_hints: list[dict[str, Any]] | None = None,
) -> str:
    matched_hint = matching_profile_hint(conversation, metadata, selection_hints)
    if matched_hint is not None and matched_hint.get("lock_capability") is True:
        return str(matched_hint.get("capability") or selected_capability)
    capability = select_profile_hint_capability(conversation, selected_capability, metadata, selection_hints)
    capability = select_grounded_capability(conversation, capability, metadata)
    capability = select_requested_effect_floor_capability(conversation, capability, metadata)
    capability = select_approval_boundary_capability(conversation, capability, metadata)
    return select_declared_effect_capability(conversation, capability, metadata)


def normalize_declared_parameters(
    parameters: dict[str, Any],
    conversation: str,
    capability_metadata: dict[str, Any],
) -> dict[str, Any]:
    input_specs = [
        item
        for item in capability_metadata.get("input_specs") or []
        if isinstance(item, dict) and item.get("name")
    ]
    declared_inputs = {str(item.get("name")) for item in input_specs}
    allowed_values_by_input = {
        str(item.get("name")): list(all_candidate_values_for_input(capability_metadata, item).keys())
        for item in input_specs
    }
    input_spec_by_name = {str(item.get("name")): item for item in input_specs}
    filtered_parameters: dict[str, Any] = {}
    for key, value in parameters.items():
        if key not in declared_inputs or value is None or value == "":
            continue
        input_spec = input_spec_by_name.get(str(key), {})
        if not is_supported_quarter_input_value(input_spec, value, conversation):
            continue
        if is_ungrounded_declared_context(input_spec, value, conversation, capability_metadata):
            continue
        value = normalize_declared_input_value(input_spec, value, conversation)
        value = normalize_reference_value(input_spec, value, conversation, capability_metadata)
        allowed_values = allowed_values_by_input.get(str(key)) or []
        if isinstance(value, str) and allowed_values:
            normalized = next((allowed for allowed in allowed_values if semantic_text_key(allowed) == semantic_text_key(value)), None)
            if normalized is None:
                customization = runtime_customization_for(capability_metadata)
                normalized = canonical_from_candidates(
                    value,
                    conversation,
                    {allowed: allowed.replace("_", " ") for allowed in allowed_values},
                    customization,
                )
            if normalized is None:
                continue
            value = normalized
        filtered_parameters[key] = value
    for input_spec in input_specs:
        name = str(input_spec.get("name") or "")
        if not name or name in filtered_parameters:
            continue
        inferred = infer_declared_input_value(input_spec, conversation, capability_metadata)
        if inferred is not None:
            filtered_parameters[name] = inferred
    return filtered_parameters


def normalize_invocation_plan(
    plan: dict[str, Any],
    conversation: str,
    metadata: dict[str, dict[str, Any]],
    *,
    selection_hints: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    capability = str(plan.get("selected_capability") or "").strip()
    if not capability:
        raise ValueError("Model selected unsupported capability: <empty>")
    if capability not in metadata:
        raise ValueError(f"Model selected unsupported capability: {capability}")
    runtime_selection_hints = runtime_selection_hints_for(metadata)
    effective_selection_hints = [
        *(selection_hints or []),
        *runtime_selection_hints,
    ]
    user_conversation = user_authored_conversation_text(conversation)
    capability = select_consumable_capability(user_conversation, capability, metadata, effective_selection_hints)

    parameters = plan.get("parameters")
    if not isinstance(parameters, dict):
        raise ValueError("Model returned invalid parameters payload")

    normalized_plan = dict(plan)
    filtered_parameters = normalize_declared_parameters(parameters, user_conversation, metadata[capability])
    normalized_plan["selected_capability"] = capability
    normalized_plan["parameters"] = filtered_parameters

    unsupported_effects = requested_unsupported_effects(user_conversation, metadata[capability])
    missing_required = [
        str(input_spec.get("name") or "")
        for input_spec in metadata[capability].get("input_specs", [])
        if input_spec.get("required") is True
        and str(input_spec.get("name") or "")
        and str(input_spec.get("name") or "") not in filtered_parameters
    ]
    if unsupported_effects:
        normalized_plan["unsupported"] = True
        normalized_plan["unsupported_reason"] = (
            "The selected ANIP capability does not declare support for requested effect(s): "
            + ", ".join(sorted(unsupported_effects))
        )
    elif normalized_plan.get("unsupported") is True and supported_by_business_language_rule(
        user_conversation,
        metadata[capability],
        unsupported_effects,
    ):
        normalized_plan["unsupported"] = False
        normalized_plan["unsupported_reason"] = None
    elif normalized_plan.get("unsupported") is True and should_clear_planner_unsupported_for_approval_boundary(
        user_conversation,
        metadata[capability],
        parameter_values=filtered_parameters,
        requested_effects=unsupported_effects,
    ):
        normalized_plan["unsupported"] = False
        normalized_plan["unsupported_reason"] = None
    elif normalized_plan.get("unsupported") is True and should_clear_planner_unsupported_for_declared_effect(
        user_conversation,
        metadata[capability],
        requested_effects=unsupported_effects,
    ):
        normalized_plan["unsupported"] = False
        normalized_plan["unsupported_reason"] = None
    elif normalized_plan.get("unsupported") is True and missing_required:
        normalized_plan["unsupported"] = False
        normalized_plan["unsupported_reason"] = None
    return normalized_plan


def conversation_text_from_history(question: str, history: list[dict[str, Any]] | None = None) -> str:
    parts: list[str] = []
    for item in history or []:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip().lower()
        content = str(item.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            parts.append(f"{role}: {content}")
    parts.append(f"user: {question}")
    return "\n".join(parts)


def user_authored_conversation_text(conversation: str) -> str:
    """Return only user-authored transcript lines when role prefixes are present."""

    text = str(conversation or "")
    user_lines: list[str] = []
    saw_role_prefix = False
    for line in text.splitlines():
        stripped = line.strip()
        lowered = stripped.lower()
        if lowered.startswith("user:"):
            saw_role_prefix = True
            content = stripped.split(":", 1)[1].strip()
            if content:
                user_lines.append(f"user: {content}")
        elif lowered.startswith("assistant:"):
            saw_role_prefix = True
    if saw_role_prefix:
        return "\n".join(user_lines)
    return text


def _failure_resolution(anip_result: dict[str, Any]) -> dict[str, Any]:
    failure = anip_result.get("failure")
    if not isinstance(failure, dict):
        return {}
    resolution = failure.get("resolution")
    return resolution if isinstance(resolution, dict) else {}


def _clarification_missing_inputs(
    failure: dict[str, Any],
    capability_metadata: dict[str, Any] | None = None,
) -> list[str]:
    resolution = failure.get("resolution") if isinstance(failure.get("resolution"), dict) else {}
    requires = semantic_text_key(resolution.get("requires") if isinstance(resolution, dict) else "")
    input_specs = capability_metadata.get("input_specs") if isinstance(capability_metadata, dict) else []
    matches: list[str] = []
    if isinstance(input_specs, list):
        for input_spec in input_specs:
            if not isinstance(input_spec, dict):
                continue
            name = str(input_spec.get("name") or "").strip()
            if name and semantic_text_key(name) and semantic_text_key(name) in requires:
                matches.append(name)
    return matches


def build_clarification_continuation(
    *,
    capability: str,
    parameters: dict[str, Any],
    anip_result: dict[str, Any],
    capability_metadata: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    failure = anip_result.get("failure")
    if not isinstance(failure, dict) or failure.get("type") != "clarification_required":
        return None
    resolution = _failure_resolution(anip_result)
    return {
        "type": "clarification",
        "capability": str(capability),
        "service": capability_metadata.get("service_name") if isinstance(capability_metadata, dict) else None,
        "parameters": dict(parameters),
        "missing_inputs": _clarification_missing_inputs(failure, capability_metadata),
        "requires": resolution.get("requires"),
        "action": resolution.get("action"),
        "failure_type": failure.get("type"),
    }


def clarification_continuation_from_history(history: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    for item in reversed(history or []):
        if not isinstance(item, dict) or str(item.get("role") or "").strip().lower() != "assistant":
            continue
        continuation = item.get("continuation")
        if isinstance(continuation, dict) and continuation.get("type") == "clarification":
            capability = str(continuation.get("capability") or "").strip()
            if capability:
                return continuation
    return None


def _input_prompt_summary(capability_metadata: dict[str, Any]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for input_spec in capability_metadata.get("input_specs") or []:
        if not isinstance(input_spec, dict):
            continue
        name = str(input_spec.get("name") or "").strip()
        if not name:
            continue
        entry = {
            "name": name,
            "type": input_spec.get("type"),
            "required": input_spec.get("required") is True,
            "description": input_spec.get("description"),
        }
        if "allowed_values" in input_spec:
            entry["allowed_values"] = input_spec.get("allowed_values")
        if isinstance(input_spec.get("resolution"), dict):
            entry["resolution"] = input_spec.get("resolution")
        summary.append({key: value for key, value in entry.items() if value not in (None, "", [])})
    return summary


def build_clarification_continuation_prompt(
    *,
    question: str,
    continuation: dict[str, Any],
    capability_metadata: dict[str, Any],
) -> str:
    return (
        "The previous ANIP invocation returned clarification_required. "
        "Decide whether the new user message answers that clarification for the same capability.\n"
        "Return JSON with exactly these fields:\n"
        "- intent_changed: boolean\n"
        "- parameters: object containing only declared inputs that the user supplied or corrected\n"
        "- rationale: short string\n"
        "- user_message: short string\n\n"
        "Rules:\n"
        "- Do not select a new capability unless the user clearly changed intent; set intent_changed=true in that case.\n"
        "- Do not invent missing values. Only extract values present in the new user message.\n"
        "- Use only declared input names.\n"
        "- Preserve the prior capability and prior parameters when intent_changed=false.\n\n"
        f"Capability: {continuation.get('capability')}\n"
        f"Declared inputs:\n{json.dumps(_input_prompt_summary(capability_metadata), ensure_ascii=False)}\n"
        f"Prior parameters:\n{json.dumps(continuation.get('parameters') or {}, ensure_ascii=False)}\n"
        f"Clarification requires: {continuation.get('requires') or continuation.get('missing_inputs') or 'unspecified'}\n"
        f"New user message:\n{question}"
    )


def normalize_clarification_continuation_plan(
    plan: dict[str, Any],
    *,
    conversation: str,
    continuation: dict[str, Any],
    capability_metadata: dict[str, Any],
) -> dict[str, Any] | None:
    if plan.get("intent_changed") is True:
        return None
    capability = str(continuation.get("capability") or "").strip()
    if not capability:
        return None
    previous_parameters = continuation.get("parameters")
    proposed_parameters = plan.get("parameters")
    declared_inputs = {
        str(input_spec.get("name"))
        for input_spec in capability_metadata.get("input_specs") or []
        if isinstance(input_spec, dict) and str(input_spec.get("name") or "").strip()
    }
    merged_parameters = (
        {
            str(key): value
            for key, value in previous_parameters.items()
            if str(key) in declared_inputs and value not in (None, "")
        }
        if isinstance(previous_parameters, dict)
        else {}
    )
    if isinstance(proposed_parameters, dict):
        merged_parameters.update(normalize_declared_parameters(proposed_parameters, conversation, capability_metadata))
    inferred_parameters = normalize_declared_parameters({}, conversation, capability_metadata)
    for key, value in inferred_parameters.items():
        merged_parameters.setdefault(key, value)
    missing_inputs = [
        str(item).strip()
        for item in continuation.get("missing_inputs") or []
        if str(item or "").strip()
    ]
    if missing_inputs and any(input_name not in merged_parameters for input_name in missing_inputs):
        return None
    return {
        "selected_capability": capability,
        "parameters": merged_parameters,
        "unsupported": False,
        "unsupported_reason": None,
        "rationale": plan.get("rationale") or "Continue the previous clarification.",
        "user_message": plan.get("user_message") or "",
        "continuation": True,
    }
