"""ANIP-only Studio stress runner.

Uses the Studio assistant and Studio workbench ANIP services without falling
back to raw Studio REST.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from uuid import uuid4

from anip_client import ANIPClient

ASSISTANT_BOOTSTRAP = "studio-assistant-bootstrap"
WORKBENCH_BOOTSTRAP = "studio-workbench-bootstrap"
AGENT_SUBJECT = "agent:studio-stress"
DOGFOOD_EVAL_BUDGET = {"currency": "USD", "max_amount": 8.0}

WORKBENCH_SCOPES = [
    "studio.workbench.create_workspace",
    "studio.workbench.create_project",
    "studio.workbench.accept_first_design",
    "studio.workbench.evaluate_service_design",
    "studio.workbench.draft_fix_from_change",
    "studio.workbench.generate_business_brief",
    "studio.workbench.generate_engineering_contract",
]

ASSISTANT_SCOPES = [
    "studio.assistant.interpret_project_intent",
]

DEFAULT_BRIEFS = [
    {
        "name": "Travel Booking Stress",
        "summary": "Search flights, book travel, block over-budget bookings, and escalate exceptions for approval.",
        "domain": "travel",
        "intent": "We need a travel booking service that searches options, books flights, blocks bookings over budget, refreshes stale quotes, and escalates exceptions for approval.",
    },
    {
        "name": "Deployment Verify Stress",
        "summary": "Run deployments, verify rollout health, and keep follow-up verification explicit.",
        "domain": "devops",
        "intent": "We need a deployment service that starts a rollout, verifies health after deployment, refreshes stale state when clusters drift, and records a clear audit trail.",
    },
    {
        "name": "Order Follow-up Stress",
        "summary": "Place orders, hand off fulfillment, and verify follow-up outcomes across services.",
        "domain": "commerce",
        "intent": "We need an order service that takes the main order action, hands work to fulfillment, verifies the final outcome, and keeps cross-service continuity explicit.",
    },
]


def issue_parent_token(
    client: ANIPClient,
    bootstrap: str,
    capability: str,
    scopes: list[str],
) -> dict:
    return client.request_capability_token(
        principal=AGENT_SUBJECT,
        capability=capability,
        scope=scopes,
        api_key=bootstrap,
        ttl_hours=1,
    )


def issue_root_capability_token(
    client: ANIPClient,
    bootstrap: str,
    capability: str,
    scope: str,
    *,
    budget: dict | None = None,
) -> str:
    response = client.request_capability_token(
        principal=AGENT_SUBJECT,
        capability=capability,
        scope=[scope],
        api_key=bootstrap,
        ttl_hours=1,
        budget=budget,
    )
    return response["token"]


def permission_snapshot(client: ANIPClient, token_jwt: str, capability: str) -> dict:
    permissions = client.check_permissions(token_jwt)
    return {
        "permissions": permissions,
        "entry": ANIPClient.match_permission(permissions, capability),
    }


def resolve_capability_token(
    client: ANIPClient,
    parent_token: dict,
    bootstrap: str,
    capability: str,
    scope: str,
    *,
    report: list[dict],
    budget: dict | None = None,
) -> str:
    parent_state = permission_snapshot(client, parent_token["token"], capability)
    parent_entry = parent_state["entry"]
    decision = {
        "capability": capability,
        "scope": scope,
        "parent": parent_entry,
        "used": None,
        "budget_requested": budget,
    }

    if parent_entry["status"] == "available":
        decision["used"] = "parent"
        report.append(decision)
        return parent_token["token"]

    if parent_entry["status"] == "denied":
        decision["used"] = "root"
        report.append(decision)
        return issue_root_capability_token(
            client,
            bootstrap,
            capability,
            scope,
            budget=budget,
        )

    child = client.request_delegated_capability_token(
        principal=AGENT_SUBJECT,
        parent_token=parent_token["token_id"],
        capability=capability,
        scope=[scope],
        subject=AGENT_SUBJECT,
        auth_bearer=parent_token["token"],
        caller_class="agent",
        ttl_hours=1,
        budget=budget,
    )
    child_state = permission_snapshot(client, child["token"], capability)
    child_entry = child_state["entry"]
    decision["used"] = "delegated"
    decision["child"] = child_entry
    decision["child_token_id"] = child["token_id"]
    report.append(decision)

    if child_entry["status"] != "available":
        raise RuntimeError(
            f"Delegated token for {capability} is still not available: {json.dumps(child_entry, sort_keys=True)}"
        )
    return child["token"]


def invoke(client: ANIPClient, token: str, capability: str, parameters: dict) -> dict:
    response = client.invoke(capability, token, parameters)
    return response["result"] if response.get("success") else response


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--studio-base-url", default="http://127.0.0.1:8100")
    parser.add_argument("--output-dir", default="/tmp/anip-studio-stress")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    assistant_client = ANIPClient(f"{args.studio_base_url.rstrip('/')}/studio-assistant")
    workbench_client = ANIPClient(f"{args.studio_base_url.rstrip('/')}/studio-workbench")

    workbench_parent = issue_parent_token(
        workbench_client,
        WORKBENCH_BOOTSTRAP,
        "create_workspace",
        WORKBENCH_SCOPES,
    )
    assistant_parent = issue_parent_token(
        assistant_client,
        ASSISTANT_BOOTSTRAP,
        "interpret_project_intent",
        ASSISTANT_SCOPES,
    )

    bootstrap_decisions: list[dict] = []
    workspace_token = resolve_capability_token(
        workbench_client,
        workbench_parent,
        WORKBENCH_BOOTSTRAP,
        "create_workspace",
        "studio.workbench.create_workspace",
        report=bootstrap_decisions,
    )
    workspace = invoke(
        workbench_client,
        workspace_token,
        "create_workspace",
        {"name": f"Stress Workspace {uuid4().hex[:8]}", "summary": "ANIP stress-testing workspace"},
    )["workspace"]

    report = {
        "workspace": workspace,
        "assistant_manifest": assistant_client.get_manifest(),
        "workbench_manifest": workbench_client.get_manifest(),
        "bootstrap_permission_decisions": bootstrap_decisions,
        "runs": [],
    }

    for brief in DEFAULT_BRIEFS:
        permission_decisions: list[dict] = []
        create_project_token = resolve_capability_token(
            workbench_client,
            workbench_parent,
            WORKBENCH_BOOTSTRAP,
            "create_project",
            "studio.workbench.create_project",
            report=permission_decisions,
        )
        project = invoke(
            workbench_client,
            create_project_token,
            "create_project",
            {
                "workspace_id": workspace["id"],
                "name": brief["name"],
                "summary": brief["summary"],
                "domain": brief["domain"],
            },
        )["project"]

        interpret_token = resolve_capability_token(
            assistant_client,
            assistant_parent,
            ASSISTANT_BOOTSTRAP,
            "interpret_project_intent",
            "studio.assistant.interpret_project_intent",
            report=permission_decisions,
        )
        interpretation = invoke(
            assistant_client,
            interpret_token,
            "interpret_project_intent",
            {"project_id": project["id"], "intent": brief["intent"]},
        )

        accept_token = resolve_capability_token(
            workbench_client,
            workbench_parent,
            WORKBENCH_BOOTSTRAP,
            "accept_first_design",
            "studio.workbench.accept_first_design",
            report=permission_decisions,
        )
        accepted = invoke(
            workbench_client,
            accept_token,
            "accept_first_design",
            {
                "project_id": project["id"],
                "source_intent": brief["intent"],
                "interpretation": interpretation,
            },
        )

        req_id = accepted["requirements"]["id"]
        shape_id = accepted["shape"]["id"]
        scenario_ids = [item["id"] for item in accepted["scenarios"]]

        eval_token = resolve_capability_token(
            workbench_client,
            workbench_parent,
            WORKBENCH_BOOTSTRAP,
            "evaluate_service_design",
            "studio.workbench.evaluate_service_design",
            report=permission_decisions,
            budget=DOGFOOD_EVAL_BUDGET,
        )
        draft_fix_token = resolve_capability_token(
            workbench_client,
            workbench_parent,
            WORKBENCH_BOOTSTRAP,
            "draft_fix_from_change",
            "studio.workbench.draft_fix_from_change",
            report=permission_decisions,
        )

        scenario_runs = []
        current_req_id = req_id
        current_shape_id = shape_id
        for scenario_id in scenario_ids:
            first_eval = invoke(
                workbench_client,
                eval_token,
                "evaluate_service_design",
                {
                    "project_id": project["id"],
                    "requirements_id": current_req_id,
                    "scenario_id": scenario_id,
                    "shape_id": current_shape_id,
                },
            )
            followup = None
            changes = first_eval["evaluation"].get("what_would_improve") or first_eval["evaluation"].get("glue_you_will_still_write") or []
            if changes:
                fix = invoke(
                    workbench_client,
                    draft_fix_token,
                    "draft_fix_from_change",
                    {
                        "project_id": project["id"],
                        "change": changes[0],
                        "requirements_id": current_req_id,
                        "scenario_id": scenario_id,
                        "shape_id": current_shape_id,
                    },
                )
                selection = fix["selection"]
                current_req_id = selection.get("requirements_id") or current_req_id
                scenario_id = selection.get("scenario_id") or scenario_id
                current_shape_id = selection.get("shape_id") or current_shape_id
                followup = invoke(
                    workbench_client,
                    eval_token,
                    "evaluate_service_design",
                    {
                        "project_id": project["id"],
                        "requirements_id": current_req_id,
                        "scenario_id": scenario_id,
                        "shape_id": current_shape_id,
                    },
                )
            scenario_runs.append({"initial": first_eval, "followup": followup})

        business_token = resolve_capability_token(
            workbench_client,
            workbench_parent,
            WORKBENCH_BOOTSTRAP,
            "generate_business_brief",
            "studio.workbench.generate_business_brief",
            report=permission_decisions,
        )
        engineering_token = resolve_capability_token(
            workbench_client,
            workbench_parent,
            WORKBENCH_BOOTSTRAP,
            "generate_engineering_contract",
            "studio.workbench.generate_engineering_contract",
            report=permission_decisions,
        )
        business_brief = invoke(
            workbench_client,
            business_token,
            "generate_business_brief",
            {
                "project_id": project["id"],
                "source_intent": brief["intent"],
                "requirements_id": current_req_id,
                "scenario_id": scenario_ids[0],
                "shape_id": current_shape_id,
            },
        )["document"]
        engineering_contract = invoke(
            workbench_client,
            engineering_token,
            "generate_engineering_contract",
            {
                "project_id": project["id"],
                "requirements_id": current_req_id,
                "scenario_id": scenario_ids[0],
                "shape_id": current_shape_id,
            },
        )["document"]

        project_dir = output_dir / slug(brief["name"])
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "business-brief.md").write_text(business_brief)
        (project_dir / "engineering-contract.md").write_text(engineering_contract)

        report["runs"].append(
            {
                "brief": brief,
                "project": project,
                "interpretation": interpretation,
                "accepted": accepted,
                "scenario_runs": scenario_runs,
                "permission_decisions": permission_decisions,
                "artifacts_dir": str(project_dir),
            }
        )

    print(json.dumps(report, indent=2))


def slug(value: str) -> str:
    compact = "".join(char.lower() if char.isalnum() else "-" for char in value.strip())
    while "--" in compact:
        compact = compact.replace("--", "-")
    compact = compact.strip("-")
    return compact or uuid4().hex[:8]


if __name__ == "__main__":
    main()
