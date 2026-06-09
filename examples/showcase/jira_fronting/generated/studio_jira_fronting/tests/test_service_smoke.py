import importlib

import pytest
from fastapi.testclient import TestClient

from jira_governed_fronting_showcase.runtime_target import GENERATED_CAPABILITY_METADATA

SERVICE_MODULES = [
    {"service_id": "jira-governance-service", "module": "jira_governed_fronting_showcase.app", "capabilities": ["jira.backlog.search", "jira.bug.prepare", "jira.story.prepare", "jira.transition.request", "jira.comment.prepare"]},
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
        headers={"Authorization": "Bearer dev-admin-key"},
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
def test_generated_service_discovery_and_invoke(service: dict[str, object]) -> None:
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
    assert invoke.status_code == 200
    payload = invoke.json()
    assert payload["success"] is True
    assert payload["result"]["execution_status"]
