# DevOps Infrastructure Showcase Source Specification

This is the Studio source document for the DevOps Infrastructure Showcase example package.
It is intentionally compact: the example is for learning ANIP contracts, registry packages,
and generated code, not for production business completeness.

## Purpose

DevOps example focused on deployment read surfaces, write controls, scoped rollback, irreversible deletion, and non-delegable destructive actions.

## Service Boundary

- Service ID: `devops-infra-service`
- Service name: DevOps Infrastructure Service
- Legacy implementation reference: `examples/showcase/devops`

The generated ANIP substrate should expose the contract and leave domain-specific behavior in
implementation material or backend adapters.

## Capabilities

- `devops.list_deployments`: List current service deployments and status. Scope: `infra.read`. Side effect: `read`.
- `devops.get_service_health`: Get health and performance metrics for a service. Scope: `infra.read`. Side effect: `read`.
- `devops.scale_replicas`: Scale the replica count for a deployment. Scope: `infra.write`. Side effect: `write`.
- `devops.update_config`: Update a configuration key-value pair for a service. Scope: `infra.write`. Side effect: `write`.
- `devops.rollback_deployment`: Roll back a service deployment to a previous version. Scope: `infra.deploy`. Side effect: `transactional`.
- `devops.delete_resource`: Permanently delete an infrastructure resource. Scope: `infra.admin`. Side effect: `irreversible`.
- `devops.destroy_environment`: Permanently destroy a non-production environment; direct principal action is required. Scope: `infra.admin`. Side effect: `irreversible`.

## Review Decisions

- Keep the example single-service unless a tutorial explicitly demonstrates cross-service behavior.
- Treat write, transactional, irreversible, and approval-gated operations as authority-sensitive.
- Require explicit business inputs rather than guessing missing identifiers, account names, service names, quote IDs, or quantities.
- Preserve the old hand-built app as reference implementation material, not as the signed behavior contract.
