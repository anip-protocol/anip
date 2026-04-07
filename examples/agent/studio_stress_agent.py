"""ANIP-only Studio stress runner.

Uses the Studio assistant and Studio workbench ANIP services without falling
back to raw Studio REST.
"""

from __future__ import annotations

import argparse
import json
import time
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
    "studio.assistant.start_design_review_session",
    "studio.assistant.stream_design_review",
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


def posture_summary(discovery: dict) -> dict:
    doc = discovery.get("anip_discovery", {})
    posture = doc.get("posture", {})
    audit = posture.get("audit", {})
    failure = posture.get("failure_disclosure", {})
    anchoring = posture.get("anchoring", {})
    return {
        "trust_level": doc.get("trust_level"),
        "audit_queryable": audit.get("queryable", False),
        "audit_retention": audit.get("retention"),
        "audit_retention_enforced": audit.get("retention_enforced", False),
        "failure_disclosure": failure.get("detail_level"),
        "anchoring_enabled": anchoring.get("enabled", False),
        "proofs_available": anchoring.get("proofs_available", False),
    }


def audit_mode(posture: dict) -> str:
    if posture.get("audit_queryable") and posture.get("trust_level") == "anchored":
        return "strict"
    if posture.get("audit_queryable"):
        return "basic"
    return "skip"


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


def invoke(
    client: ANIPClient,
    token: str,
    capability: str,
    parameters: dict,
    *,
    client_reference_id: str,
    task_id: str | None = None,
    parent_invocation_id: str | None = None,
    upstream_service: str | None = None,
) -> dict:
    return client.invoke(
        capability,
        token,
        parameters,
        client_reference_id=client_reference_id,
        task_id=task_id,
        parent_invocation_id=parent_invocation_id,
        upstream_service=upstream_service,
    )


def verify_audit(
    client: ANIPClient,
    token: str,
    capability: str,
    *,
    client_reference_id: str,
    task_id: str | None,
    invocation_id: str,
    mode: str,
) -> dict:
    audit = client.query_audit(
        token,
        capability=capability,
        client_reference_id=client_reference_id,
        task_id=task_id,
        limit=20,
    )
    entries = audit.get("entries", [])
    verification = {
        "mode": mode,
        "count": len(entries),
        "matched_client_reference_id": any(entry.get("client_reference_id") == client_reference_id for entry in entries),
        "matched_invocation_id": any(entry.get("invocation_id") == invocation_id for entry in entries),
        "matched_task_id": task_id is not None and any(entry.get("task_id") == task_id for entry in entries),
        "event_classes": sorted({entry.get("event_class") for entry in entries if entry.get("event_class")}),
    }
    if mode == "skip":
        return {"audit": audit, "verification": verification}
    if not verification["matched_client_reference_id"]:
        raise RuntimeError(f"Audit did not return client_reference_id {client_reference_id} for {capability}")
    if mode == "strict":
        if not verification["matched_invocation_id"]:
            raise RuntimeError(f"Audit did not return invocation_id {invocation_id} for {capability}")
        if task_id is not None and not verification["matched_task_id"]:
            raise RuntimeError(f"Audit did not return task_id {task_id} for {capability}")
    return {"audit": audit, "verification": verification}


def verify_stream_audit(
    client: ANIPClient,
    token: str,
    capability: str,
    *,
    client_reference_id: str,
    invocation_id: str,
    mode: str,
) -> dict:
    audit = client.query_audit(
        token,
        capability=capability,
        client_reference_id=client_reference_id,
        limit=20,
    )
    entries = audit.get("entries", [])
    entry = next((item for item in entries if item.get("invocation_id") == invocation_id), None)
    if entry is None:
        raise RuntimeError(f"Streaming audit did not return invocation_id {invocation_id} for {capability}")
    stream_summary = entry.get("stream_summary")
    if not isinstance(stream_summary, dict):
        raise RuntimeError(f"Streaming audit did not persist stream_summary for {capability}")
    verification = {
        "mode": mode,
        "matched_client_reference_id": entry.get("client_reference_id") == client_reference_id,
        "matched_invocation_id": entry.get("invocation_id") == invocation_id,
        "events_emitted": stream_summary.get("events_emitted"),
        "response_mode": stream_summary.get("response_mode"),
    }
    if not verification["matched_client_reference_id"]:
        raise RuntimeError(f"Streaming audit did not return client_reference_id {client_reference_id} for {capability}")
    if verification["response_mode"] != "streaming":
        raise RuntimeError(f"Streaming audit recorded wrong response mode for {capability}: {verification['response_mode']}")
    if not isinstance(verification["events_emitted"], int) or verification["events_emitted"] < 1:
        raise RuntimeError(f"Streaming audit did not record emitted events for {capability}")
    return {"audit": audit, "verification": verification}


def verify_checkpoints(
    client: ANIPClient,
    posture: dict,
) -> dict:
    """Verify anchored checkpoint/proof surfaces when the service advertises them."""
    if not posture.get("anchoring_enabled"):
        return {"mode": "skip", "reason": "anchoring_disabled"}

    listing = {"checkpoints": []}
    checkpoints: list[dict] = []
    for _ in range(5):
        listing = client.list_checkpoints(limit=10)
        checkpoints = listing.get("checkpoints", [])
        if checkpoints:
            break
        time.sleep(1)
    if not checkpoints:
        raise RuntimeError("Anchored service returned no checkpoints")

    ordered = sorted(
        checkpoints,
        key=lambda item: item.get("range", {}).get("last_sequence", 0),
    )
    latest = ordered[-1]
    latest_detail = client.get_checkpoint(
        latest["checkpoint_id"],
        include_proof=True,
        leaf_index=0,
    )
    checkpoint = latest_detail.get("checkpoint", {})
    inclusion_proof = latest_detail.get("inclusion_proof")
    if not isinstance(inclusion_proof, dict):
        raise RuntimeError(f"Checkpoint {latest['checkpoint_id']} did not return inclusion_proof")

    verification: dict = {
        "mode": "strict" if posture.get("proofs_available") else "basic",
        "checkpoint_count": len(ordered),
        "latest_checkpoint_id": latest["checkpoint_id"],
        "latest_entry_count": checkpoint.get("entry_count"),
        "latest_last_sequence": checkpoint.get("range", {}).get("last_sequence"),
        "inclusion_proof_present": True,
        "inclusion_path_length": len(inclusion_proof.get("path") or []),
        "proof_unavailable": latest_detail.get("proof_unavailable"),
    }

    if len(ordered) >= 2:
        previous = ordered[-2]
        latest_with_consistency = client.get_checkpoint(
            latest["checkpoint_id"],
            consistency_from=previous["checkpoint_id"],
        )
        consistency_proof = latest_with_consistency.get("consistency_proof")
        if not isinstance(consistency_proof, dict):
            raise RuntimeError(
                "Anchored service advertised proofs but did not return consistency_proof "
                f"from {previous['checkpoint_id']} to {latest['checkpoint_id']}"
            )
        verification.update(
            {
                "consistency_proof_present": True,
                "consistency_from": previous["checkpoint_id"],
                "consistency_path_length": len(consistency_proof.get("path") or []),
            }
        )
        return {
            "listing": listing,
            "latest": latest_detail,
            "consistency": latest_with_consistency,
            "verification": verification,
        }

    verification["consistency_proof_present"] = False
    return {
        "listing": listing,
        "latest": latest_detail,
        "consistency": None,
        "verification": verification,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--studio-base-url", default="http://127.0.0.1:8100")
    parser.add_argument("--output-dir", default="/tmp/anip-studio-stress")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    assistant_client = ANIPClient(f"{args.studio_base_url.rstrip('/')}/studio-assistant")
    workbench_client = ANIPClient(f"{args.studio_base_url.rstrip('/')}/studio-workbench")
    assistant_discovery = assistant_client.discover()
    workbench_discovery = workbench_client.discover()
    assistant_posture = posture_summary(assistant_discovery)
    workbench_posture = posture_summary(workbench_discovery)

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
    workspace_ref = f"workspace-{uuid4().hex[:8]}"
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
        client_reference_id=workspace_ref,
    )["result"]["workspace"]

    report = {
        "workspace": workspace,
        "assistant_discovery": assistant_discovery,
        "workbench_discovery": workbench_discovery,
        "assistant_posture": assistant_posture,
        "workbench_posture": workbench_posture,
        "assistant_manifest": assistant_client.get_manifest(),
        "workbench_manifest": workbench_client.get_manifest(),
        "bootstrap_permission_decisions": bootstrap_decisions,
        "checkpoint_checks": None,
        "runs": [],
    }

    for brief in DEFAULT_BRIEFS:
        permission_decisions: list[dict] = []
        audit_checks: list[dict] = []
        run_id = f"run-{slug(brief['name'])}-{uuid4().hex[:8]}"
        create_project_token = resolve_capability_token(
            workbench_client,
            workbench_parent,
            WORKBENCH_BOOTSTRAP,
            "create_project",
            "studio.workbench.create_project",
            report=permission_decisions,
        )
        create_project_ref = f"{slug(brief['name'])}-create-project-{uuid4().hex[:8]}"
        project_resp = invoke(
            workbench_client,
            create_project_token,
            "create_project",
            {
                "workspace_id": workspace["id"],
                "name": brief["name"],
                "summary": brief["summary"],
                "domain": brief["domain"],
            },
            client_reference_id=create_project_ref,
        )
        project = project_resp["result"]["project"]
        audit_checks.append(
            {
                "service": "studio-workbench",
                "capability": "create_project",
                "client_reference_id": create_project_ref,
                **verify_audit(
                    workbench_client,
                    create_project_token,
                    "create_project",
                    client_reference_id=create_project_ref,
                    task_id=None,
                    invocation_id=project_resp["invocation_id"],
                    mode=audit_mode(workbench_posture),
                ),
            }
        )

        interpret_token = resolve_capability_token(
            assistant_client,
            assistant_parent,
            ASSISTANT_BOOTSTRAP,
            "interpret_project_intent",
            "studio.assistant.interpret_project_intent",
            report=permission_decisions,
        )
        interpret_ref = f"{slug(brief['name'])}-interpret-{uuid4().hex[:8]}"
        interpretation_resp = invoke(
            assistant_client,
            interpret_token,
            "interpret_project_intent",
            {"project_id": project["id"], "intent": brief["intent"]},
            client_reference_id=interpret_ref,
        )
        interpretation = interpretation_resp["result"]
        audit_checks.append(
            {
                "service": "studio-assistant",
                "capability": "interpret_project_intent",
                "client_reference_id": interpret_ref,
                **verify_audit(
                    assistant_client,
                    interpret_token,
                    "interpret_project_intent",
                    client_reference_id=interpret_ref,
                    task_id=None,
                    invocation_id=interpretation_resp["invocation_id"],
                    mode=audit_mode(assistant_posture),
                ),
            }
        )

        accept_token = resolve_capability_token(
            workbench_client,
            workbench_parent,
            WORKBENCH_BOOTSTRAP,
            "accept_first_design",
            "studio.workbench.accept_first_design",
            report=permission_decisions,
        )
        accept_ref = f"{slug(brief['name'])}-accept-{uuid4().hex[:8]}"
        accepted_resp = invoke(
            workbench_client,
            accept_token,
            "accept_first_design",
            {
                "project_id": project["id"],
                "source_intent": brief["intent"],
                "interpretation": interpretation,
            },
            client_reference_id=accept_ref,
        )
        accepted = accepted_resp["result"]
        audit_checks.append(
            {
                "service": "studio-workbench",
                "capability": "accept_first_design",
                "client_reference_id": accept_ref,
                **verify_audit(
                    workbench_client,
                    accept_token,
                    "accept_first_design",
                    client_reference_id=accept_ref,
                    task_id=None,
                    invocation_id=accepted_resp["invocation_id"],
                    mode=audit_mode(workbench_posture),
                ),
            }
        )

        req_id = accepted["requirements"]["id"]
        shape_id = accepted["shape"]["id"]
        scenario_ids = [item["id"] for item in accepted["scenarios"]]

        review_session = None
        review_stream = None
        if "start_design_review_session" in report["assistant_manifest"]["capabilities"]:
            review_start_child = assistant_client.request_delegated_capability_token(
                principal=AGENT_SUBJECT,
                parent_token=assistant_parent["token_id"],
                capability="start_design_review_session",
                scope=["studio.assistant.start_design_review_session"],
                subject=AGENT_SUBJECT,
                auth_bearer=assistant_parent["token"],
                caller_class="agent",
                ttl_hours=1,
            )
            review_start_token = review_start_child["token"]
            permission_decisions.append(
                {
                    "capability": "start_design_review_session",
                    "scope": "studio.assistant.start_design_review_session",
                    "parent": permission_snapshot(assistant_client, assistant_parent["token"], "start_design_review_session")["entry"],
                    "used": "delegated",
                    "budget_requested": None,
                    "child": permission_snapshot(assistant_client, review_start_token, "start_design_review_session")["entry"],
                    "child_token_id": review_start_child["token_id"],
                }
            )
            review_start_ref = f"{slug(brief['name'])}-review-start-{uuid4().hex[:8]}"
            review_start_resp = invoke(
                assistant_client,
                review_start_token,
                "start_design_review_session",
                {
                    "project_id": project["id"],
                    "shape_id": shape_id,
                    "scenario_id": scenario_ids[0],
                },
                client_reference_id=review_start_ref,
            )
            review_session = review_start_resp["result"]
            audit_checks.append(
                {
                    "service": "studio-assistant",
                    "capability": "start_design_review_session",
                    "client_reference_id": review_start_ref,
                    **verify_audit(
                        assistant_client,
                        review_start_token,
                        "start_design_review_session",
                        client_reference_id=review_start_ref,
                        task_id=None,
                        invocation_id=review_start_resp["invocation_id"],
                        mode=audit_mode(assistant_posture),
                    ),
                }
            )

            review_stream_child = assistant_client.request_delegated_capability_token(
                principal=AGENT_SUBJECT,
                parent_token=assistant_parent["token_id"],
                capability="stream_design_review",
                scope=["studio.assistant.stream_design_review"],
                subject=AGENT_SUBJECT,
                auth_bearer=assistant_parent["token"],
                caller_class="agent",
                ttl_hours=1,
            )
            review_stream_token = review_stream_child["token"]
            permission_decisions.append(
                {
                    "capability": "stream_design_review",
                    "scope": "studio.assistant.stream_design_review",
                    "parent": permission_snapshot(assistant_client, assistant_parent["token"], "stream_design_review")["entry"],
                    "used": "delegated",
                    "budget_requested": None,
                    "child": permission_snapshot(assistant_client, review_stream_token, "stream_design_review")["entry"],
                    "child_token_id": review_stream_child["token_id"],
                }
            )
            review_stream_ref = f"{slug(brief['name'])}-review-stream-{uuid4().hex[:8]}"
            review_stream_events = assistant_client.invoke_stream(
                "stream_design_review",
                review_stream_token,
                {
                    "project_id": project["id"],
                    "session_id": review_session["session_id"],
                    "question": "What should the PM pressure next?",
                },
                client_reference_id=review_stream_ref,
            )
            completed_event = next((event for event in review_stream_events if event["event"] == "completed"), None)
            if completed_event is None:
                raise RuntimeError("Streaming review did not produce a completed event")
            review_stream = completed_event["data"]
            audit_checks.append(
                {
                    "service": "studio-assistant",
                    "capability": "stream_design_review",
                    "client_reference_id": review_stream_ref,
                    "events": review_stream_events,
                    **verify_stream_audit(
                        assistant_client,
                        review_stream_token,
                        "stream_design_review",
                        client_reference_id=review_stream_ref,
                        invocation_id=review_stream["invocation_id"],
                        mode=audit_mode(assistant_posture),
                    ),
                }
            )

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
            eval_ref = f"{slug(brief['name'])}-eval-{uuid4().hex[:8]}"
            first_eval_resp = invoke(
                workbench_client,
                eval_token,
                "evaluate_service_design",
                {
                    "project_id": project["id"],
                    "requirements_id": current_req_id,
                    "scenario_id": scenario_id,
                    "shape_id": current_shape_id,
                },
                client_reference_id=eval_ref,
            )
            first_eval = first_eval_resp["result"]
            audit_checks.append(
                {
                    "service": "studio-workbench",
                    "capability": "evaluate_service_design",
                    "client_reference_id": eval_ref,
                    **verify_audit(
                        workbench_client,
                        eval_token,
                        "evaluate_service_design",
                        client_reference_id=eval_ref,
                        task_id=None,
                        invocation_id=first_eval_resp["invocation_id"],
                        mode=audit_mode(workbench_posture),
                    ),
                }
            )
            followup = None
            changes = first_eval["evaluation"].get("what_would_improve") or first_eval["evaluation"].get("glue_you_will_still_write") or []
            if changes:
                fix_ref = f"{slug(brief['name'])}-fix-{uuid4().hex[:8]}"
                fix_resp = invoke(
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
                    client_reference_id=fix_ref,
                )
                fix = fix_resp["result"]
                audit_checks.append(
                    {
                        "service": "studio-workbench",
                        "capability": "draft_fix_from_change",
                        "client_reference_id": fix_ref,
                        **verify_audit(
                            workbench_client,
                            draft_fix_token,
                            "draft_fix_from_change",
                            client_reference_id=fix_ref,
                            task_id=None,
                            invocation_id=fix_resp["invocation_id"],
                            mode=audit_mode(workbench_posture),
                        ),
                    }
                )
                selection = fix["selection"]
                current_req_id = selection.get("requirements_id") or current_req_id
                scenario_id = selection.get("scenario_id") or scenario_id
                current_shape_id = selection.get("shape_id") or current_shape_id
                follow_ref = f"{slug(brief['name'])}-follow-{uuid4().hex[:8]}"
                followup_resp = invoke(
                    workbench_client,
                    eval_token,
                    "evaluate_service_design",
                    {
                        "project_id": project["id"],
                        "requirements_id": current_req_id,
                        "scenario_id": scenario_id,
                        "shape_id": current_shape_id,
                    },
                    client_reference_id=follow_ref,
                )
                followup = followup_resp["result"]
                audit_checks.append(
                    {
                        "service": "studio-workbench",
                        "capability": "evaluate_service_design",
                        "client_reference_id": follow_ref,
                        **verify_audit(
                            workbench_client,
                            eval_token,
                            "evaluate_service_design",
                            client_reference_id=follow_ref,
                            task_id=None,
                            invocation_id=followup_resp["invocation_id"],
                            mode=audit_mode(workbench_posture),
                        ),
                    }
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
        business_ref = f"{slug(brief['name'])}-business-{uuid4().hex[:8]}"
        business_resp = invoke(
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
            client_reference_id=business_ref,
        )
        business_brief = business_resp["result"]["document"]
        audit_checks.append(
            {
                "service": "studio-workbench",
                "capability": "generate_business_brief",
                "client_reference_id": business_ref,
                **verify_audit(
                    workbench_client,
                    business_token,
                    "generate_business_brief",
                    client_reference_id=business_ref,
                    task_id=None,
                    invocation_id=business_resp["invocation_id"],
                    mode=audit_mode(workbench_posture),
                ),
            }
        )
        engineering_ref = f"{slug(brief['name'])}-engineering-{uuid4().hex[:8]}"
        engineering_resp = invoke(
            workbench_client,
            engineering_token,
            "generate_engineering_contract",
            {
                "project_id": project["id"],
                "requirements_id": current_req_id,
                "scenario_id": scenario_ids[0],
                "shape_id": current_shape_id,
            },
            client_reference_id=engineering_ref,
        )
        engineering_contract = engineering_resp["result"]["document"]
        audit_checks.append(
            {
                "service": "studio-workbench",
                "capability": "generate_engineering_contract",
                "client_reference_id": engineering_ref,
                **verify_audit(
                    workbench_client,
                    engineering_token,
                    "generate_engineering_contract",
                    client_reference_id=engineering_ref,
                    task_id=None,
                    invocation_id=engineering_resp["invocation_id"],
                    mode=audit_mode(workbench_posture),
                ),
            }
        )

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
                "review_session": review_session,
                "review_stream": review_stream,
                "scenario_runs": scenario_runs,
                "permission_decisions": permission_decisions,
                "audit_checks": audit_checks,
                "run_id": run_id,
                "artifacts_dir": str(project_dir),
            }
        )

    report["checkpoint_checks"] = verify_checkpoints(
        workbench_client,
        workbench_posture,
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
