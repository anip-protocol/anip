# ANIP DevOps Infrastructure Showcase

A governance-focused demonstration of ANIP's protocol features using a DevOps infrastructure domain. The centerpiece is the **scope-bound rollback token** — showing how a token can be scoped to a single capability (rollback) via `infra.deploy` scope, blocking scale and delete operations even though the issuer has broader authority. Purpose parameters (e.g., `target_service`) are carried as metadata but not enforced by the handler — scope enforcement is what actually restricts the token.

## What This Demonstrates

| ANIP Feature | How It Appears |
|---|---|
| **Scope-bound tokens** (centerpiece) | Platform engineer issues a rollback-only token (infra.deploy scope); token can rollback but cannot scale or delete. Purpose parameters carried as metadata. |
| Side-effect types | All four types present: read (list deployments, health), write (scale, config), transactional (rollback with 2h window), irreversible (delete) |
| Health / observability | `/-/health` endpoint, observability hooks logging invocation start/end with timing |
| Scoped delegation | Platform engineer -> app-developer -> CI agent, each narrowing scope |
| Repeated-denial aggregation | Three consecutive delete attempts denied; with `aggregation_window=60`, these will be aggregated after the window closes (~60s). The demo audit step may show individual entries if queried before flush. |
| Scope enforcement | CI agent with read+write scope blocked from admin-only `delete_resource`, with structured failure and resolution |

## Capabilities

- `list_deployments` -- read. List all current service deployments and their status.
- `get_service_health` -- read. Get health and performance metrics for a specific service.
- `scale_replicas` -- write. Scale the replica count for a service deployment.
- `update_config` -- write. Update a configuration key-value pair for a service.
- `rollback_deployment` -- transactional, 2h rollback window. Roll back a service deployment to a previous version.
- `delete_resource` -- irreversible. Permanently delete an infrastructure resource (cannot be undone).

## Running

```bash
# Install dependencies (from repo root)
pip install -r examples/showcase/devops/requirements.txt

# Start the service
cd examples/showcase/devops
python app.py

# In another terminal: run the demo
python demo.py
```

## Endpoints

- **ANIP Protocol:** `http://localhost:8000/.well-known/anip`
- **REST API:** `http://localhost:8000/rest/openapi.json`
- **GraphQL:** `http://localhost:8000/graphql`
- **MCP:** `http://localhost:8000/mcp`
- **Health:** `http://localhost:8000/-/health`

## API Keys

| Key | Principal |
|---|---|
| `platform-key` | `human:platform-engineer@example.com` |
| `appteam-key` | `human:app-developer@example.com` |
| `ci-key` | `agent:ci-pipeline` |

## Configuration

| Variable | Default | Description |
|---|---|---|
| `ANIP_STORAGE` | `:memory:` | Storage DSN (`:memory:` or `sqlite:///path.db`) |
| `ANIP_TRUST_LEVEL` | `signed` | Trust level (`signed` or `anchored`) |
| `ANIP_KEY_PATH` | `./anip-keys` | Key directory |
| `PORT` | `8000` | HTTP port |

## Scope-Bound Rollback Token

The demo's centerpiece shows how a platform engineer can issue a narrowly-scoped token for incident response:

```python
{
    "subject": "agent:ci-pipeline",
    "scope": ["infra.deploy"],
    "capability": "rollback_deployment",
    "purpose_parameters": {
        "reason": "incident-response",
        "target_service": "api-gateway",
    },
}
```

This token grants only `rollback_deployment` capability via `infra.deploy` scope. Attempts to use it for `scale_replicas` (requires `infra.write`) or `delete_resource` (requires `infra.admin`) are rejected with structured failure responses including resolution guidance.

**Note:** The `purpose_parameters` (reason, target_service) are carried as token metadata but are not enforced by the handler — the scope restriction is what actually constrains the token. Handler-level purpose parameter enforcement is a future enhancement.
