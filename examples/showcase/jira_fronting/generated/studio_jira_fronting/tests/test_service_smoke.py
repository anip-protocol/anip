import importlib
import json

import pytest
from fastapi.testclient import TestClient

from jira_governed_fronting_showcase.runtime_target import GENERATED_CAPABILITY_METADATA

SERVICE_MODULES = [
    {"service_id": "jira-fronting", "module": "jira_governed_fronting_showcase.app", "capabilities": ["jira.backlog.search_context", "jira.issue.get_context", "jira.incident_bug.prepare", "jira.story.prepare", "jira.subtask.prepare", "jira.customer_escalation.comment.prepare", "jira.release_notes.prepare"], "principal": "human:smoke-test|actor_id=jira_triage_operator", "expect": "success"},
    {"service_id": "jira-governance", "module": "jira_governed_fronting_showcase.services.jira_governance.app", "capabilities": ["jira.workflow_transition.request", "jira.sprint_move.request", "jira.assignee_change.request", "jira.issue_link.request"], "principal": "human:smoke-test|actor_id=jira_audit_reviewer", "expect": "approval_required"},
]

def _capability_map(payload: dict) -> dict:
    capabilities = payload.get('capabilities')
    if capabilities is None and isinstance(payload.get('anip_discovery'), dict):
        capabilities = payload['anip_discovery'].get('capabilities', {})
    if isinstance(capabilities, list):
        return {item.get('name'): item for item in capabilities if isinstance(item, dict) and item.get('name')}
    if isinstance(capabilities, dict):
        return capabilities
    return {}

def _issue_token(client: TestClient, capability_id: str, scope: list[str]) -> str:
    response = client.post(
        "/anip/tokens",
        headers={"Authorization": "Bearer smoke-test-key"},
        json={
            "capability": capability_id,
            "scope": scope,
            "subject": "agent:test",
            "purpose_parameters": {"actor_id": "test", "source": "pytest"},
        },
    )
    assert response.status_code == 200
    return response.json()["token"]

def _minimum_scope(client: TestClient, capability_id: str, fallback: list[str]) -> list[str]:
    manifest = client.get('/anip/manifest')
    assert manifest.status_code == 200
    capabilities = _capability_map(manifest.json())
    capability = capabilities.get(capability_id, {})
    return capability.get('minimum_scope') or fallback

@pytest.mark.parametrize('service', SERVICE_MODULES)
def test_generated_service_discovery_and_invoke(service: dict[str, object], monkeypatch: pytest.MonkeyPatch) -> None:
    # Invoke as the principal the generated policy lets reach the backend, if any;
    # the generator recorded the outcome its policy gives that principal.
    monkeypatch.setenv('ANIP_API_KEYS_JSON', json.dumps({'smoke-test-key': service['principal']}))
    module = importlib.import_module(str(service['module']))
    client = TestClient(module.create_app())
    discovery = client.get('/.well-known/anip')
    assert discovery.status_code == 200
    discovery_names = set(_capability_map(discovery.json()).keys())
    assert discovery_names == set(service['capabilities'])

    capability = next(item for item in GENERATED_CAPABILITY_METADATA if item['capability_id'] == service['capabilities'][0])
    token = _issue_token(client, capability['capability_id'], _minimum_scope(client, capability['capability_id'], capability['minimum_scope']))
    invoke = client.post(
        f"/anip/invoke/{capability['capability_id']}",
        headers={"Authorization": f"Bearer {token}"},
        json={"parameters": capability["sample_parameters"]},
    )
    payload = invoke.json()
    if service['expect'] == 'success':
        assert invoke.status_code == 200
        assert payload["success"] is True
        assert payload["result"]["execution_status"]
    else:
        assert payload["success"] is False
        assert payload["failure"]["type"] == service['expect']
