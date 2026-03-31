"""Conformance tests for ANIP task_id and parent_invocation_id lineage.

Spec references: §6.3 (invocation request/response), §5.4 (audit),
v0.12 additions for task identity and invocation lineage.

Important: issue_token() binds a task_id by default ("conformance-test").
Tests that need custom task_id values must issue tokens with task_id=None
to avoid purpose_mismatch failures.
"""
import time
import uuid

from conftest import issue_token


class TestTaskIdEcho:
    def test_invoke_echoes_task_id_from_token(self, client, bootstrap_bearer, read_capability, all_scopes, sample_inputs):
        """When the token has purpose.task_id, it should be echoed in the response."""
        cap_name, _ = read_capability
        my_task = f"task-{uuid.uuid4().hex[:12]}"
        # Issue token bound to our specific task_id
        token = issue_token(client, all_scopes, cap_name, bootstrap_bearer, task_id=my_task)
        params = sample_inputs.get(cap_name, {})

        resp = client.post(
            f"/anip/invoke/{cap_name}",
            headers={"Authorization": f"Bearer {token}"},
            json={"parameters": params},
        )
        assert resp.status_code == 200, f"Invoke failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert data.get("success") is True, f"Invoke not successful: {data}"
        assert data.get("task_id") == my_task, (
            f"Expected task_id '{my_task}' from token purpose, "
            f"got '{data.get('task_id')}'"
        )

    def test_invoke_echoes_request_task_id_when_token_unbound(self, client, bootstrap_bearer, read_capability, all_scopes, sample_inputs):
        """When token has no purpose.task_id, request task_id should be echoed."""
        cap_name, _ = read_capability
        # Issue token WITHOUT task binding
        token = issue_token(client, all_scopes, cap_name, bootstrap_bearer, task_id=None)
        request_task = f"task-{uuid.uuid4().hex[:12]}"
        params = sample_inputs.get(cap_name, {})

        resp = client.post(
            f"/anip/invoke/{cap_name}",
            headers={"Authorization": f"Bearer {token}"},
            json={"parameters": params, "task_id": request_task},
        )
        assert resp.status_code == 200, f"Invoke failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert data.get("success") is True, f"Invoke not successful: {data}"
        assert data.get("task_id") == request_task, (
            f"Expected task_id '{request_task}' from request, "
            f"got '{data.get('task_id')}'"
        )


class TestParentInvocationIdEcho:
    def test_invoke_echoes_parent_invocation_id(self, client, bootstrap_bearer, read_capability, all_scopes, sample_inputs):
        """Invoking with parent_invocation_id should echo it back in the response."""
        cap_name, _ = read_capability
        token = issue_token(client, all_scopes, cap_name, bootstrap_bearer)
        parent_id = "inv-000000000001"
        params = sample_inputs.get(cap_name, {})

        resp = client.post(
            f"/anip/invoke/{cap_name}",
            headers={"Authorization": f"Bearer {token}"},
            json={"parameters": params, "parent_invocation_id": parent_id},
        )
        assert resp.status_code == 200, f"Invoke failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert data.get("success") is True, f"Invoke not successful: {data}"
        assert data.get("parent_invocation_id") == parent_id


class TestLineageInAudit:
    def test_task_id_recorded_in_audit(self, client, bootstrap_bearer, read_capability, all_scopes, sample_inputs):
        """Invoking with task_id should record it in the audit log entry."""
        cap_name, _ = read_capability
        my_task = f"task-{uuid.uuid4().hex[:12]}"
        # Token bound to our task_id
        token = issue_token(client, all_scopes, cap_name, bootstrap_bearer, task_id=my_task)
        params = sample_inputs.get(cap_name, {})

        invoke_resp = client.post(
            f"/anip/invoke/{cap_name}",
            headers={"Authorization": f"Bearer {token}"},
            json={"parameters": params},
        )
        assert invoke_resp.status_code == 200
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
        assert matching[0].get("task_id") == my_task

    def test_audit_filter_by_task_id(self, client, bootstrap_bearer, read_capability, all_scopes, sample_inputs):
        """Audit query with ?task_id=X should return only entries with that task_id."""
        cap_name, _ = read_capability
        task_id_a = f"task-a-{uuid.uuid4().hex[:8]}"
        task_id_b = f"task-b-{uuid.uuid4().hex[:8]}"
        params = sample_inputs.get(cap_name, {})

        # Issue SEPARATE tokens for each task_id (each bound to its own task)
        token_a = issue_token(client, all_scopes, cap_name, bootstrap_bearer, task_id=task_id_a)
        token_b = issue_token(client, all_scopes, cap_name, bootstrap_bearer, task_id=task_id_b)

        client.post(
            f"/anip/invoke/{cap_name}",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"parameters": params},
        )
        client.post(
            f"/anip/invoke/{cap_name}",
            headers={"Authorization": f"Bearer {token_b}"},
            json={"parameters": params},
        )

        time.sleep(1)

        # Filter audit by task_id_a using token_a
        audit_resp = client.post(
            f"/anip/audit?task_id={task_id_a}",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert audit_resp.status_code == 200
        audit_data = audit_resp.json()

        assert audit_data["count"] >= 1, (
            f"Expected at least 1 audit entry for task_id '{task_id_a}'"
        )
        for entry in audit_data["entries"]:
            assert entry.get("task_id") == task_id_a

    def test_audit_filter_by_parent_invocation_id(self, client, bootstrap_bearer, read_capability, all_scopes, sample_inputs):
        """Audit query with ?parent_invocation_id=X should return only matching entries."""
        cap_name, _ = read_capability
        token = issue_token(client, all_scopes, cap_name, bootstrap_bearer)
        parent_id_a = "inv-00000000aa01"
        parent_id_b = "inv-00000000bb02"
        params = sample_inputs.get(cap_name, {})

        client.post(
            f"/anip/invoke/{cap_name}",
            headers={"Authorization": f"Bearer {token}"},
            json={"parameters": params, "parent_invocation_id": parent_id_a},
        )
        client.post(
            f"/anip/invoke/{cap_name}",
            headers={"Authorization": f"Bearer {token}"},
            json={"parameters": params, "parent_invocation_id": parent_id_b},
        )

        time.sleep(1)

        audit_resp = client.post(
            f"/anip/audit?parent_invocation_id={parent_id_a}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert audit_resp.status_code == 200
        audit_data = audit_resp.json()

        assert audit_data["count"] >= 1, (
            f"Expected at least 1 audit entry for parent_invocation_id '{parent_id_a}'"
        )
        for entry in audit_data["entries"]:
            assert entry.get("parent_invocation_id") == parent_id_a
