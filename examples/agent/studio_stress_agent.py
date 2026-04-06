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


def issue_token(client: ANIPClient, bootstrap: str, capability: str, scope: str) -> str:
    response = client.request_capability_token(
        principal="agent:studio-stress",
        capability=capability,
        scope=[scope],
        api_key=bootstrap,
        ttl_hours=1,
    )
    return response["token"]


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

    workspace_token = issue_token(
        workbench_client,
        WORKBENCH_BOOTSTRAP,
        "create_workspace",
        "studio.workbench.create_workspace",
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
        "runs": [],
    }

    for brief in DEFAULT_BRIEFS:
        create_project_token = issue_token(
            workbench_client,
            WORKBENCH_BOOTSTRAP,
            "create_project",
            "studio.workbench.create_project",
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

        interpret_token = issue_token(
            assistant_client,
            ASSISTANT_BOOTSTRAP,
            "interpret_project_intent",
            "studio.assistant.interpret_project_intent",
        )
        interpretation = invoke(
            assistant_client,
            interpret_token,
            "interpret_project_intent",
            {"project_id": project["id"], "intent": brief["intent"]},
        )

        accept_token = issue_token(
            workbench_client,
            WORKBENCH_BOOTSTRAP,
            "accept_first_design",
            "studio.workbench.accept_first_design",
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

        eval_token = issue_token(
            workbench_client,
            WORKBENCH_BOOTSTRAP,
            "evaluate_service_design",
            "studio.workbench.evaluate_service_design",
        )
        draft_fix_token = issue_token(
            workbench_client,
            WORKBENCH_BOOTSTRAP,
            "draft_fix_from_change",
            "studio.workbench.draft_fix_from_change",
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

        business_token = issue_token(
            workbench_client,
            WORKBENCH_BOOTSTRAP,
            "generate_business_brief",
            "studio.workbench.generate_business_brief",
        )
        engineering_token = issue_token(
            workbench_client,
            WORKBENCH_BOOTSTRAP,
            "generate_engineering_contract",
            "studio.workbench.generate_engineering_contract",
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
