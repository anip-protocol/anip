"""Conformance tests for ANIP cross-service continuity (v0.18).

Spec references: v0.18 additions for upstream_service propagation.

upstream_service is an optional string field that callers MAY include in
an invoke request to identify the service that initiated this call as part
of a cross-service workflow. Services MUST echo it in the response and
record it in the audit log. Services MUST NOT reject requests because the
parent_invocation_id was issued by a foreign service.
"""
import re
import time
import uuid

from conftest import issue_token


class TestUpstreamServiceEcho:
    def test_upstream_service_echoed(self, client, bootstrap_bearer, read_capability, all_scopes, sample_inputs):
        """Invoking with upstream_service echoes it back in the response."""
        cap_name, _ = read_capability
        token = issue_token(client, all_scopes, cap_name, bootstrap_bearer)
        params = sample_inputs.get(cap_name, {})

        resp = client.post(
            f"/anip/invoke/{cap_name}",
            headers={"Authorization": f"Bearer {token}"},
            json={"parameters": params, "upstream_service": "test-upstream"},
        )
        assert resp.status_code == 200, f"Invoke failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert data.get("success") is True, f"Invoke not successful: {data}"
        assert data.get("upstream_service") == "test-upstream", (
            f"Expected upstream_service 'test-upstream' echoed in response, "
            f"got '{data.get('upstream_service')}'"
        )

    def test_upstream_service_optional(self, client, bootstrap_bearer, read_capability, all_scopes, sample_inputs):
        """Invoking without upstream_service succeeds — the field is optional."""
        cap_name, _ = read_capability
        token = issue_token(client, all_scopes, cap_name, bootstrap_bearer)
        params = sample_inputs.get(cap_name, {})

        resp = client.post(
            f"/anip/invoke/{cap_name}",
            headers={"Authorization": f"Bearer {token}"},
            json={"parameters": params},
        )
        assert resp.status_code == 200, f"Invoke failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert data.get("success") is True, f"Invoke not successful: {data}"


class TestUpstreamServiceAudit:
    def test_upstream_service_in_audit(self, client, bootstrap_bearer, read_capability, all_scopes, sample_inputs):
        """upstream_service provided on invoke is recorded in the audit log entry."""
        cap_name, _ = read_capability
        token = issue_token(client, all_scopes, cap_name, bootstrap_bearer)
        params = sample_inputs.get(cap_name, {})
        upstream = f"upstream-{uuid.uuid4().hex[:8]}"

        invoke_resp = client.post(
            f"/anip/invoke/{cap_name}",
            headers={"Authorization": f"Bearer {token}"},
            json={"parameters": params, "upstream_service": upstream},
        )
        assert invoke_resp.status_code == 200, f"Invoke failed: {invoke_resp.status_code} {invoke_resp.text}"
        invocation_id = invoke_resp.json()["invocation_id"]

        time.sleep(1)

        audit_resp = client.post(
            "/anip/audit",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert audit_resp.status_code == 200
        entries = audit_resp.json()["entries"]

        matching = [e for e in entries if e.get("invocation_id") == invocation_id]
        assert len(matching) >= 1, (
            f"Expected audit entry for {invocation_id}, found 0 "
            f"(total entries: {len(entries)})"
        )
        assert matching[0].get("upstream_service") == upstream, (
            f"Expected upstream_service '{upstream}' in audit entry, "
            f"got '{matching[0].get('upstream_service')}'"
        )


class TestCrossServiceLineage:
    def test_task_id_propagation_accepted(self, client, bootstrap_bearer, read_capability, all_scopes, sample_inputs):
        """A task_id not created by this service is accepted (services must not validate origin).

        Services MUST accept any syntactically valid task_id in the request,
        regardless of whether it was created on this service. task_id is a
        logical grouping mechanism, not a reference to a service-local resource.
        """
        cap_name, _ = read_capability
        # Issue token without task binding so we can provide any task_id
        token = issue_token(client, all_scopes, cap_name, bootstrap_bearer, task_id=None)
        params = sample_inputs.get(cap_name, {})
        # Use a task_id format that clearly did not originate from this service
        foreign_task_id = f"foreign-service-task-{uuid.uuid4().hex[:12]}"

        resp = client.post(
            f"/anip/invoke/{cap_name}",
            headers={"Authorization": f"Bearer {token}"},
            json={"parameters": params, "task_id": foreign_task_id},
        )
        assert resp.status_code == 200, (
            f"Service rejected a foreign task_id — services must not validate task_id origin: "
            f"{resp.status_code} {resp.text}"
        )
        data = resp.json()
        assert data.get("success") is True, f"Invoke not successful: {data}"
        assert data.get("task_id") == foreign_task_id, (
            f"Expected task_id '{foreign_task_id}' echoed, got '{data.get('task_id')}'"
        )

    def test_foreign_parent_invocation_id_accepted(self, client, bootstrap_bearer, read_capability, all_scopes, sample_inputs):
        """A valid parent_invocation_id from a foreign service is accepted and echoed.

        Services MUST NOT reject a parent_invocation_id simply because the
        referenced invocation did not originate on this service. The field is
        syntactically validated only — referential validation is explicitly
        prohibited by the spec to enable cross-service invocation trees.
        """
        cap_name, _ = read_capability
        token = issue_token(client, all_scopes, cap_name, bootstrap_bearer)
        params = sample_inputs.get(cap_name, {})
        # Generate a random valid inv-{hex12} ID as if it came from a foreign service
        foreign_parent_id = f"inv-{uuid.uuid4().hex[:12]}"

        resp = client.post(
            f"/anip/invoke/{cap_name}",
            headers={"Authorization": f"Bearer {token}"},
            json={"parameters": params, "parent_invocation_id": foreign_parent_id},
        )
        assert resp.status_code == 200, (
            f"Service rejected a foreign parent_invocation_id — services MUST NOT "
            f"perform referential validation: {resp.status_code} {resp.text}"
        )
        data = resp.json()
        assert data.get("success") is True, f"Invoke not successful: {data}"
        assert data.get("parent_invocation_id") == foreign_parent_id, (
            f"Expected foreign parent_invocation_id '{foreign_parent_id}' echoed, "
            f"got '{data.get('parent_invocation_id')}'"
        )
        # Verify format is preserved exactly
        assert re.match(r"^inv-[0-9a-f]{12}$", data["parent_invocation_id"]), (
            f"parent_invocation_id format invalid: '{data['parent_invocation_id']}'"
        )
