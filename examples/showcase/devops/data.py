"""Mock infrastructure data and in-memory store for the DevOps showcase."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Deployment:
    """A deployed service."""
    name: str
    version: str
    replicas: int
    status: str  # "running" | "degraded" | "stopped"
    environment: str  # "production" | "staging"


@dataclass
class ServiceHealth:
    """Health status for a service."""
    name: str
    status: str  # "healthy" | "degraded" | "unhealthy"
    uptime_seconds: int
    error_rate: float
    latency_p50_ms: int
    latency_p99_ms: int


@dataclass
class ScaleEvent:
    """A completed scale operation."""
    event_id: str
    service_name: str
    previous_replicas: int
    new_replicas: int
    initiated_by: str
    on_behalf_of: str
    status: str = "completed"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class ConfigChange:
    """A configuration change."""
    change_id: str
    service_name: str
    key: str
    previous_value: str | None
    new_value: str
    initiated_by: str
    on_behalf_of: str
    status: str = "applied"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class RollbackEvent:
    """A deployment rollback."""
    rollback_id: str
    service_name: str
    from_version: str
    to_version: str
    initiated_by: str
    on_behalf_of: str
    status: str = "completed"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class DeletionEvent:
    """A resource deletion."""
    deletion_id: str
    resource_type: str
    resource_name: str
    initiated_by: str
    on_behalf_of: str
    status: str = "deleted"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class EnvironmentDestroyEvent:
    """A complete environment destruction."""
    destroy_id: str
    environment_name: str
    services_removed: int
    initiated_by: str
    on_behalf_of: str
    status: str = "destroyed"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# Static infrastructure data
# ---------------------------------------------------------------------------

DEPLOYMENTS: list[Deployment] = [
    Deployment("api-gateway", "v2.3.1", 3, "running", "production"),
    Deployment("user-service", "v1.8.0", 2, "running", "production"),
    Deployment("payment-service", "v3.1.2", 4, "running", "production"),
    Deployment("notification-service", "v1.2.5", 2, "degraded", "production"),
]

_DEPLOYMENT_INDEX: dict[str, Deployment] = {d.name: d for d in DEPLOYMENTS}

SERVICE_HEALTH: dict[str, ServiceHealth] = {
    "api-gateway": ServiceHealth("api-gateway", "healthy", 864000, 0.001, 12, 45),
    "user-service": ServiceHealth("user-service", "healthy", 432000, 0.002, 25, 80),
    "payment-service": ServiceHealth("payment-service", "healthy", 259200, 0.0005, 35, 120),
    "notification-service": ServiceHealth("notification-service", "degraded", 86400, 0.05, 150, 800),
}

# Version history for rollback support
VERSION_HISTORY: dict[str, list[str]] = {
    "api-gateway": ["v2.3.1", "v2.3.0", "v2.2.0", "v2.1.0", "v1.0.0"],
    "user-service": ["v1.8.0", "v1.7.2", "v1.7.0", "v1.6.0", "v1.0.0"],
    "payment-service": ["v3.1.2", "v3.1.0", "v3.0.0", "v2.0.0", "v1.0.0"],
    "notification-service": ["v1.2.5", "v1.2.0", "v1.1.0", "v1.0.0"],
}

# Configuration store: service_name -> {key: value}
CONFIG_STORE: dict[str, dict[str, str]] = {
    "api-gateway": {"log_level": "info", "rate_limit": "1000", "timeout_ms": "5000"},
    "user-service": {"log_level": "info", "max_connections": "100", "cache_ttl": "300"},
    "payment-service": {"log_level": "warn", "retry_count": "3", "timeout_ms": "10000"},
    "notification-service": {"log_level": "debug", "batch_size": "50", "retry_count": "5"},
}

# In-memory event stores
_SCALE_EVENTS: dict[str, ScaleEvent] = {}
_CONFIG_CHANGES: dict[str, ConfigChange] = {}
_ROLLBACK_EVENTS: dict[str, RollbackEvent] = {}
_DELETION_EVENTS: dict[str, DeletionEvent] = {}
_DESTROY_EVENTS: dict[str, EnvironmentDestroyEvent] = {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_deployments() -> list[dict]:
    """Return current deployments."""
    return [
        {
            "name": d.name,
            "version": d.version,
            "replicas": d.replicas,
            "status": d.status,
            "environment": d.environment,
        }
        for d in DEPLOYMENTS
    ]


def get_service_health(service_name: str) -> dict | None:
    """Return health data for a service."""
    health = SERVICE_HEALTH.get(service_name)
    if health is None:
        return None
    return {
        "name": health.name,
        "status": health.status,
        "uptime_seconds": health.uptime_seconds,
        "error_rate": health.error_rate,
        "latency_p50_ms": health.latency_p50_ms,
        "latency_p99_ms": health.latency_p99_ms,
    }


def scale_replicas(
    service_name: str,
    replicas: int,
    initiated_by: str = "",
    on_behalf_of: str = "",
) -> ScaleEvent:
    """Scale a service to the given replica count."""
    deployment = _DEPLOYMENT_INDEX.get(service_name)
    if deployment is None:
        raise ValueError(f"Unknown service: {service_name}")
    if replicas <= 0:
        raise ValueError("Replica count must be positive")
    if replicas > 20:
        raise ValueError("Replica count cannot exceed 20")

    previous = deployment.replicas
    deployment.replicas = replicas

    event = ScaleEvent(
        event_id=f"SC-{uuid.uuid4().hex[:8].upper()}",
        service_name=service_name,
        previous_replicas=previous,
        new_replicas=replicas,
        initiated_by=initiated_by,
        on_behalf_of=on_behalf_of,
    )
    _SCALE_EVENTS[event.event_id] = event
    return event


def update_config(
    service_name: str,
    key: str,
    value: str,
    initiated_by: str = "",
    on_behalf_of: str = "",
) -> ConfigChange:
    """Update a configuration key for a service."""
    if service_name not in CONFIG_STORE:
        raise ValueError(f"Unknown service: {service_name}")

    config = CONFIG_STORE[service_name]
    previous = config.get(key)
    config[key] = value

    change = ConfigChange(
        change_id=f"CF-{uuid.uuid4().hex[:8].upper()}",
        service_name=service_name,
        key=key,
        previous_value=previous,
        new_value=value,
        initiated_by=initiated_by,
        on_behalf_of=on_behalf_of,
    )
    _CONFIG_CHANGES[change.change_id] = change
    return change


def rollback_deployment(
    service_name: str,
    target_version: str,
    initiated_by: str = "",
    on_behalf_of: str = "",
) -> RollbackEvent:
    """Roll back a service to a previous version."""
    deployment = _DEPLOYMENT_INDEX.get(service_name)
    if deployment is None:
        raise ValueError(f"Unknown service: {service_name}")

    history = VERSION_HISTORY.get(service_name, [])
    if target_version not in history:
        raise ValueError(f"Version {target_version} not found in history for {service_name}")
    if target_version == deployment.version:
        raise ValueError(f"{service_name} is already at version {target_version}")

    from_version = deployment.version
    deployment.version = target_version

    event = RollbackEvent(
        rollback_id=f"RB-{uuid.uuid4().hex[:8].upper()}",
        service_name=service_name,
        from_version=from_version,
        to_version=target_version,
        initiated_by=initiated_by,
        on_behalf_of=on_behalf_of,
    )
    _ROLLBACK_EVENTS[event.rollback_id] = event
    return event


def delete_resource(
    resource_type: str,
    resource_name: str,
    initiated_by: str = "",
    on_behalf_of: str = "",
) -> DeletionEvent:
    """Permanently delete a resource."""
    valid_types = {"deployment", "config", "service"}
    if resource_type not in valid_types:
        raise ValueError(f"Invalid resource type: {resource_type}; must be one of {valid_types}")

    # For deployments, actually remove from the list
    if resource_type == "deployment":
        deployment = _DEPLOYMENT_INDEX.pop(resource_name, None)
        if deployment is None:
            raise ValueError(f"Deployment {resource_name} not found")
        DEPLOYMENTS[:] = [d for d in DEPLOYMENTS if d.name != resource_name]
        SERVICE_HEALTH.pop(resource_name, None)
        VERSION_HISTORY.pop(resource_name, None)
        CONFIG_STORE.pop(resource_name, None)
    elif resource_type == "config":
        if resource_name not in CONFIG_STORE:
            raise ValueError(f"Config for {resource_name} not found")
        del CONFIG_STORE[resource_name]
    elif resource_type == "service":
        # Remove everything associated with the service
        deployment = _DEPLOYMENT_INDEX.pop(resource_name, None)
        if deployment is None:
            raise ValueError(f"Service {resource_name} not found")
        DEPLOYMENTS[:] = [d for d in DEPLOYMENTS if d.name != resource_name]
        SERVICE_HEALTH.pop(resource_name, None)
        VERSION_HISTORY.pop(resource_name, None)
        CONFIG_STORE.pop(resource_name, None)

    event = DeletionEvent(
        deletion_id=f"DL-{uuid.uuid4().hex[:8].upper()}",
        resource_type=resource_type,
        resource_name=resource_name,
        initiated_by=initiated_by,
        on_behalf_of=on_behalf_of,
    )
    _DELETION_EVENTS[event.deletion_id] = event
    return event


def destroy_environment(
    environment_name: str,
    initiated_by: str = "",
    on_behalf_of: str = "",
) -> EnvironmentDestroyEvent:
    """Irreversibly destroy all services in an environment."""
    valid_envs = {"staging", "development", "preview"}
    if environment_name not in valid_envs:
        raise ValueError(
            f"Cannot destroy environment '{environment_name}'. "
            f"Only non-production environments may be destroyed: {sorted(valid_envs)}"
        )

    # Count and remove all deployments in this environment
    to_remove = [d for d in DEPLOYMENTS if d.environment == environment_name]
    services_removed = len(to_remove)

    for deployment in to_remove:
        _DEPLOYMENT_INDEX.pop(deployment.name, None)
        SERVICE_HEALTH.pop(deployment.name, None)
        VERSION_HISTORY.pop(deployment.name, None)
        CONFIG_STORE.pop(deployment.name, None)

    DEPLOYMENTS[:] = [d for d in DEPLOYMENTS if d.environment != environment_name]

    event = EnvironmentDestroyEvent(
        destroy_id=f"DE-{uuid.uuid4().hex[:8].upper()}",
        environment_name=environment_name,
        services_removed=services_removed,
        initiated_by=initiated_by,
        on_behalf_of=on_behalf_of,
    )
    _DESTROY_EVENTS[event.destroy_id] = event
    return event
