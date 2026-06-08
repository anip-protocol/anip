#!/usr/bin/env python3
"""Build lightweight Studio-authored showcase packages.

These examples are intentionally smaller than the GTM showcase. They turn the
legacy hand-built Travel, Finance, and DevOps demos into source-doc -> contract
package artifacts that can be consumed by the generator and registry tooling.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_VERSION = "0.1.0"
EXAMPLE_GENERATED_AT = "2026-05-08T00:00:00Z"


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def write_json(path: Path, payload: Any) -> None:
    write_text(path, json.dumps(payload, indent=2, sort_keys=False))


def input_field(
    name: str,
    type_: str,
    summary: str,
    *,
    required: bool = True,
    default: str = "",
    allowed_values: list[str] | None = None,
    entity_reference: bool = False,
) -> dict[str, Any]:
    return {
        "input_name": name,
        "input_type": type_,
        "required": required,
        "summary": summary,
        "default_value": default,
        "allowed_values": allowed_values or [],
        "entity_reference": entity_reference,
        "clarification_hint": f"Ask for {name} when it is missing or ambiguous.",
    }


def grant_policy() -> dict[str, Any]:
    return {
        "allowed_grant_types": ["one_time", "session_bound"],
        "default_grant_type": "one_time",
        "expires_in_seconds": 900,
        "max_uses": 1,
    }


def capability(
    domain: str,
    service_id: str,
    capability_id: str,
    title: str,
    summary: str,
    *,
    intent: str,
    operation: str,
    side_effect: str,
    scope: list[str],
    output_shape: str,
    inputs: list[dict[str, Any]] | None = None,
    produces: list[str] | None = None,
    does_not_produce: list[str] | None = None,
) -> dict[str, Any]:
    approval_like = side_effect in {"write", "transactional", "irreversible", "approval_required"} or operation == "approval_gated"
    namespaced_capability_id = capability_id if "." in capability_id else f"{domain}.{capability_id}"
    return {
        "id": f"{domain}:{namespaced_capability_id}",
        "kind": "atomic",
        "source_kind": "studio_source_doc",
        "service_id": service_id,
        "capability_id": namespaced_capability_id,
        "title": title,
        "summary": summary,
        "entity_targeted": any(item.get("entity_reference") for item in inputs or []),
        "subject_kind": "business object",
        "context_type": domain,
        "output_intent": output_shape,
        "intent_type": intent,
        "operation_type": operation,
        "side_effect_level": side_effect,
        "implementation_fit": {
            "category": "custom_service_logic",
            "rationale": "The generated ANIP substrate exposes the contract; the legacy showcase app remains useful implementation material.",
        },
        "business_effects": {
            "produces": produces or ["Read bounded data"],
            "does_not_produce": does_not_produce or ["Bypass declared authority"],
        },
        "minimum_scope": scope,
        "backend_operation": capability_id,
        "path_template": f"/{capability_id}",
        "output_shape": output_shape,
        "inputs": inputs or [],
        **({"grant_policy": grant_policy()} if approval_like else {}),
    }


EXAMPLES: dict[str, dict[str, Any]] = {
    "travel": {
        "package_id": "travel-booking-showcase",
        "system_name": "Travel Booking Showcase",
        "domain": "travel",
        "service_id": "travel-booking-service",
        "service_name": "Travel Booking Service",
        "source_dir": "docs/examples/travel-showcase",
        "legacy_dir": "examples/showcase/travel",
        "port": 9110,
        "summary": "Travel booking example focused on scoped search, quote binding, booking authority, and recovery from stale or unavailable options.",
        "capabilities": [
            capability(
                "travel",
                "travel-booking-service",
                "search_flights",
                "Search flights",
                "Search available flights by origin and destination and return priced quote references.",
                intent="search",
                operation="read",
                side_effect="read",
                scope=["travel.search"],
                output_shape="flight_list",
                inputs=[
                    input_field("origin", "airport_code", "Departure airport IATA code.", entity_reference=True),
                    input_field("destination", "airport_code", "Arrival airport IATA code.", entity_reference=True),
                ],
                produces=["Summarize information", "Return bounded options"],
                does_not_produce=["Book travel", "Charge payment"],
            ),
            capability(
                "travel",
                "travel-booking-service",
                "check_availability",
                "Check availability",
                "Check seat availability and current price for a specific flight.",
                intent="inspect",
                operation="read",
                side_effect="read",
                scope=["travel.search"],
                output_shape="availability_info",
                inputs=[input_field("flight_number", "string", "Flight number to check.", entity_reference=True)],
                produces=["Read bounded data"],
                does_not_produce=["Book travel", "Charge payment"],
            ),
            capability(
                "travel",
                "travel-booking-service",
                "book_flight",
                "Book flight",
                "Book a confirmed flight reservation from a current quote.",
                intent="business_action",
                operation="approval_gated",
                side_effect="irreversible",
                scope=["travel.book"],
                output_shape="booking_confirmation",
                inputs=[
                    input_field("flight_number", "string", "Flight to book.", entity_reference=True),
                    input_field("quote_id", "object", "Priced quote returned by search_flights.", entity_reference=True),
                    input_field("passengers", "integer", "Number of passengers.", required=False, default="1"),
                ],
                produces=["Execute approved action"],
                does_not_produce=["Book without quote", "Ignore budget authority"],
            ),
            capability(
                "travel",
                "travel-booking-service",
                "cancel_booking",
                "Cancel booking",
                "Cancel an existing booking within the transactional cancellation window.",
                intent="business_action",
                operation="write",
                side_effect="transactional",
                scope=["travel.book"],
                output_shape="cancellation_confirmation",
                inputs=[input_field("booking_id", "string", "Booking identifier to cancel.", entity_reference=True)],
                produces=["Change system state"],
                does_not_produce=["Delete booking history"],
            ),
        ],
    },
    "finance": {
        "package_id": "finance-operations-showcase",
        "system_name": "Finance Operations Showcase",
        "domain": "finance",
        "service_id": "finance-ops-service",
        "service_name": "Finance Operations Service",
        "source_dir": "docs/examples/finance-showcase",
        "legacy_dir": "examples/showcase/finance",
        "port": 9120,
        "summary": "Finance example focused on read scopes, trade authority, transfer authority, and high-risk financial side effects.",
        "capabilities": [
            capability("finance", "finance-ops-service", "query_portfolio", "Query portfolio", "Query current holdings and valuations.", intent="inspect", operation="read", side_effect="read", scope=["finance.read"], output_shape="portfolio_summary", produces=["Summarize information"], does_not_produce=["Trade", "Transfer funds"]),
            capability("finance", "finance-ops-service", "get_market_data", "Get market data", "Get current market data for a ticker symbol.", intent="inspect", operation="read", side_effect="read", scope=["finance.read"], output_shape="market_data", inputs=[input_field("symbol", "string", "Ticker symbol.", entity_reference=True)], produces=["Read bounded data"], does_not_produce=["Trade"]),
            capability("finance", "finance-ops-service", "execute_trade", "Execute trade", "Execute a buy or sell trade after current market data is available.", intent="business_action", operation="approval_gated", side_effect="irreversible", scope=["finance.trade"], output_shape="trade_confirmation", inputs=[input_field("symbol", "string", "Ticker symbol.", entity_reference=True), input_field("side", "string", "Trade side.", required=False, default="buy", allowed_values=["buy", "sell"]), input_field("quantity", "integer", "Number of shares to trade.")], produces=["Execute approved action"], does_not_produce=["Trade without authority", "Ignore price context"]),
            capability("finance", "finance-ops-service", "transfer_funds", "Transfer funds", "Transfer funds between accounts with transactional recovery posture.", intent="business_action", operation="approval_gated", side_effect="transactional", scope=["finance.transfer"], output_shape="transfer_confirmation", inputs=[input_field("from_account", "string", "Source account.", entity_reference=True), input_field("to_account", "string", "Destination account.", entity_reference=True), input_field("amount", "number", "Transfer amount in USD.")], produces=["Change system state"], does_not_produce=["Transfer without authority"]),
            capability("finance", "finance-ops-service", "generate_report", "Generate report", "Generate a daily, holdings, or transaction report.", intent="business_action", operation="write", side_effect="write", scope=["finance.read"], output_shape="financial_report", inputs=[input_field("report_type", "string", "Report type.", allowed_values=["daily_summary", "holdings", "transactions"])], produces=["Draft content", "Summarize information"], does_not_produce=["Trade", "Transfer funds"]),
        ],
    },
    "devops": {
        "package_id": "devops-infrastructure-showcase",
        "system_name": "DevOps Infrastructure Showcase",
        "domain": "devops",
        "service_id": "devops-infra-service",
        "service_name": "DevOps Infrastructure Service",
        "source_dir": "docs/examples/devops-showcase",
        "legacy_dir": "examples/showcase/devops",
        "port": 9130,
        "summary": "DevOps example focused on deployment read surfaces, write controls, scoped rollback, irreversible deletion, and non-delegable destructive actions.",
        "capabilities": [
            capability("devops", "devops-infra-service", "list_deployments", "List deployments", "List current service deployments and status.", intent="inspect", operation="read", side_effect="read", scope=["infra.read"], output_shape="deployment_list", produces=["Read bounded data"], does_not_produce=["Change infrastructure"]),
            capability("devops", "devops-infra-service", "get_service_health", "Get service health", "Get health and performance metrics for a service.", intent="inspect", operation="read", side_effect="read", scope=["infra.read"], output_shape="service_health", inputs=[input_field("service_name", "string", "Service to inspect.", entity_reference=True)], produces=["Read bounded data"], does_not_produce=["Change infrastructure"]),
            capability("devops", "devops-infra-service", "scale_replicas", "Scale replicas", "Scale the replica count for a deployment.", intent="business_action", operation="write", side_effect="write", scope=["infra.write"], output_shape="scale_confirmation", inputs=[input_field("service_name", "string", "Service to scale.", entity_reference=True), input_field("replicas", "integer", "Target replica count.")], produces=["Change system state"], does_not_produce=["Delete infrastructure"]),
            capability("devops", "devops-infra-service", "update_config", "Update config", "Update a configuration key-value pair for a service.", intent="business_action", operation="write", side_effect="write", scope=["infra.write"], output_shape="config_change", inputs=[input_field("service_name", "string", "Service to configure.", entity_reference=True), input_field("key", "string", "Configuration key."), input_field("value", "string", "New configuration value.")], produces=["Change system state"], does_not_produce=["Delete infrastructure"]),
            capability("devops", "devops-infra-service", "rollback_deployment", "Rollback deployment", "Roll back a service deployment to a previous version.", intent="business_action", operation="approval_gated", side_effect="transactional", scope=["infra.deploy"], output_shape="rollback_confirmation", inputs=[input_field("service_name", "string", "Service to roll back.", entity_reference=True), input_field("target_version", "string", "Target version.")], produces=["Change system state"], does_not_produce=["Delete infrastructure"]),
            capability("devops", "devops-infra-service", "delete_resource", "Delete resource", "Permanently delete an infrastructure resource.", intent="business_action", operation="approval_gated", side_effect="irreversible", scope=["infra.admin"], output_shape="deletion_confirmation", inputs=[input_field("resource_type", "string", "Resource type.", allowed_values=["deployment", "config", "service"]), input_field("resource_name", "string", "Resource name.", entity_reference=True)], produces=["Execute approved action"], does_not_produce=["Destroy environment"]),
            capability("devops", "devops-infra-service", "destroy_environment", "Destroy environment", "Permanently destroy a non-production environment; direct principal action is required.", intent="business_action", operation="approval_gated", side_effect="irreversible", scope=["infra.admin"], output_shape="destroy_confirmation", inputs=[input_field("environment_name", "string", "Environment name.", allowed_values=["staging", "development", "preview"], entity_reference=True)], produces=["Execute approved action"], does_not_produce=["Delegate destructive environment removal"]),
        ],
    },
}


def source_doc(example: dict[str, Any]) -> str:
    caps = "\n".join(
        f"- `{cap['capability_id']}`: {cap['summary']} Scope: `{', '.join(cap['minimum_scope'])}`. Side effect: `{cap['side_effect_level']}`."
        for cap in example["capabilities"]
    )
    return f"""# {example['system_name']} Source Specification

This is the Studio source document for the {example['system_name']} example package.
It is intentionally compact: the example is for learning ANIP contracts, registry packages,
and generated code, not for production business completeness.

## Purpose

{example['summary']}

## Service Boundary

- Service ID: `{example['service_id']}`
- Service name: {example['service_name']}
- Legacy implementation reference: `{example['legacy_dir']}`

The generated ANIP substrate should expose the contract and leave domain-specific behavior in
implementation material or backend adapters.

## Capabilities

{caps}

## Review Decisions

- Keep the example single-service unless a tutorial explicitly demonstrates cross-service behavior.
- Treat write, transactional, irreversible, and approval-gated operations as authority-sensitive.
- Require explicit business inputs rather than guessing missing identifiers, account names, service names, quote IDs, or quantities.
- Preserve the old hand-built app as reference implementation material, not as the signed behavior contract.
"""


def build_definition(example_key: str, example: dict[str, Any], now: str) -> dict[str, Any]:
    service_id = example["service_id"]
    capability_ids = [cap["capability_id"] for cap in example["capabilities"]]
    return {
        "artifact_type": "anip_service_definition",
        "contract_schema_version": "anip-service-definition/v1",
        "generated_at": now,
        "identity": {
            "system_name": example["system_name"],
            "domain_name": example["domain"],
            "delivery_model": "single_service",
            "architecture_shape": "single_service",
        },
        "authority": {
            "approval_expectation": "project_specific",
            "blocked_failure_posture": "clarify_or_stop",
        },
        "audit": {
            "durable_records_required": True,
            "searchable_history_required": True,
        },
        "generation": {
            "protocols": ["https", "mcp"],
            "layout_strategy": "service_oriented",
            "selected_service_ids": [service_id],
        },
        "service_topology_bindings": [
            {
                "id": service_id,
                "service_id": service_id,
                "service_name": example["service_name"],
                "source_role": "example_service",
                "source_capabilities": capability_ids,
                "formalized_capability_ids": capability_ids,
                "owned_concept_ids": [],
            }
        ],
        "capability_formalizations": example["capabilities"],
        "permission_intent_bindings": [
            {
                "id": f"{example_key}_example_user_access",
                "actor_id": "example_user",
                "business_area": example["domain"],
                "business_area_label": f"{example['domain'].title()} Example Access",
                "access_posture": "bounded",
                "governed_outcome_type": "bounded_result",
                "governed_outcome": "Allow tutorial users to invoke declared capabilities within the scopes shown by each capability.",
                "target_service_ids": [service_id],
                "target_capability_ids": capability_ids,
                "formalization_strategy": "Generated examples keep policy simple and visible for onboarding.",
            }
        ],
        "runtime_policy_bindings": [
            {
                "id": f"{example_key}_example_user_policy",
                "source_permission_id": f"{example_key}_example_user_access",
                "actor_id": "example_user",
                "principal_selector": {"claim": "actor_id", "equals": "example_user"},
                "business_area": example["domain"],
                "business_area_label": f"{example['domain'].title()} Example Access",
                "service_ids": [service_id],
                "capability_ids": capability_ids,
                "required_scopes": sorted({scope for cap in example["capabilities"] for scope in cap["minimum_scope"]}),
                "decision": "allow_with_limits",
                "business_rule": "Use the declared capability scope and required inputs as the tutorial boundary.",
                "enforcement_notes": "Generated examples use simple policy so the contract remains readable.",
            }
        ],
        "integration_fronting": {
            "project_type": "example_showcase",
            "capability_mappings": [
                {
                    "id": f"{cap['capability_id']}_mapping",
                    "capability_id": cap["capability_id"],
                    "title": cap["title"],
                    "intent": cap["summary"],
                    "service_id": service_id,
                    "service_name": example["service_name"],
                    "backend_kind": "python_reference_adapter",
                    "connection_ref": example["legacy_dir"],
                    "raw_operation_refs": [cap["backend_operation"]],
                    "backend_input_mode": "explicit",
                    "explicit_required_backend_inputs": [item["input_name"] for item in cap["inputs"] if item["required"]],
                    "explicit_optional_backend_inputs": [item["input_name"] for item in cap["inputs"] if not item["required"]],
                    "execution_posture": cap["intent_type"],
                    "side_effect_level": cap["side_effect_level"],
                    "subject_kind": cap["subject_kind"],
                    "context_type": cap["context_type"],
                    "output_intent": cap["output_intent"],
                    "audit_required": True,
                }
                for cap in example["capabilities"]
            ],
        },
        "source": {
            "source_docs": [f"{example['source_dir']}/source-spec.md"],
            "legacy_implementation": example["legacy_dir"],
        },
    }


def build_consumability(example: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "anip-agent-consumability/v0",
        "capabilities": {
            cap["capability_id"]: {
                "intent": {
                    "category": cap["capability_id"].replace("_", "."),
                    "summary": cap["summary"],
                },
                "business_effects": cap["business_effects"],
                "required_context": [
                    {
                        "input": item["input_name"],
                        "behavior": "clarify",
                        "summary": item["summary"],
                    }
                    for item in cap["inputs"]
                    if item["required"]
                ],
            }
            for cap in example["capabilities"]
        },
    }


def build_package(example_key: str, example: dict[str, Any], definition: dict[str, Any], now: str) -> dict[str, Any]:
    package_id = example["package_id"]
    signature = digest(definition)
    consumability = build_consumability(example)
    readiness = {
        "status": "ready",
        "score": 100,
        "summary": {"blockers": 0, "warnings": 0, "info": 0, "probes": 0, "required_app_glue": 0},
    }
    lineage = {
        "project_ref": f"studio-source:{example_key}",
        "product_revision": {
            "ref": f"{example_key}:source-spec:v1",
            "artifact_id": f"{example_key}-source-spec",
            "revision_number": 1,
            "baseline_locked_at": now,
        },
        "developer_revision": {
            "ref": f"{example_key}:developer-definition:v1",
            "artifact_id": f"{example_key}-developer-definition",
            "revision_number": 1,
            "contract_signature": signature,
        },
    }
    manifest = {
        "package_kind": "anip_service_blueprint",
        "artifact_type": "anip_package_manifest",
        "blueprint_id": package_id,
        "package_id": package_id,
        "name": f"{example['system_name']} Service Blueprint",
        "version": PACKAGE_VERSION,
        "package_version": PACKAGE_VERSION,
        "schema_version": definition["contract_schema_version"],
        "publisher": {"id": "local-studio-source", "display_name": "Local Studio Source Export"},
        "service_definition": "anip-service-definition.json",
        "service_definition_digest": signature,
        "service_definition_digest_algorithm": "sha256",
        "build_packs": {"recommended": ["anip-build-pack@local"]},
        "verifier_packs": {"recommended": ["anip-verifier@local"]},
        "readme": f"# {example['system_name']}\n\nGenerated example ANIP package from Studio-style source docs.\n",
        "source_links": [
            {
                "title": "Source documentation",
                "url": f"https://github.com/anip-protocol/anip/tree/main/{example['source_dir']}",
            },
            {
                "title": "Legacy implementation reference",
                "url": f"https://github.com/anip-protocol/anip/tree/main/{example['legacy_dir']}",
            },
        ],
        "capability_count": len(example["capabilities"]),
        "service_count": 1,
        "service_ids": [example["service_id"]],
        "lineage": lineage,
        "source": {
            "business_source_path": f"{example['source_dir']}/source-spec.md",
            "product_revision_ref": f"{example_key}:source-spec:v1",
            "developer_revision_ref": f"{example_key}:developer-definition:v1",
        },
        "agent_consumption_readiness": readiness,
        "agent_consumability": consumability,
        "generated_at": now,
    }
    lock = {
        "lock_kind": "publisher_recommended_lock",
        "artifact_type": "anip_package_lock",
        "blueprint_id": package_id,
        "blueprint_version": PACKAGE_VERSION,
        "package_id": package_id,
        "package_version": PACKAGE_VERSION,
        "service_definition_digest": signature,
        "schema_version": manifest["schema_version"],
        "build_packs": manifest["build_packs"]["recommended"],
        "verifier_packs": manifest["verifier_packs"]["recommended"],
        "runtime_packages": [],
        "extension_packs": [],
        "regression_packs": [],
        "selected_service_ids": [example["service_id"]],
        "capability_ids": [cap["capability_id"] for cap in example["capabilities"]],
        "contract_signature": signature,
        "lineage": lineage,
        "agent_consumption_readiness": readiness,
        "agent_consumability": {
            "schema_version": consumability["schema_version"],
            "capability_count": len(consumability["capabilities"]),
        },
        "generated_at": now,
    }
    return {
        "bundle_schema_version": "anip-package-bundle/v1",
        "authority": "local-studio",
        "publication": {
            "package_id": package_id,
            "package_version": PACKAGE_VERSION,
            "project_ref": lineage["project_ref"],
            "product_revision_ref": lineage["product_revision"]["ref"],
            "developer_revision_ref": lineage["developer_revision"]["ref"],
            "contract_signature": signature,
            "publisher_id": "local-studio-source",
            "publisher_type": "local",
            "lineage": lineage,
            "published_at": now,
        },
        "package": {
            "package_id": package_id,
            "package_version": PACKAGE_VERSION,
            "contract_signature": signature,
            "publisher_id": "local-studio-source",
            "publisher_type": "local",
            "lineage": lineage,
            "schema_version": definition["contract_schema_version"],
            "manifest_digest": digest(manifest),
            "definition_digest": signature,
            "lock_digest": digest(lock),
            "manifest": manifest,
            "service_definition": definition,
            "recommended_lock": lock,
        },
        "receipt": {"registry_signature": "", "issued_at": now, "authority": "local-studio"},
        "lineage": lineage,
        "manifest": manifest,
        "service_definition": definition,
        "lock": lock,
        "registry_keys": [],
        "digests": {
            "manifest": digest(manifest),
            "service_definition": signature,
            "lock": digest(lock),
            "receipt": "",
        },
    }


def main() -> None:
    now = EXAMPLE_GENERATED_AT
    for key, example in EXAMPLES.items():
        definition = build_definition(key, example, now)
        package = build_package(key, example, definition, now)
        source_dir = REPO_ROOT / example["source_dir"]
        package_dir = REPO_ROOT / f"examples/showcase/{key}/registry-packages"
        base = package_dir / f"{example['package_id']}-{PACKAGE_VERSION}"
        write_text(source_dir / "source-spec.md", source_doc(example))
        write_json(base.with_name(base.name + "-service-definition.json"), definition)
        write_json(base.with_name(base.name + "-manifest.json"), package["manifest"])
        write_json(base.with_name(base.name + "-lock.json"), package["lock"])
        write_json(base.with_name(base.name + ".anip-package.json"), package)
        write_text(
            package_dir / "README.md",
            f"""# {example['system_name']} Registry Package

Generated from `{example['source_dir']}/source-spec.md`.

Generate Python code:

```bash
cd packages/go
go run ./cmd/anip-generate \\
  --package-bundle ../../examples/showcase/{key}/registry-packages/{example['package_id']}-{PACKAGE_VERSION}.anip-package.json \\
  --target python \\
  --dependency-source local \\
  --package-name anip_{key}_showcase \\
  --port {example['port']} \\
  --output ../../examples/showcase/{key}/generated/studio_{key} \\
  --force
```
""",
        )
        print(f"wrote {key}: {base}")


if __name__ == "__main__":
    main()
