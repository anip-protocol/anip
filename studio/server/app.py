"""Thin validation API wrapping the ANIP evaluator, plus project workspace API."""

from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request as URLRequest
from urllib.request import urlopen

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from psycopg.types.json import Json

ROOT = Path(__file__).resolve().parents[2]

# Add local packages to Python path so Studio can mount real ANIP services.
for path in [
    ROOT / "tooling" / "bin",
    ROOT / "packages" / "python" / "anip-core" / "src",
    ROOT / "packages" / "python" / "anip-crypto" / "src",
    ROOT / "packages" / "python" / "anip-server" / "src",
    ROOT / "packages" / "python" / "anip-service" / "src",
    ROOT / "packages" / "python" / "anip-fastapi" / "src",
]:
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from anip_fastapi import mount_anip  # noqa: E402
from anip_design_validate import evaluate, validate_payload  # noqa: E402
from .derivation import build_shape_backed_proposal  # noqa: E402
from .assistant_provider import (  # noqa: E402
    load_assistant_provider_resolution,
    save_persisted_assistant_provider_settings,
    studio_read_only_enabled,
    studio_read_only_reason,
)
from .simulator_provider import (  # noqa: E402
    load_simulator_provider_resolution,
    run_agent_consumption_simulation,
    save_persisted_simulator_provider_settings,
)
from .assistant_service import create_studio_assistant_service  # noqa: E402
from .workbench_service import create_studio_workbench_service  # noqa: E402

from .db import check_ready, get_pool, init_db, migration_status, set_database_url  # noqa: E402
from .models import AgentConsumptionSimulationRequest, AgentConsumptionSimulationResult, AssistantRuntimeConfigOut, RegistryTrustPolicyOut, RuntimeStatusOut, SimulatorRuntimeConfigOut, StudioSettingsOut, UpdateAssistantRuntimeConfig, UpdateSimulatorRuntimeConfig, UpdateStudioSettings  # noqa: E402
from .repository import load_vocabulary_defaults  # noqa: E402
from .publication_guard import validate_publication_saved_revision  # noqa: E402
from .routers import projects, artifacts, shapes, vocabulary, import_export, workspaces, data_access_projects, application_integration_projects, integration_fronting, local_publications, registry_verification  # noqa: E402
from .seed import seed_from_examples  # noqa: E402
from .observability import StudioMetrics, configure_json_logging  # noqa: E402

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "tooling" / "schemas"
VOCAB_DEFAULTS_PATH = Path(__file__).parent / "vocabulary_defaults.json"
ASSISTANT_SERVICE = create_studio_assistant_service()
WORKBENCH_SERVICE = create_studio_workbench_service()
_REGISTRY_CONFIG_KEY = "registry_trust_policy_config"
LOGGER = configure_json_logging()
METRICS = StudioMetrics()


def _env_bool(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _env_bool_default(name: str, fallback: bool) -> bool:
    value = os.getenv(name, "").strip().lower()
    if not value:
        return fallback
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return fallback


def _startup_showcase_seed_enabled() -> bool:
    return _env_bool("STUDIO_SEED_SHOWCASES") or _env_bool("STUDIO_SEED_EXAMPLES")


def _read_only_database_url() -> str:
    if not studio_read_only_enabled():
        return ""
    return os.getenv("STUDIO_READ_ONLY_DATABASE_URL", "").strip()


class ValidateRequest(BaseModel):
    requirements: dict
    proposal: dict
    scenario: dict


class ValidateShapeRequest(BaseModel):
    requirements: dict
    shape: dict
    scenario: dict


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations = _env_bool_default("STUDIO_RUN_MIGRATIONS", True)
    seed_showcases = _startup_showcase_seed_enabled()
    read_only_database_url = _read_only_database_url()
    prepare_with_writer = run_migrations or seed_showcases or not read_only_database_url

    if run_migrations:
        init_db()
    else:
        LOGGER.info("studio_migrations_skipped", extra={"event": "studio_migrations_skipped"})
    if prepare_with_writer:
        with get_pool().connection() as conn:
            load_vocabulary_defaults(conn, str(VOCAB_DEFAULTS_PATH))
            if seed_showcases:
                seed_from_examples(conn)
    else:
        LOGGER.info(
            "studio_writable_startup_prep_skipped",
            extra={"event": "studio_writable_startup_prep_skipped"},
        )

    if read_only_database_url:
        set_database_url(read_only_database_url)
        LOGGER.info(
            "studio_runtime_database_read_only",
            extra={"event": "studio_runtime_database_read_only"},
        )

    await ASSISTANT_SERVICE.start()
    await WORKBENCH_SERVICE.start()
    try:
        yield
    finally:
        await ASSISTANT_SERVICE.shutdown()
        await WORKBENCH_SERVICE.shutdown()
        ASSISTANT_SERVICE.stop()
        WORKBENCH_SERVICE.stop()


app = FastAPI(title="ANIP Studio Validation API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_READ_ONLY_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
_READ_ONLY_ALLOWED_POST_PATHS = {
    "/api/validate",
    "/api/validate-shape",
}


@app.middleware("http")
async def enforce_studio_read_only(request: Request, call_next):
    method = request.method.upper()
    path = request.url.path
    if (
        studio_read_only_enabled()
        and method not in _READ_ONLY_SAFE_METHODS
        and not (method == "POST" and path in _READ_ONLY_ALLOWED_POST_PATHS)
    ):
        return JSONResponse(
            status_code=403,
            content={"detail": studio_read_only_reason()},
        )
    return await call_next(request)


@app.middleware("http")
async def record_studio_observability(request: Request, call_next):
    start = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        duration_seconds = time.perf_counter() - start
        route = request.scope.get("route")
        route_path = getattr(route, "path", request.url.path)
        METRICS.record_request(request.method, route_path, status_code, duration_seconds)
        LOGGER.info(
            "studio_http_request",
            extra={
                "event": "studio_http_request",
                "method": request.method,
                "route": route_path,
                "status": status_code,
                "duration_ms": int(duration_seconds * 1000),
            },
        )

# --- Include routers ---
app.include_router(projects.router)
app.include_router(workspaces.router)
app.include_router(data_access_projects.router)
app.include_router(application_integration_projects.router)
app.include_router(integration_fronting.router)
app.include_router(local_publications.router)
app.include_router(registry_verification.router)
app.include_router(artifacts.router)
app.include_router(shapes.router)
app.include_router(vocabulary.router)
app.include_router(import_export.router)
mount_anip(app, ASSISTANT_SERVICE, prefix="/studio-assistant")
mount_anip(app, WORKBENCH_SERVICE, prefix="/studio-workbench")


# --- Existing endpoints (unchanged) ---

@app.post("/api/validate")
async def validate_endpoint(req: ValidateRequest):
    try:
        validate_payload(req.requirements, SCHEMA_DIR / "requirements.schema.json")
        validate_payload(req.proposal, SCHEMA_DIR / "proposal.schema.json")
        validate_payload(req.scenario, SCHEMA_DIR / "scenario.schema.json")
        result = evaluate(req.requirements, req.proposal, req.scenario)
        validate_payload(result, SCHEMA_DIR / "evaluation.schema.json")
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.post("/api/validate-shape")
async def validate_shape_endpoint(req: ValidateShapeRequest):
    try:
        validate_payload(req.requirements, SCHEMA_DIR / "requirements.schema.json")
        validate_payload(req.shape, SCHEMA_DIR / "shape.schema.json")
        validate_payload(req.scenario, SCHEMA_DIR / "scenario.schema.json")
        proposal = build_shape_backed_proposal(req.shape, req.requirements)
        validate_payload(proposal, SCHEMA_DIR / "proposal.schema.json")
        result = evaluate(req.requirements, proposal, req.scenario)
        validate_payload(result, SCHEMA_DIR / "evaluation.schema.json")
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/readyz")
async def readyz():
    payload = {"status": "ok", "service": "anip-studio"}
    try:
        payload["migration"] = check_ready()
    except Exception as exc:
        try:
            migration = migration_status()
        except Exception as migration_exc:
            migration = {
                "applied": False,
                "applied_count": 0,
                "expected_count": 0,
                "pending": [],
                "error": str(migration_exc),
            }
        payload["status"] = "error"
        payload["migration"] = migration
        payload["error"] = str(exc)
        METRICS.record_readiness("error", migration)
        return JSONResponse(status_code=503, content=payload)
    METRICS.record_readiness("ok", payload["migration"])
    return payload


@app.get("/api/metrics")
async def metrics():
    return PlainTextResponse(
        METRICS.prometheus_text(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@app.get("/api/runtime-status", response_model=RuntimeStatusOut)
async def runtime_status():
    resolution = load_assistant_provider_resolution()
    config = resolution.config
    provider = config.provider or "deterministic"
    llm_enabled = provider not in {"", "deterministic", "none", "off"}
    api_key_configured = bool(config.api_key)
    if provider == "ollama":
        llm_ready = bool(config.model)
    elif provider in {"openai", "anthropic"}:
        llm_ready = bool(config.model and config.api_key)
    else:
        llm_ready = False
    return RuntimeStatusOut(
        studio_api_reachable=True,
        assistant_provider=provider,
        assistant_model=config.model,
        assistant_base_url=config.base_url,
        llm_enabled=llm_enabled,
        llm_ready=llm_ready,
        api_key_configured=api_key_configured,
        api_key_source=resolution.api_key_source,
        provider_source=resolution.provider_source,
        model_source=resolution.model_source,
        base_url_source=resolution.base_url_source,
        read_only_mode=studio_read_only_enabled(),
        read_only_reason=studio_read_only_reason(),
    )


@app.get("/api/runtime-config", response_model=AssistantRuntimeConfigOut)
async def runtime_config():
    resolution = load_assistant_provider_resolution()
    config = resolution.config
    return AssistantRuntimeConfigOut(
        assistant_provider=config.provider,
        assistant_model=config.model,
        assistant_base_url=config.base_url,
        temperature=config.temperature,
        timeout_seconds=config.timeout_seconds,
        strict=config.strict,
        api_key_configured=bool(config.api_key),
        stored_api_key_configured=resolution.stored_api_key_configured,
        provider_source=resolution.provider_source,
        model_source=resolution.model_source,
        base_url_source=resolution.base_url_source,
        api_key_source=resolution.api_key_source,
        temperature_source=resolution.temperature_source,
        timeout_seconds_source=resolution.timeout_seconds_source,
        strict_source=resolution.strict_source,
        read_only_mode=studio_read_only_enabled(),
        read_only_reason=studio_read_only_reason(),
    )


@app.get("/api/simulator-config", response_model=SimulatorRuntimeConfigOut)
async def simulator_config():
    resolution = load_simulator_provider_resolution()
    config = resolution.config
    return SimulatorRuntimeConfigOut(
        simulator_provider=config.provider,
        simulator_model=config.model,
        simulator_base_url=config.base_url,
        temperature=config.temperature,
        timeout_seconds=config.timeout_seconds,
        api_key_configured=bool(config.api_key),
        stored_api_key_configured=resolution.stored_api_key_configured,
        provider_source=resolution.provider_source,
        model_source=resolution.model_source,
        base_url_source=resolution.base_url_source,
        api_key_source=resolution.api_key_source,
        temperature_source=resolution.temperature_source,
        timeout_seconds_source=resolution.timeout_seconds_source,
        read_only_mode=studio_read_only_enabled(),
        read_only_reason=studio_read_only_reason(),
    )


def _first_env_value(names: tuple[str, ...]) -> tuple[str | None, str]:
    for name in names:
        value = os.environ.get(name)
        if value and value.strip():
            return value.strip(), "env"
    return None, "default"


def _normalize_optional_string(value) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _normalize_registry_mode(value) -> str | None:
    normalized = _normalize_optional_string(value)
    if normalized is None:
        return None
    normalized = normalized.lower()
    if normalized not in {"dev", "production"}:
        raise HTTPException(status_code=422, detail="required_registry_mode must be dev or production")
    return normalized


def _load_persisted_registry_trust_policy() -> dict:
    try:
        with get_pool().connection() as conn:
            row = conn.execute(
                "SELECT value FROM studio_settings WHERE key = %s",
                (_REGISTRY_CONFIG_KEY,),
            ).fetchone()
    except Exception:
        return {}
    if not row:
        return {}
    value = row.get("value")
    return value if isinstance(value, dict) else {}


def _save_persisted_registry_trust_policy(update: dict) -> dict:
    current = _load_persisted_registry_trust_policy()
    next_value = dict(current)
    if "registry_url" in update:
        next_value["registry_url"] = _normalize_optional_string(update.get("registry_url"))
    if "required_registry_mode" in update:
        next_value["required_registry_mode"] = _normalize_registry_mode(update.get("required_registry_mode"))
    if "trusted_registry_key_id" in update:
        next_value["trusted_registry_key_id"] = _normalize_optional_string(update.get("trusted_registry_key_id"))
    if update.get("clear_registry_publish_token"):
        next_value["registry_publish_token"] = None
    elif "registry_publish_token" in update:
        next_value["registry_publish_token"] = _normalize_optional_string(update.get("registry_publish_token"))

    with get_pool().connection() as conn:
        conn.execute(
            "INSERT INTO studio_settings (key, value) VALUES (%s, %s)"
            " ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()",
            (_REGISTRY_CONFIG_KEY, Json(next_value)),
        )
        conn.commit()
    return _load_persisted_registry_trust_policy()


def _resolve_registry_publish_token(stored: dict | None = None) -> tuple[str | None, str]:
    env_token = _normalize_optional_string(os.environ.get("STUDIO_REGISTRY_PUBLISH_TOKEN"))
    if env_token:
        return env_token, "env"
    if stored is None:
        stored = _load_persisted_registry_trust_policy()
    stored_token = _normalize_optional_string(stored.get("registry_publish_token"))
    if stored_token:
        return stored_token, "stored"
    return None, "none"


def _registry_trust_policy_config() -> RegistryTrustPolicyOut:
    stored = _load_persisted_registry_trust_policy()

    registry_url, registry_url_source = _first_env_value(("STUDIO_REGISTRY_URL", "VITE_REGISTRY_BACKEND_URL"))
    stored_registry_url = _normalize_optional_string(stored.get("registry_url"))
    if registry_url:
        registry_url_source = "env"
    elif stored_registry_url:
        registry_url = stored_registry_url
        registry_url_source = "stored"
    else:
        registry_url = "http://127.0.0.1:8200"
        registry_url_source = "default"
    registry_url = registry_url.rstrip("/")

    explicit_required_mode = _normalize_optional_string(os.environ.get("STUDIO_REGISTRY_REQUIRED_MODE"))
    required_mode = _normalize_registry_mode(explicit_required_mode) if explicit_required_mode else None
    stored_required_mode = _normalize_registry_mode(stored.get("required_registry_mode"))
    required_mode_source = "env" if required_mode else "unset"
    if not required_mode and stored_required_mode:
        required_mode = stored_required_mode
        required_mode_source = "stored"

    studio_mode = (
        os.environ.get("STUDIO_MODE")
        or os.environ.get("APP_ENV")
        or os.environ.get("ENVIRONMENT")
        or ""
    ).strip().lower()
    production_mode_detected = studio_mode == "production"
    if not required_mode and production_mode_detected:
        required_mode = "production"
        required_mode_source = "production-default"

    trusted_key = _normalize_optional_string(os.environ.get("STUDIO_REGISTRY_TRUSTED_KEY_ID"))
    stored_trusted_key = _normalize_optional_string(stored.get("trusted_registry_key_id"))
    trusted_key_source = "env" if trusted_key else "unset"
    if not trusted_key and stored_trusted_key:
        trusted_key = stored_trusted_key
        trusted_key_source = "stored"

    publish_token, publish_token_source = _resolve_registry_publish_token(stored)

    allows_development_registry = required_mode != "production"
    key_pinned = bool(trusted_key)
    warning = None
    if allows_development_registry:
        warning = "Development Registry mode is allowed. Use only for local development."
    elif not key_pinned:
        warning = "Production Registry mode is required, but the receipt signing key is not pinned."

    return RegistryTrustPolicyOut(
        registry_url=registry_url,
        registry_url_source=registry_url_source,
        required_registry_mode=required_mode,
        required_registry_mode_source=required_mode_source,
        trusted_registry_key_id=trusted_key,
        trusted_registry_key_id_source=trusted_key_source,
        publish_token_configured=bool(publish_token),
        publish_token_source=publish_token_source,
        production_mode_detected=production_mode_detected,
        allows_development_registry=allows_development_registry,
        key_pinned=key_pinned,
        warning=warning,
    )


@app.get("/api/settings", response_model=StudioSettingsOut)
async def studio_settings():
    return StudioSettingsOut(
        assistant=await runtime_config(),
        simulator=await simulator_config(),
        registry=_registry_trust_policy_config(),
    )


def _save_assistant_runtime_config(body: UpdateAssistantRuntimeConfig) -> None:
    payload = body.model_dump(exclude_unset=True)
    mapped_payload = {}
    if "assistant_provider" in payload:
        mapped_payload["provider"] = payload["assistant_provider"]
    if "assistant_model" in payload:
        mapped_payload["model"] = payload["assistant_model"]
    if "assistant_base_url" in payload:
        mapped_payload["base_url"] = payload["assistant_base_url"]
    if "assistant_api_key" in payload:
        mapped_payload["api_key"] = payload["assistant_api_key"]
    if "clear_assistant_api_key" in payload:
        mapped_payload["clear_api_key"] = payload["clear_assistant_api_key"]
    if "temperature" in payload:
        mapped_payload["temperature"] = payload["temperature"]
    if "timeout_seconds" in payload:
        mapped_payload["timeout_seconds"] = payload["timeout_seconds"]
    if "strict" in payload:
        mapped_payload["strict"] = payload["strict"]
    save_persisted_assistant_provider_settings(mapped_payload)


def _save_simulator_runtime_config(body: UpdateSimulatorRuntimeConfig) -> None:
    payload = body.model_dump(exclude_unset=True)
    mapped_payload = {}
    if "simulator_provider" in payload:
        mapped_payload["provider"] = payload["simulator_provider"]
    if "simulator_model" in payload:
        mapped_payload["model"] = payload["simulator_model"]
    if "simulator_base_url" in payload:
        mapped_payload["base_url"] = payload["simulator_base_url"]
    if "simulator_api_key" in payload:
        mapped_payload["api_key"] = payload["simulator_api_key"]
    if "clear_simulator_api_key" in payload:
        mapped_payload["clear_api_key"] = payload["clear_simulator_api_key"]
    if "temperature" in payload:
        mapped_payload["temperature"] = payload["temperature"]
    if "timeout_seconds" in payload:
        mapped_payload["timeout_seconds"] = payload["timeout_seconds"]
    save_persisted_simulator_provider_settings(mapped_payload)


@app.put("/api/runtime-config", response_model=AssistantRuntimeConfigOut)
async def update_runtime_config(body: UpdateAssistantRuntimeConfig):
    _save_assistant_runtime_config(body)
    return await runtime_config()


@app.put("/api/simulator-config", response_model=SimulatorRuntimeConfigOut)
async def update_simulator_config(body: UpdateSimulatorRuntimeConfig):
    _save_simulator_runtime_config(body)
    return await simulator_config()


@app.post("/api/agent-consumption-simulator/run", response_model=AgentConsumptionSimulationResult)
async def run_agent_consumption_simulator(body: AgentConsumptionSimulationRequest):
    try:
        return await run_agent_consumption_simulation(body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.put("/api/settings", response_model=StudioSettingsOut)
async def update_studio_settings(body: UpdateStudioSettings):
    if body.assistant is not None:
        _save_assistant_runtime_config(body.assistant)
    if body.simulator is not None:
        _save_simulator_runtime_config(body.simulator)
    if body.registry is not None:
        _save_persisted_registry_trust_policy(body.registry.model_dump(exclude_unset=True))
    return await studio_settings()


@app.post("/api/registry/publications")
async def publish_registry_publication(request: Request):
    return await _forward_registry_publish(request, "publications", "publication")


@app.post("/api/registry/templates")
async def publish_registry_template(request: Request):
    return await _forward_registry_publish(request, "templates", "template")


@app.get("/api/registry/templates")
async def list_registry_templates(request: Request):
    return await _forward_registry_read(
        request,
        "templates",
        "templates",
        unavailable_payload={
            "items": [],
            "warning": "Registry templates are unavailable because Studio could not reach the configured Registry. Built-in templates and empty project creation remain available.",
        },
    )


@app.get("/api/registry/templates/{template_id}/{template_version}")
async def get_registry_template(request: Request, template_id: str, template_version: str):
    registry_path = f"templates/{quote(template_id, safe='')}/{quote(template_version, safe='')}"
    return await _forward_registry_read(request, registry_path, "template")


@app.get("/api/registry/templates/{template_id}/{template_version}/download")
async def download_registry_template(request: Request, template_id: str, template_version: str):
    registry_path = f"templates/{quote(template_id, safe='')}/{quote(template_version, safe='')}/download"
    return await _forward_registry_read(request, registry_path, "template download")


async def _forward_registry_publish(request: Request, registry_path: str, label: str):
    policy = _registry_trust_policy_config()
    publish_token, _ = _resolve_registry_publish_token()
    if not publish_token:
        raise HTTPException(status_code=400, detail="Registry publish token is not configured in Studio settings or environment.")

    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid registry {label} payload.") from exc

    if registry_path == "publications":
        project_ref = str(payload.get("project_ref") or "").strip() if isinstance(payload, dict) else ""
        if not project_ref:
            raise HTTPException(status_code=422, detail="project_ref is required for package publication.")
        with get_pool().connection() as conn:
            validate_publication_saved_revision(conn, project_ref, payload)

    url = f"{policy.registry_url.rstrip('/')}/registry-api/v1/{registry_path}"
    request_body = json.dumps(payload).encode("utf-8")
    outbound = URLRequest(
        url,
        data=request_body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {publish_token}",
        },
    )
    try:
        with urlopen(outbound, timeout=30) as response:
            response_body = response.read().decode("utf-8")
            return JSONResponse(content=json.loads(response_body), status_code=response.status)
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise HTTPException(status_code=exc.code, detail=detail) from exc
    except URLError as exc:
        raise HTTPException(status_code=502, detail=f"Registry {label} publish request failed: {exc.reason}") from exc


async def _forward_registry_read(
    request: Request,
    registry_path: str,
    label: str,
    unavailable_payload: dict | None = None,
):
    policy = _registry_trust_policy_config()
    query = request.url.query
    suffix = f"?{query}" if query else ""
    url = f"{policy.registry_url.rstrip('/')}/registry-api/v1/{registry_path}{suffix}"
    outbound = URLRequest(url, method="GET", headers={"Accept": "application/json"})
    try:
        with urlopen(outbound, timeout=30) as response:
            response_body = response.read().decode("utf-8")
            return JSONResponse(content=json.loads(response_body), status_code=response.status)
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise HTTPException(status_code=exc.code, detail=detail) from exc
    except URLError as exc:
        if unavailable_payload is not None:
            return JSONResponse(content=unavailable_payload, status_code=200)
        raise HTTPException(status_code=502, detail=f"Registry {label} request failed: {exc.reason}") from exc
