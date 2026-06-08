"""Configurable model provider support for Studio agent-consumption simulation."""

from __future__ import annotations

from dataclasses import dataclass
import asyncio
import json
import os
from typing import Any

import httpx
from psycopg.types.json import Json

from .db import get_pool
from .assistant_provider import (
    _env_float,
    _env_string,
    _parse_json_object,
    _normalize_float,
    _normalize_optional_string,
    _normalize_provider,
)


_SIMULATOR_CONFIG_KEY = "simulator_runtime_config"
_DEFAULT_SIMULATOR_MODEL = "gpt-5.4-mini"
_DEFAULT_TIMEOUT_SECONDS = 60.0
_TRANSIENT_PROVIDER_ATTEMPTS = 2
_TRANSIENT_PROVIDER_BACKOFF_SECONDS = 3.0


@dataclass(frozen=True)
class SimulatorProviderConfig:
    provider: str
    model: str | None
    base_url: str | None
    api_key: str | None
    temperature: float
    timeout_seconds: float


@dataclass(frozen=True)
class SimulatorProviderResolution:
    config: SimulatorProviderConfig
    provider_source: str
    model_source: str
    base_url_source: str
    api_key_source: str
    temperature_source: str
    timeout_seconds_source: str
    stored_api_key_configured: bool


def load_simulator_provider_resolution() -> SimulatorProviderResolution:
    stored = load_persisted_simulator_provider_settings()

    env_provider_raw, env_provider_present = _env_string("STUDIO_SIMULATOR_PROVIDER")
    stored_provider_raw = _normalize_optional_string(stored.get("provider"))
    provider = _normalize_provider(env_provider_raw if env_provider_present else (stored_provider_raw or "openai"))
    provider_source = "env" if env_provider_present else ("stored" if stored_provider_raw else "default")

    env_model, env_model_present = _env_string("STUDIO_SIMULATOR_MODEL")
    stored_model = _normalize_optional_string(stored.get("model"))
    model = env_model if env_model_present else (stored_model or _DEFAULT_SIMULATOR_MODEL)
    model_source = "env" if env_model_present else ("stored" if stored_model else "default")

    env_base_url, env_base_url_present = _env_string("STUDIO_SIMULATOR_BASE_URL")
    stored_base_url = _normalize_optional_string(stored.get("base_url"))
    base_url = env_base_url if env_base_url_present else stored_base_url
    base_url_source = "env" if env_base_url_present else ("stored" if stored_base_url else "default")

    api_key, api_key_source, stored_api_key_configured = _resolve_simulator_api_key(provider, stored)

    env_temperature, env_temperature_present = _env_float("STUDIO_SIMULATOR_TEMPERATURE")
    stored_temperature = _normalize_float(stored.get("temperature"))
    temperature = env_temperature if env_temperature_present else (stored_temperature if stored_temperature is not None else 0.0)
    temperature_source = "env" if env_temperature_present else ("stored" if stored_temperature is not None else "default")

    env_timeout, env_timeout_present = _env_float("STUDIO_SIMULATOR_TIMEOUT_SECONDS")
    stored_timeout = _normalize_float(stored.get("timeout_seconds"))
    timeout_seconds = env_timeout if env_timeout_present else (stored_timeout if stored_timeout is not None else _DEFAULT_TIMEOUT_SECONDS)
    timeout_seconds_source = "env" if env_timeout_present else ("stored" if stored_timeout is not None else "default")

    return SimulatorProviderResolution(
        config=SimulatorProviderConfig(
            provider=provider,
            model=model,
            base_url=base_url,
            api_key=api_key,
            temperature=temperature,
            timeout_seconds=timeout_seconds,
        ),
        provider_source=provider_source,
        model_source=model_source,
        base_url_source=base_url_source,
        api_key_source=api_key_source,
        temperature_source=temperature_source,
        timeout_seconds_source=timeout_seconds_source,
        stored_api_key_configured=stored_api_key_configured,
    )


def load_persisted_simulator_provider_settings() -> dict[str, Any]:
    try:
        with get_pool().connection() as conn:
            row = conn.execute(
                "SELECT value FROM studio_settings WHERE key = %s",
                (_SIMULATOR_CONFIG_KEY,),
            ).fetchone()
    except Exception:
        return {}
    if not row:
        return {}
    value = row.get("value")
    return value if isinstance(value, dict) else {}


def save_persisted_simulator_provider_settings(update: dict[str, Any]) -> dict[str, Any]:
    current = load_persisted_simulator_provider_settings()
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
    if "api_key" in update:
        next_value["api_key"] = _normalize_optional_string(update.get("api_key"))
    if update.get("clear_api_key"):
        next_value["api_key"] = None

    with get_pool().connection() as conn:
        conn.execute(
            "INSERT INTO studio_settings (key, value) VALUES (%s, %s)"
            " ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()",
            (_SIMULATOR_CONFIG_KEY, Json(next_value)),
        )
        conn.commit()
    return load_persisted_simulator_provider_settings()


def _resolve_simulator_api_key(provider: str, stored: dict[str, Any]) -> tuple[str | None, str, bool]:
    explicit, explicit_present = _env_string("STUDIO_SIMULATOR_API_KEY")
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


async def run_agent_consumption_simulation(payload: dict[str, Any]) -> dict[str, Any]:
    resolution = load_simulator_provider_resolution()
    config = resolution.config
    provider = config.provider or "openai"
    if provider in {"", "deterministic", "none", "off"}:
        raise ValueError("Agent simulator provider is disabled. Configure a simulator provider in Studio settings.")
    if provider in {"openai", "ollama"}:
        result = await _invoke_openai_compatible(config, payload)
    elif provider == "anthropic":
        result = await _invoke_anthropic(config, payload)
    else:
        raise ValueError(f"Unsupported STUDIO_SIMULATOR_PROVIDER: {provider}")
    return {
        "artifact_type": "agent_consumption_simulation_model_output",
        "schema_version": "anip-agent-consumption-simulator/v0",
        "simulator_runtime": {
            "provider": provider,
            "model": config.model,
            "provider_source": resolution.provider_source,
            "model_source": resolution.model_source,
        },
        **_normalize_model_result(result),
    }


async def _invoke_openai_compatible(config: SimulatorProviderConfig, payload: dict[str, Any]) -> dict[str, Any]:
    if not config.model:
        raise ValueError("STUDIO_SIMULATOR_MODEL is required for openai or ollama providers")
    if config.provider == "openai" and not config.api_key:
        raise ValueError("OPENAI_API_KEY or STUDIO_SIMULATOR_API_KEY is required for the OpenAI simulator provider")

    base_url = (config.base_url or _default_base_url(config.provider)).rstrip("/")
    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"

    body = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": _system_prompt()},
            {"role": "user", "content": _user_prompt(payload)},
        ],
        "temperature": config.temperature,
    }
    data = await _post_json_with_retry(
        provider=config.provider,
        url=f"{base_url}/chat/completions",
        headers=headers,
        body=body,
        timeout_seconds=config.timeout_seconds,
    )
    content = data["choices"][0]["message"]["content"]
    text = "".join(part.get("text", "") for part in content if isinstance(part, dict)) if isinstance(content, list) else str(content)
    return _parse_json_object(text)


async def _invoke_anthropic(config: SimulatorProviderConfig, payload: dict[str, Any]) -> dict[str, Any]:
    if not config.model:
        raise ValueError("STUDIO_SIMULATOR_MODEL is required for anthropic provider")
    if not config.api_key:
        raise ValueError("ANTHROPIC_API_KEY or STUDIO_SIMULATOR_API_KEY is required for the Anthropic simulator provider")

    base_url = (config.base_url or _default_base_url(config.provider)).rstrip("/")
    headers = {
        "Content-Type": "application/json",
        "x-api-key": config.api_key,
        "anthropic-version": "2023-06-01",
    }
    body = {
        "model": config.model,
        "max_tokens": 4000,
        "temperature": config.temperature,
        "system": _system_prompt(),
        "messages": [{"role": "user", "content": _user_prompt(payload)}],
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


def _system_prompt() -> str:
    return (
        "You are the ANIP Studio agent-consumption simulator. "
        "You simulate how a baseline ANIP-aware consuming app would interpret package metadata, choose capabilities, prepare parameters, and handle ANIP outcomes. "
        "You do not invent service behavior that is absent from the contract or consumability metadata. "
        "You may use reviewed app-glue hints, but you must not assume hidden GTM-specific code or phrase lists. "
        "Return only valid JSON. Do not wrap JSON in markdown."
    )


def _user_prompt(payload: dict[str, Any]) -> str:
    return (
        "Simulate each probe using only the supplied ANIP package definition, readiness report, and reviewed agent consumability metadata.\n"
        "Return JSON with exactly these top-level fields:\n"
        "- cases: array\n"
        "- summary: object\n\n"
        "Each cases item must contain exactly these fields:\n"
        "- probe_id: string\n"
        "- selected_capability_id: string or null\n"
        "- actual_outcome: one of success, clarification_required, denied, approval_required, unsupported\n"
        "- parameter_plan: object\n"
        "- used_consumability_hints: array of strings\n"
        "- rationale: string\n"
        "- confidence: number from 0 to 1\n\n"
        "Scoring is performed later by deterministic Studio code. Your job is only to produce the simulated consuming-app decision.\n"
        "Rules:\n"
        "- If required context is missing and metadata says clarify or clarify_or_app_select, use clarification_required unless reviewed app glue clearly supplies selection behavior.\n"
        "- If the prompt asks for a declared does_not_produce effect, use unsupported or denied instead of selecting a harmless read capability.\n"
        "- If the capability needs approval and no grant is present in the probe, use approval_required.\n"
        "- Prefer the target_capability_id from the probe only if the prompt and metadata support it.\n"
        "- Do not use examples or facts that are not present in the payload.\n\n"
        f"Payload:\n{json.dumps(payload, indent=2)}"
    )


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
            detail = response.text.strip()
            if len(detail) > 800:
                detail = detail[:800] + "..."
            raise ValueError(
                f"{provider} simulator provider returned HTTP {response.status_code}"
                + (f": {detail}" if detail else "")
            )
        return response.json()

    raise ValueError(f"{provider} simulator provider timed out after {timeout_seconds:.0f}s") from last_timeout


def _default_base_url(provider: str) -> str:
    if provider == "openai":
        return "https://api.openai.com/v1"
    if provider == "anthropic":
        return "https://api.anthropic.com/v1"
    if provider == "ollama":
        return "http://127.0.0.1:11434/v1"
    raise ValueError(f"Unsupported STUDIO_SIMULATOR_PROVIDER: {provider}")


def _normalize_model_result(result: dict[str, Any]) -> dict[str, Any]:
    cases = result.get("cases")
    if not isinstance(cases, list):
        raise ValueError("Simulator provider response must include cases array")
    normalized_cases = []
    for item in cases:
        if not isinstance(item, dict):
            continue
        probe_id = _normalize_optional_string(item.get("probe_id"))
        if not probe_id:
            continue
        selected_capability_id = _normalize_optional_string(item.get("selected_capability_id"))
        actual_outcome = _normalize_outcome(item.get("actual_outcome"))
        parameter_plan = item.get("parameter_plan") if isinstance(item.get("parameter_plan"), dict) else {}
        hints = item.get("used_consumability_hints")
        normalized_cases.append({
            "probe_id": probe_id,
            "selected_capability_id": selected_capability_id,
            "actual_outcome": actual_outcome,
            "parameter_plan": parameter_plan,
            "used_consumability_hints": [str(value) for value in hints] if isinstance(hints, list) else [],
            "rationale": str(item.get("rationale") or ""),
            "confidence": _bounded_float(item.get("confidence"), default=0.0),
        })
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    return {
        "cases": normalized_cases,
        "summary": summary,
    }


def _normalize_outcome(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"success", "clarification_required", "denied", "approval_required", "unsupported"}:
        return normalized
    return "unsupported"


def _bounded_float(value: Any, *, default: float) -> float:
    normalized = _normalize_float(value)
    if normalized is None:
        return default
    return min(1.0, max(0.0, normalized))
