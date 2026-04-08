"""Configurable model provider support for the Studio assistant.

This module keeps provider selection and HTTP specifics out of the main
assistant service. The assistant can stay capability-bounded and deterministic
at its core while optionally using a configured model provider for
interpretation and explanation.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Any

import httpx


@dataclass(frozen=True)
class AssistantProviderConfig:
    provider: str
    model: str | None
    base_url: str | None
    api_key: str | None
    temperature: float
    timeout_seconds: float
    strict: bool


def load_assistant_provider_config() -> AssistantProviderConfig:
    provider = (os.getenv("STUDIO_ASSISTANT_PROVIDER") or "deterministic").strip().lower()
    model = (os.getenv("STUDIO_ASSISTANT_MODEL") or "").strip() or None
    base_url = (os.getenv("STUDIO_ASSISTANT_BASE_URL") or "").strip() or None
    api_key = _provider_api_key(provider)
    temperature = _safe_float(os.getenv("STUDIO_ASSISTANT_TEMPERATURE"), default=0.2)
    timeout_seconds = _safe_float(os.getenv("STUDIO_ASSISTANT_TIMEOUT_SECONDS"), default=20.0)
    strict = (os.getenv("STUDIO_ASSISTANT_STRICT") or "").strip().lower() in {"1", "true", "yes", "on"}

    return AssistantProviderConfig(
        provider=provider,
        model=model,
        base_url=base_url,
        api_key=api_key,
        temperature=temperature,
        timeout_seconds=timeout_seconds,
        strict=strict,
    )


async def try_model_assistant_response(capability: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    config = load_assistant_provider_config()
    if config.provider in {"", "deterministic", "none", "off"}:
        return None

    try:
        if config.provider in {"openai", "ollama"}:
            return await _invoke_openai_compatible(config, capability, payload)
        if config.provider == "anthropic":
            return await _invoke_anthropic(config, capability, payload)
        raise ValueError(f"Unsupported STUDIO_ASSISTANT_PROVIDER: {config.provider}")
    except Exception:
        if config.strict:
            raise
        return None


def _provider_api_key(provider: str) -> str | None:
    explicit = (os.getenv("STUDIO_ASSISTANT_API_KEY") or "").strip()
    if explicit:
        return explicit
    if provider == "openai":
        return (os.getenv("OPENAI_API_KEY") or "").strip() or None
    if provider == "anthropic":
        return (os.getenv("ANTHROPIC_API_KEY") or "").strip() or None
    return None


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

    async with httpx.AsyncClient(timeout=config.timeout_seconds) as client:
        response = await client.post(f"{base_url}/chat/completions", headers=headers, json=body)
        response.raise_for_status()
        data = response.json()

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

    async with httpx.AsyncClient(timeout=config.timeout_seconds) as client:
        response = await client.post(f"{base_url}/messages", headers=headers, json=body)
        response.raise_for_status()
        data = response.json()

    parts = data.get("content", [])
    text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
    return _parse_json_object(text)


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
