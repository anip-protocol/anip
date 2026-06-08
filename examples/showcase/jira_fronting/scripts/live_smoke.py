"""Read-only live smoke for the Jira fronting showcase.

Expected environment:
- JIRA_BASE_URL
- JIRA_EMAIL
- JIRA_API_TOKEN

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

from fastapi.testclient import TestClient


def jira_get(path: str, query: dict[str, str] | None = None) -> dict:
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


def create_generated_app():
    app_module = os.getenv("ANIP_JIRA_GENERATED_APP_MODULE", "jira_governed_fronting_gate_clean.app")
    module = importlib.import_module(app_module)
    return module.create_app()


def create_generated_clients() -> dict[str, TestClient]:
    app_module = os.getenv("ANIP_JIRA_GENERATED_APP_MODULE", "jira_governed_fronting_gate_clean.app")
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
        service_clients["default"] = TestClient(create_generated_app())
    capability_clients: dict[str, TestClient] = {}
    for capability in capability_metadata:
        capability_id = str(capability.get("capability_id", "")).strip()
        service_id = str(capability.get("service_id", "")).strip()
        if capability_id:
            capability_clients[capability_id] = service_clients.get(service_id) or next(iter(service_clients.values()))
    return capability_clients


def issue_token(client: TestClient, capability_id: str) -> str:
    response = client.post(
        "/anip/tokens",
        headers={"Authorization": "Bearer dev-admin-key"},
        json={
            "capability": capability_id,
            "scope": [capability_id],
            "subject": "agent:live-jira-smoke",
            "purpose_parameters": {"actor_id": "jira_fronting_consumer", "source": "live-smoke"},
        },
    )
    response.raise_for_status()
    return response.json()["token"]


def invoke(client: TestClient, capability_id: str, parameters: dict) -> dict:
    token = issue_token(client, capability_id)
    response = client.post(
        f"/anip/invoke/{capability_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"parameters": parameters},
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("success"):
        raise RuntimeError(payload)
    return payload["result"]


def main() -> None:
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
    clients = create_generated_clients()

    cases = {
        "jira.backlog.search_context": {
            "parameters": {"project_key": project_key, "query": "test", "limit": 5},
            "expected_status": "completed",
            "expect_mutation": None,
        },
        "jira.issue.get_context": {
            "parameters": {"issue_key": issue_key, "include_comments": True},
            "expected_status": "completed",
            "expect_mutation": None,
        },
        "jira.incident_bug.prepare": {
            "parameters": {
                "project_key": project_key,
                "summary": "ANIP Jira fronting smoke preview",
                "description": "Generated by the live read/write-adjacent smoke. This must not create a Jira issue.",
                "severity": "sev3",
                "labels": ["anip-smoke"],
            },
            "expected_status": "prepared",
            "expect_mutation": False,
        },
        "jira.story.prepare": {
            "parameters": {
                "project_key": project_key,
                "summary": "ANIP Jira fronting story preview",
                "acceptance_criteria": ["Given a governed Jira request", "When ANIP prepares a story", "Then Jira is not mutated"],
                "priority": "medium",
                "labels": ["anip-smoke"],
            },
            "expected_status": "prepared",
            "expect_mutation": False,
        },
        "jira.subtask.prepare": {
            "parameters": {
                "parent_issue_key": issue_key,
                "summary": "ANIP Jira fronting subtask preview",
                "description": "Preview a subtask under a real parent issue without creating it.",
            },
            "expected_status": "prepared",
            "expect_mutation": False,
        },
        "jira.customer_escalation.comment.prepare": {
            "parameters": {
                "issue_key": issue_key,
                "comment_purpose": "triage_update",
                "context": "Prepare a customer-safe triage update preview. Do not post it.",
                "visibility": "internal",
            },
            "expected_status": "prepared",
            "expect_mutation": False,
        },
        "jira.workflow_transition.request": {
            "parameters": {
                "issue_key": issue_key,
                "target_status": target_status,
                "reason": "Validate governed transition preview without mutating Jira.",
                "comment": "ANIP smoke transition preview only.",
            },
            "expected_status": "prepared",
            "expect_mutation": False,
        },
        "jira.sprint_move.request": {
            "parameters": {
                "issue_keys": [issue_key],
                "target_sprint": "preview-sprint",
                "reason": "Validate sprint move preview without mutating Jira.",
            },
            "expected_status": "prepared",
            "expect_mutation": False,
        },
        "jira.assignee_change.request": {
            "parameters": {
                "issue_key": issue_key,
                "assignee_ref": "preview-account-id",
                "reason": "Validate assignee change preview without mutating Jira.",
            },
            "expected_status": "prepared",
            "expect_mutation": False,
        },
        "jira.issue_link.request": {
            "parameters": {
                "source_issue_key": issue_key,
                "target_issue_key": second_issue_key,
                "link_type": "Relates",
                "reason": "Validate issue link preview without mutating Jira.",
            },
            "expected_status": "prepared",
            "expect_mutation": False,
        },
        "jira.release_notes.prepare": {
            "parameters": {
                "project_key": project_key,
                "release_ref": release_ref,
                "issue_query": "test",
                "audience": "internal",
                "limit": 5,
            },
            "expected_status": "prepared",
            "expect_mutation": None,
        },
    }

    summary: dict[str, dict] = {}
    for capability_id, case in cases.items():
        client = clients.get(capability_id)
        if client is None:
            raise AssertionError(f"{capability_id}: generated service client not found")
        result = invoke(client, capability_id, case["parameters"])
        execution_status = result.get("execution_status")
        expected_status = case["expected_status"]
        if execution_status != expected_status:
            raise AssertionError(f"{capability_id}: expected {expected_status}, got {execution_status}: {result}")
        expected_mutation = case["expect_mutation"]
        if expected_mutation is not None and result.get("mutation_performed") is not expected_mutation:
            raise AssertionError(f"{capability_id}: unexpected mutation posture: {result}")
        summary[capability_id] = {
            "execution_status": execution_status,
            "mutation_performed": result.get("mutation_performed"),
            "approval_required": result.get("approval_required"),
            "jira_action": result.get("jira_action"),
        }
        if capability_id == "jira.backlog.search_context":
            summary[capability_id]["issue_count"] = (result.get("result") or {}).get("count")
            summary[capability_id]["jql"] = result.get("jql")
        if capability_id == "jira.release_notes.prepare":
            summary[capability_id]["issue_count"] = (result.get("result") or {}).get("issue_count")
            summary[capability_id]["release_ref"] = release_ref

    print(json.dumps({
        "project_key": project_key,
        "issue_key": issue_key,
        "capabilities_tested": len(summary),
        "results": summary,
    }, indent=2))


if __name__ == "__main__":
    main()
