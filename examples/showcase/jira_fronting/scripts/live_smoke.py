"""Read-only live smoke for the Jira fronting showcase.

The Python bundle never mutates Jira: write-adjacent capabilities return governed
previews, including after an approval grant.

Expected environment:
- JIRA_BASE_URL
- JIRA_EMAIL
- JIRA_API_TOKEN

Optional:
- ANIP_JIRA_GENERATED_APP_MODULE (default jira_governed_fronting_showcase.app)

The smoke authenticates through the generated service's ANIP_API_KEYS_JSON, which
it sets itself: one API key per actor that the 0.2.3 policy bindings select, an
approver, and principals no binding selects. It checks that:

- each capability succeeds for an actor whose binding allows it;
- approval-gated capabilities return approval_required, and complete after an
  approver issues a grant through POST /anip/approval_grants;
- a principal without an actor claim, an actor no binding names, a deny
  binding and a clarify binding are refused.

Run after generating the Python service with the Jira custom bundle:

PYTHONPATH="<repo python packages>:<generated src>" python examples/showcase/jira_fronting/scripts/live_smoke.py
"""
from __future__ import annotations

import base64
import importlib
import json
import os
import urllib.parse
import urllib.request
from typing import Any

from fastapi.testclient import TestClient

DEFAULT_APP_MODULE = "jira_governed_fronting_showcase.app"

# API key -> ANIP principal. The actor_id claims are the actors the 0.2.3
# runtime policy bindings select.
SMOKE_KEYS = {
    "smoke-release-preparer": "human:live-jira-smoke|actor_id=jira_release_preparer",
    "smoke-triage-operator": "human:live-jira-smoke|actor_id=jira_triage_operator",
    "smoke-delivery-coordinator": "human:live-jira-smoke|actor_id=jira_delivery_coordinator",
    "smoke-audit-reviewer": "human:live-jira-smoke|actor_id=jira_audit_reviewer",
    "smoke-change-approver": "human:live-jira-approver|actor_id=jira_change_approver",
    "smoke-no-actor": "human:live-jira-smoke",
    "smoke-unknown-actor": "human:live-jira-smoke|actor_id=jira_unknown_actor",
}
APPROVER_KEY = "smoke-change-approver"
NO_BINDING_DETAIL = "No runtime policy binding matches the current actor for this capability."


def jira_get(path: str, query: dict[str, str] | None = None) -> Any:
    base_url = os.environ["JIRA_BASE_URL"].rstrip("/")
    email = os.environ["JIRA_EMAIL"]
    token = os.environ["JIRA_API_TOKEN"]
    credentials = base64.b64encode(f"{email}:{token}".encode()).decode()
    url = f"{base_url}{path}"
    if query:
        url += f"?{urllib.parse.urlencode(query)}"
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "Authorization": f"Basic {credentials}"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode())


def generated_app_module() -> str:
    return os.getenv("ANIP_JIRA_GENERATED_APP_MODULE", "").strip() or DEFAULT_APP_MODULE


def create_generated_clients() -> tuple[dict[str, TestClient], dict[str, list[str]]]:
    """Return a client and the minimum scope for every generated capability."""
    app_module = generated_app_module()
    package_name = app_module.rsplit(".", 1)[0]
    runtime_target_module = importlib.import_module(f"{package_name}.runtime_target")
    capability_metadata = getattr(runtime_target_module, "GENERATED_CAPABILITY_METADATA", [])
    services = getattr(runtime_target_module, "RUNTIME_TARGET", {}).get("services", [])
    service_ids = [str(service.get("service_id", "")).strip() for service in services if service.get("service_id")]
    service_clients: dict[str, TestClient] = {}
    for index, service_id in enumerate(service_ids):
        if index == 0:
            service_module_name = app_module
        else:
            service_module_name = f"{package_name}.services.{service_id.replace('-', '_')}.app"
        service_module = importlib.import_module(service_module_name)
        service_clients[service_id] = TestClient(service_module.create_app())
    if not service_clients:
        service_clients["default"] = TestClient(importlib.import_module(app_module).create_app())
    clients: dict[str, TestClient] = {}
    scopes: dict[str, list[str]] = {}
    for capability in capability_metadata:
        capability_id = str(capability.get("capability_id", "")).strip()
        if not capability_id:
            continue
        service_id = str(capability.get("service_id", "")).strip()
        clients[capability_id] = service_clients.get(service_id) or next(iter(service_clients.values()))
        scopes[capability_id] = list(capability.get("minimum_scope") or [capability_id])
    return clients, scopes


class Smoke:
    def __init__(self, clients: dict[str, TestClient], scopes: dict[str, list[str]]) -> None:
        self.clients = clients
        self.scopes = scopes

    def client(self, capability_id: str) -> TestClient:
        client = self.clients.get(capability_id)
        if client is None:
            raise AssertionError(f"{capability_id}: generated service client not found")
        return client

    def token(self, key: str, capability_id: str, scope: list[str] | None = None) -> str:
        response = self.client(capability_id).post(
            "/anip/tokens",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "capability": capability_id,
                "scope": scope or self.scopes.get(capability_id, [capability_id]),
                "subject": "agent:live-jira-smoke",
                "purpose_parameters": {"source": "live-smoke"},
            },
        )
        response.raise_for_status()
        return response.json()["token"]

    def invoke(self, key: str, capability_id: str, parameters: dict, approval_grant: str | None = None) -> dict:
        body: dict[str, Any] = {"parameters": parameters}
        if approval_grant:
            body["approval_grant"] = approval_grant
        response = self.client(capability_id).post(
            f"/anip/invoke/{capability_id}",
            headers={"Authorization": f"Bearer {self.token(key, capability_id)}"},
            json=body,
        )
        return response.json()

    def grant(self, key: str, capability_id: str, approval_request_id: str) -> dict:
        approver_token = self.token(key, capability_id, scope=[f"approver:{capability_id}"])
        response = self.client(capability_id).post(
            "/anip/approval_grants",
            headers={"Authorization": f"Bearer {approver_token}"},
            json={"approval_request_id": approval_request_id, "grant_type": "one_time"},
        )
        return response.json()


def expect_result(capability_id: str, payload: dict, status: str, mutation: bool | None) -> dict:
    if not payload.get("success"):
        raise AssertionError(f"{capability_id}: expected {status}, got failure: {payload}")
    result = payload["result"]
    if result.get("execution_status") != status:
        raise AssertionError(f"{capability_id}: expected {status}, got {result.get('execution_status')}: {result}")
    if mutation is not None and result.get("mutation_performed") is not mutation:
        raise AssertionError(f"{capability_id}: unexpected mutation posture: {result}")
    return result


def expect_failure(capability_id: str, payload: dict, failure_type: str, detail: str | None = None) -> dict:
    failure = payload.get("failure") or {}
    if payload.get("success") is not False or failure.get("type") != failure_type:
        raise AssertionError(f"{capability_id}: expected failure {failure_type}, got {payload}")
    if detail is not None and failure.get("detail") != detail:
        raise AssertionError(f"{capability_id}: expected detail {detail!r}, got {failure.get('detail')!r}")
    return failure


def run_with_approval(smoke: Smoke, key: str, capability_id: str, parameters: dict, check_approver_scope: bool) -> tuple[dict, dict]:
    failure = expect_failure(capability_id, smoke.invoke(key, capability_id, parameters), "approval_required")
    approval_request_id = (failure.get("approval_required") or {}).get("approval_request_id")
    if not approval_request_id:
        raise AssertionError(f"{capability_id}: approval_required carried no approval_request_id: {failure}")
    if check_approver_scope:
        # A token without approver:<capability> scope cannot issue the grant.
        requester_token = smoke.token(key, capability_id)
        refused = smoke.client(capability_id).post(
            "/anip/approval_grants",
            headers={"Authorization": f"Bearer {requester_token}"},
            json={"approval_request_id": approval_request_id, "grant_type": "one_time"},
        ).json()
        expect_failure(capability_id, refused, "approver_not_authorized")
    grant = smoke.grant(APPROVER_KEY, capability_id, approval_request_id)
    grant_id = grant.get("grant_id")
    if not grant_id:
        raise AssertionError(f"{capability_id}: approval grant was not issued: {grant}")
    result = expect_result(capability_id, smoke.invoke(key, capability_id, parameters, approval_grant=grant_id), "prepared", False)
    return result, {"approval_request_id": approval_request_id, "grant_id": grant_id}


def main() -> None:
    os.environ["ANIP_API_KEYS_JSON"] = json.dumps(SMOKE_KEYS)
    projects = jira_get("/rest/api/3/project/search", {"maxResults": "1"}).get("values", [])
    if not projects:
        raise SystemExit("No Jira projects available for live smoke")
    project_key = projects[0]["key"]
    issues = jira_get(
        "/rest/api/3/search/jql",
        {
            "jql": f"project = {project_key} ORDER BY updated DESC",
            "maxResults": "2",
            "fields": "summary,status,issuetype,project",
        },
    ).get("issues", [])
    if not issues:
        raise SystemExit(f"No Jira issues available in project {project_key} for live smoke")
    issue_key = issues[0]["key"]
    second_issue_key = issues[1]["key"] if len(issues) > 1 else issue_key
    transitions = jira_get(f"/rest/api/3/issue/{issue_key}/transitions").get("transitions", [])
    target_status = (transitions[0] or {}).get("name") if transitions else "To Do"
    versions = jira_get(f"/rest/api/3/project/{project_key}/versions")
    release_ref = versions[0]["name"] if versions else "unversioned"
    smoke = Smoke(*create_generated_clients())

    # (capability, API key, parameters, expected execution_status, expected mutation_performed)
    allowed: list[tuple[str, str, dict[str, Any], str, bool | None]] = [
        ("jira.backlog.search_context", "smoke-release-preparer",
         {"project_key": project_key, "query": "test", "limit": 5}, "completed", None),
        ("jira.issue.get_context", "smoke-release-preparer",
         {"issue_key": issue_key, "include_comments": True}, "completed", None),
        ("jira.incident_bug.prepare", "smoke-release-preparer", {
            "project_key": project_key,
            "summary": "ANIP Jira fronting smoke preview",
            "description": "Generated by the live read/write-adjacent smoke. This must not create a Jira issue.",
            "severity": "sev3",
            "labels": ["anip-smoke"],
        }, "prepared", False),
        ("jira.story.prepare", "smoke-release-preparer", {
            "project_key": project_key,
            "summary": "ANIP Jira fronting story preview",
            "acceptance_criteria": ["Given a governed Jira request", "When ANIP prepares a story", "Then Jira is not mutated"],
            "priority": "medium",
            "labels": ["anip-smoke"],
        }, "prepared", False),
        ("jira.subtask.prepare", "smoke-release-preparer", {
            "parent_issue_key": issue_key,
            "summary": "ANIP Jira fronting subtask preview",
            "description": "Preview a subtask under a real parent issue without creating it.",
        }, "prepared", False),
        ("jira.customer_escalation.comment.prepare", "smoke-release-preparer", {
            "issue_key": issue_key,
            "comment_purpose": "triage_update",
            "context": "Prepare a customer-safe triage update preview. Do not post it.",
            "visibility": "internal",
        }, "prepared", False),
        ("jira.release_notes.prepare", "smoke-triage-operator", {
            "project_key": project_key,
            "release_ref": release_ref,
            "issue_query": "test",
            "audience": "internal",
            "limit": 5,
        }, "prepared", None),
    ]
    # Approval-gated capabilities: (capability, requester API key, parameters).
    gated: list[tuple[str, str, dict[str, Any]]] = [
        ("jira.workflow_transition.request", "smoke-delivery-coordinator", {
            "issue_key": issue_key,
            "target_status": target_status,
            "reason": "Validate governed transition preview without mutating Jira.",
            "comment": "ANIP smoke transition preview only.",
        }),
        ("jira.sprint_move.request", "smoke-audit-reviewer", {
            "issue_keys": [issue_key],
            "target_sprint": "preview-sprint",
            "reason": "Validate sprint move preview without mutating Jira.",
        }),
        ("jira.assignee_change.request", "smoke-audit-reviewer", {
            "issue_key": issue_key,
            "assignee_ref": "preview-account-id",
            "reason": "Validate assignee change preview without mutating Jira.",
        }),
        ("jira.issue_link.request", "smoke-audit-reviewer", {
            "source_issue_key": issue_key,
            "target_issue_key": second_issue_key,
            "link_type": "Relates",
            "reason": "Validate issue link preview without mutating Jira.",
        }),
    ]
    backlog = {"project_key": project_key, "query": "test", "limit": 5}
    assignee = gated[2][2]
    # (label, capability, API key, parameters, expected failure type, expected detail)
    refused: list[tuple[str, str, str, dict[str, Any], str, str | None]] = [
        ("principal without an actor claim", "jira.backlog.search_context", "smoke-no-actor", backlog, "denied", NO_BINDING_DETAIL),
        ("actor no binding names", "jira.backlog.search_context", "smoke-unknown-actor", backlog, "denied", NO_BINDING_DETAIL),
        ("deny binding", "jira.assignee_change.request", "smoke-triage-operator", assignee, "denied", None),
        ("deny binding", "jira.release_notes.prepare", "smoke-release-preparer", allowed[6][2], "denied", None),
        ("clarify binding", "jira.issue.get_context", "smoke-triage-operator", allowed[1][2], "clarification_required", None),
    ]

    summary: dict[str, dict] = {}
    for capability_id, key, parameters, status, mutation in allowed:
        result = expect_result(capability_id, smoke.invoke(key, capability_id, parameters), status, mutation)
        summary[capability_id] = {
            "actor": SMOKE_KEYS[key],
            "execution_status": result.get("execution_status"),
            "mutation_performed": result.get("mutation_performed"),
            "jira_action": result.get("jira_action"),
        }
        if capability_id == "jira.backlog.search_context":
            summary[capability_id]["issue_count"] = (result.get("result") or {}).get("count")
            summary[capability_id]["jql"] = result.get("jql")
        if capability_id == "jira.release_notes.prepare":
            summary[capability_id]["issue_count"] = (result.get("result") or {}).get("issue_count")
            summary[capability_id]["release_ref"] = release_ref
    for index, (capability_id, key, parameters) in enumerate(gated):
        result, approval = run_with_approval(smoke, key, capability_id, parameters, check_approver_scope=index == 0)
        summary[capability_id] = {
            "actor": SMOKE_KEYS[key],
            "first_attempt": "approval_required",
            **approval,
            "execution_status": result.get("execution_status"),
            "mutation_performed": result.get("mutation_performed"),
            "jira_action": result.get("jira_action"),
        }
    refusals = []
    for label, capability_id, key, parameters, failure_type, detail in refused:
        expect_failure(capability_id, smoke.invoke(key, capability_id, parameters), failure_type, detail)
        refusals.append({"check": label, "capability_id": capability_id, "actor": SMOKE_KEYS[key], "failure": failure_type})

    print(json.dumps({
        "project_key": project_key,
        "issue_key": issue_key,
        "capabilities_tested": len(summary),
        "results": summary,
        "refusals": refusals,
    }, indent=2))


if __name__ == "__main__":
    main()
