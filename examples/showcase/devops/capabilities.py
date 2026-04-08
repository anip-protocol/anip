"""DevOps infrastructure capabilities — ANIP capability declarations and handlers."""
from anip_service import Capability, InvocationContext, ANIPError
from anip_core import (
    CapabilityDeclaration, CapabilityInput, CapabilityOutput,
    Cost, CostCertainty, ObservabilityContract, SessionInfo,
    SideEffect, SideEffectType,
)
import data


# ---------------------------------------------------------------------------
# 1. list_deployments — read-only, scope: infra.read
# ---------------------------------------------------------------------------

_LIST_DEPLOYMENTS_DECL = CapabilityDeclaration(
    name="list_deployments",
    description="List all current service deployments and their status",
    contract_version="1.0",
    inputs=[],
    output=CapabilityOutput(
        type="deployment_list",
        fields=["deployments", "count"],
    ),
    side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
    minimum_scope=["infra.read"],
    cost=Cost(certainty=CostCertainty.FIXED, financial=None, compute={"latency_p50": "50ms", "tokens": 400}),
    session=SessionInfo(),
    observability=ObservabilityContract(
        logged=True, retention="P7D",
        fields_logged=["capability", "parameters", "result_count"],
        audit_accessible_by=["delegation.root_principal"],
    ),
)


def _handle_list_deployments(ctx: InvocationContext, params: dict) -> dict:
    deployments = data.list_deployments()
    return {
        "deployments": deployments,
        "count": len(deployments),
    }


list_deployments = Capability(declaration=_LIST_DEPLOYMENTS_DECL, handler=_handle_list_deployments)


# ---------------------------------------------------------------------------
# 2. get_service_health — read-only, scope: infra.read
# ---------------------------------------------------------------------------

_SERVICE_HEALTH_DECL = CapabilityDeclaration(
    name="get_service_health",
    description="Get health and performance metrics for a specific service",
    contract_version="1.0",
    inputs=[
        CapabilityInput(name="service_name", type="string", description="Name of the service to check"),
    ],
    output=CapabilityOutput(
        type="service_health",
        fields=["name", "status", "uptime_seconds", "error_rate", "latency_p50_ms", "latency_p99_ms"],
    ),
    side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
    minimum_scope=["infra.read"],
    cost=Cost(certainty=CostCertainty.FIXED, financial=None, compute={"latency_p50": "30ms", "tokens": 200}),
    session=SessionInfo(),
    observability=ObservabilityContract(
        logged=True, retention="P7D",
        fields_logged=["capability", "parameters", "result"],
        audit_accessible_by=["delegation.root_principal"],
    ),
)


def _handle_get_service_health(ctx: InvocationContext, params: dict) -> dict:
    service_name = params.get("service_name")
    if not service_name:
        raise ANIPError("invalid_parameters", "service_name is required")

    health = data.get_service_health(service_name)
    if health is None:
        raise ANIPError("capability_unavailable", f"No health data for service {service_name}")
    return health


get_service_health = Capability(declaration=_SERVICE_HEALTH_DECL, handler=_handle_get_service_health)


# ---------------------------------------------------------------------------
# 3. scale_replicas — write, scope: infra.write
# ---------------------------------------------------------------------------

_SCALE_DECL = CapabilityDeclaration(
    name="scale_replicas",
    description="Scale the replica count for a service deployment",
    contract_version="1.0",
    inputs=[
        CapabilityInput(name="service_name", type="string", description="Service to scale"),
        CapabilityInput(name="replicas", type="integer", description="Target replica count (1-20)"),
    ],
    output=CapabilityOutput(
        type="scale_confirmation",
        fields=["event_id", "service_name", "previous_replicas", "new_replicas", "status"],
    ),
    side_effect=SideEffect(type=SideEffectType.WRITE, rollback_window="not_applicable"),
    minimum_scope=["infra.write"],
    cost=Cost(certainty=CostCertainty.FIXED, financial=None, compute={"latency_p50": "200ms", "tokens": 300}),
    session=SessionInfo(),
    observability=ObservabilityContract(
        logged=True, retention="P90D",
        fields_logged=["capability", "delegation_chain", "parameters", "result"],
        audit_accessible_by=["delegation.root_principal"],
    ),
)


def _handle_scale_replicas(ctx: InvocationContext, params: dict) -> dict:
    service_name = params.get("service_name")
    replicas = params.get("replicas")

    if not service_name:
        raise ANIPError("invalid_parameters", "service_name is required")
    if replicas is None:
        raise ANIPError("invalid_parameters", "replicas is required")

    try:
        event = data.scale_replicas(
            service_name=service_name,
            replicas=int(replicas),
            initiated_by=ctx.subject,
            on_behalf_of=ctx.root_principal,
        )
    except ValueError as exc:
        raise ANIPError("invalid_parameters", str(exc))

    return {
        "event_id": event.event_id,
        "service_name": event.service_name,
        "previous_replicas": event.previous_replicas,
        "new_replicas": event.new_replicas,
        "status": event.status,
    }


scale_replicas = Capability(declaration=_SCALE_DECL, handler=_handle_scale_replicas)


# ---------------------------------------------------------------------------
# 4. update_config — write, scope: infra.write
# ---------------------------------------------------------------------------

_CONFIG_DECL = CapabilityDeclaration(
    name="update_config",
    description="Update a configuration key-value pair for a service",
    contract_version="1.0",
    inputs=[
        CapabilityInput(name="service_name", type="string", description="Service to configure"),
        CapabilityInput(name="key", type="string", description="Configuration key to set"),
        CapabilityInput(name="value", type="string", description="New value for the key"),
    ],
    output=CapabilityOutput(
        type="config_change",
        fields=["change_id", "service_name", "key", "previous_value", "new_value", "status"],
    ),
    side_effect=SideEffect(type=SideEffectType.WRITE, rollback_window="not_applicable"),
    minimum_scope=["infra.write"],
    cost=Cost(certainty=CostCertainty.FIXED, financial=None, compute={"latency_p50": "100ms", "tokens": 300}),
    session=SessionInfo(),
    observability=ObservabilityContract(
        logged=True, retention="P90D",
        fields_logged=["capability", "delegation_chain", "parameters", "result"],
        audit_accessible_by=["delegation.root_principal"],
    ),
)


def _handle_update_config(ctx: InvocationContext, params: dict) -> dict:
    service_name = params.get("service_name")
    key = params.get("key")
    value = params.get("value")

    if not service_name:
        raise ANIPError("invalid_parameters", "service_name is required")
    if not key:
        raise ANIPError("invalid_parameters", "key is required")
    if value is None:
        raise ANIPError("invalid_parameters", "value is required")

    try:
        change = data.update_config(
            service_name=service_name,
            key=key,
            value=str(value),
            initiated_by=ctx.subject,
            on_behalf_of=ctx.root_principal,
        )
    except ValueError as exc:
        raise ANIPError("invalid_parameters", str(exc))

    return {
        "change_id": change.change_id,
        "service_name": change.service_name,
        "key": change.key,
        "previous_value": change.previous_value,
        "new_value": change.new_value,
        "status": change.status,
    }


update_config = Capability(declaration=_CONFIG_DECL, handler=_handle_update_config)


# ---------------------------------------------------------------------------
# 5. rollback_deployment — transactional, rollback_window: PT2H, scope: infra.deploy
# ---------------------------------------------------------------------------

_ROLLBACK_DECL = CapabilityDeclaration(
    name="rollback_deployment",
    description="Roll back a service deployment to a previous version",
    contract_version="1.0",
    inputs=[
        CapabilityInput(name="service_name", type="string", description="Service to roll back"),
        CapabilityInput(name="target_version", type="string", description="Version to roll back to"),
    ],
    output=CapabilityOutput(
        type="rollback_confirmation",
        fields=["rollback_id", "service_name", "from_version", "to_version", "status"],
    ),
    side_effect=SideEffect(type=SideEffectType.TRANSACTIONAL, rollback_window="PT2H"),
    minimum_scope=["infra.deploy"],
    cost=Cost(certainty=CostCertainty.FIXED, financial=None, compute={"latency_p50": "2s", "tokens": 500}),
    session=SessionInfo(),
    observability=ObservabilityContract(
        logged=True, retention="P365D",
        fields_logged=["capability", "delegation_chain", "parameters", "result"],
        audit_accessible_by=["delegation.root_principal"],
    ),
)


def _handle_rollback_deployment(ctx: InvocationContext, params: dict) -> dict:
    service_name = params.get("service_name")
    target_version = params.get("target_version")

    if not service_name:
        raise ANIPError("invalid_parameters", "service_name is required")
    if not target_version:
        raise ANIPError("invalid_parameters", "target_version is required")

    try:
        event = data.rollback_deployment(
            service_name=service_name,
            target_version=target_version,
            initiated_by=ctx.subject,
            on_behalf_of=ctx.root_principal,
        )
    except ValueError as exc:
        raise ANIPError(
            "invalid_parameters", str(exc),
            resolution={
                "action": "list_deployments",
                "recovery_class": "refresh_then_retry",
                "recovery_target": {
                    "kind": "refresh",
                    "target": {"service": "devops-infra", "capability": "list_deployments"},
                    "continuity": "same_task",
                    "retry_after_target": True,
                },
            },
        )

    return {
        "rollback_id": event.rollback_id,
        "service_name": event.service_name,
        "from_version": event.from_version,
        "to_version": event.to_version,
        "status": event.status,
    }


rollback_deployment = Capability(declaration=_ROLLBACK_DECL, handler=_handle_rollback_deployment)


# ---------------------------------------------------------------------------
# 6. delete_resource — irreversible, scope: infra.admin
# ---------------------------------------------------------------------------

_DELETE_DECL = CapabilityDeclaration(
    name="delete_resource",
    description="Permanently delete an infrastructure resource (cannot be undone)",
    contract_version="1.0",
    inputs=[
        CapabilityInput(name="resource_type", type="string", description="Type of resource: deployment, config, or service"),
        CapabilityInput(name="resource_name", type="string", description="Name of the resource to delete"),
    ],
    output=CapabilityOutput(
        type="deletion_confirmation",
        fields=["deletion_id", "resource_type", "resource_name", "status"],
    ),
    side_effect=SideEffect(type=SideEffectType.IRREVERSIBLE, rollback_window="none"),
    minimum_scope=["infra.admin"],
    cost=Cost(certainty=CostCertainty.FIXED, financial=None, compute={"latency_p50": "500ms", "tokens": 300}),
    session=SessionInfo(),
    verify_via=["list_deployments"],
    observability=ObservabilityContract(
        logged=True, retention="P365D",
        fields_logged=["capability", "delegation_chain", "parameters", "result"],
        audit_accessible_by=["delegation.root_principal"],
    ),
)


def _handle_delete_resource(ctx: InvocationContext, params: dict) -> dict:
    resource_type = params.get("resource_type")
    resource_name = params.get("resource_name")

    if not resource_type:
        raise ANIPError("invalid_parameters", "resource_type is required")
    if not resource_name:
        raise ANIPError("invalid_parameters", "resource_name is required")

    try:
        event = data.delete_resource(
            resource_type=resource_type,
            resource_name=resource_name,
            initiated_by=ctx.subject,
            on_behalf_of=ctx.root_principal,
        )
    except ValueError as exc:
        raise ANIPError(
            "invalid_parameters", str(exc),
            resolution={
                "action": "list_deployments",
                "recovery_class": "refresh_then_retry",
                "recovery_target": {
                    "kind": "revalidation",
                    "target": {"service": "devops-infra", "capability": "list_deployments"},
                    "continuity": "same_task",
                    "retry_after_target": True,
                },
            },
        )

    return {
        "deletion_id": event.deletion_id,
        "resource_type": event.resource_type,
        "resource_name": event.resource_name,
        "status": event.status,
    }


delete_resource = Capability(declaration=_DELETE_DECL, handler=_handle_delete_resource)


# ---------------------------------------------------------------------------
# 7. destroy_environment — irreversible, non-delegable, scope: infra.admin
# ---------------------------------------------------------------------------

_DESTROY_ENV_DECL = CapabilityDeclaration(
    name="destroy_environment",
    description=(
        "Permanently destroy all services and configuration in a non-production environment. "
        "This action is irreversible. Requires direct principal action — cannot be delegated."
    ),
    contract_version="1.0",
    inputs=[
        CapabilityInput(
            name="environment_name",
            type="string",
            description="Name of the environment to destroy (staging, development, or preview only)",
        ),
    ],
    output=CapabilityOutput(
        type="destroy_confirmation",
        fields=["destroy_id", "environment_name", "services_removed", "status"],
    ),
    side_effect=SideEffect(type=SideEffectType.IRREVERSIBLE, rollback_window="none"),
    minimum_scope=["infra.admin"],
    cost=Cost(certainty=CostCertainty.FIXED, financial=None, compute={"latency_p50": "5s", "tokens": 400}),
    session=SessionInfo(),
    observability=ObservabilityContract(
        logged=True, retention="P730D",
        fields_logged=["capability", "delegation_chain", "parameters", "result"],
        audit_accessible_by=["delegation.root_principal"],
    ),
)


def _handle_destroy_environment(ctx: InvocationContext, params: dict) -> dict:
    # Non-delegable: only the root principal (the direct human) may invoke this.
    # A delegated agent will have ctx.subject != ctx.root_principal.
    if ctx.subject != ctx.root_principal:
        raise ANIPError(
            "non_delegable_action",
            "destroy_environment requires direct principal action and cannot be delegated",
            resolution={
                "action": "escalate_to_principal",
                "recovery_class": "redelegation",
                "grantable_by": "delegation.root_principal",
                "recovery_target": {
                    "kind": "redelegation",
                    "continuity": "same_task",
                    "retry_after_target": True,
                },
            },
        )

    environment_name = params.get("environment_name")
    if not environment_name:
        raise ANIPError("invalid_parameters", "environment_name is required")

    try:
        event = data.destroy_environment(
            environment_name=environment_name,
            initiated_by=ctx.subject,
            on_behalf_of=ctx.root_principal,
        )
    except ValueError as exc:
        raise ANIPError("invalid_parameters", str(exc))

    return {
        "destroy_id": event.destroy_id,
        "environment_name": event.environment_name,
        "services_removed": event.services_removed,
        "status": event.status,
    }


destroy_environment = Capability(declaration=_DESTROY_ENV_DECL, handler=_handle_destroy_environment)
