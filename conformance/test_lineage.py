"""Conformance tests for ANIP task_id and parent_invocation_id lineage.

Spec references: §6.3 (invocation request/response), §5.4 (audit),
v0.12 additions for task identity and invocation lineage.
"""
import time
import uuid

from conftest import issue_token


class TestTaskIdEcho:
    def test_invoke_echoes_task_id(self, client, bootstrap_bearer, read_capability, all_scopes, sample_inputs):
        """Invoking with task_id in the body should echo it back in the response."""
        cap_name, _ = read_capability
        token = issue_token(client, all_scopes, cap_name, bootstrap_bearer)
        task_id = f"task-{uuid.uuid4().hex[:12]}"
        params = sample_inputs.get(cap_name, {})

        resp = client.post(
            f"/anip/invoke/{cap_name}",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "parameters": params,
                "task_id": task_id,
            },
        )
        data = resp.json()
        assert "invocation_id" in data
        assert data.get("task_id") == task_id, (
            f"Expected task_id '{task_id}' to be echoed in response, "
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
            json={
                "parameters": params,
                "parent_invocation_id": parent_id,
            },
        )
        data = resp.json()
        assert "invocation_id" in data
        assert data.get("parent_invocation_id") == parent_id, (
            f"Expected parent_invocation_id '{parent_id}' to be echoed in response, "
            f"got '{data.get('parent_invocation_id')}'"
        )


class TestLineageInAudit:
    def test_task_id_recorded_in_audit(self, client, bootstrap_bearer, read_capability, all_scopes, sample_inputs):
        """Invoking with task_id should record it in the audit log entry."""
        cap_name, _ = read_capability
        token = issue_token(client, all_scopes, cap_name, bootstrap_bearer)
        task_id = f"task-{uuid.uuid4().hex[:12]}"
        params = sample_inputs.get(cap_name, {})

        # Invoke with task_id
        invoke_resp = client.post(
            f"/anip/invoke/{cap_name}",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "parameters": params,
                "task_id": task_id,
            },
        )
        invoke_data = invoke_resp.json()
        invocation_id = invoke_data["invocation_id"]

        # Allow async audit write to complete
        time.sleep(1)

        # Query audit log — use bootstrap bearer (not delegation token)
        # to avoid scoping issues, and search for our entry by invocation_id
        audit_resp = client.post(
            "/anip/audit",
            headers={"Authorization": f"Bearer {bootstrap_bearer}"},
        )
        assert audit_resp.status_code == 200
        audit_data = audit_resp.json()

        matching = [
            e for e in audit_data["entries"]
            if e.get("invocation_id") == invocation_id
        ]
        assert len(matching) >= 1, (
            f"Expected at least 1 audit entry for {invocation_id}, found 0. "
            f"Total entries: {audit_data.get('count', 'unknown')}"
        )
        assert matching[0].get("task_id") == task_id, (
            f"Audit entry should contain task_id '{task_id}', "
            f"got '{matching[0].get('task_id')}'"
        )

    def test_audit_filter_by_task_id(self, client, bootstrap_bearer, read_capability, all_scopes, sample_inputs):
        """Audit query with ?task_id=X should return only entries with that task_id."""
        cap_name, _ = read_capability
        token = issue_token(client, all_scopes, cap_name, bootstrap_bearer)
        task_id_a = f"task-a-{uuid.uuid4().hex[:8]}"
        task_id_b = f"task-b-{uuid.uuid4().hex[:8]}"
        params = sample_inputs.get(cap_name, {})

        # Invoke twice with different task_ids
        client.post(
            f"/anip/invoke/{cap_name}",
            headers={"Authorization": f"Bearer {token}"},
            json={"parameters": params, "task_id": task_id_a},
        )
        client.post(
            f"/anip/invoke/{cap_name}",
            headers={"Authorization": f"Bearer {token}"},
            json={"parameters": params, "task_id": task_id_b},
        )

        # Allow async audit writes to complete
        time.sleep(1)

        # Filter audit by task_id_a — use bootstrap bearer
        audit_resp = client.post(
            f"/anip/audit?task_id={task_id_a}",
            headers={"Authorization": f"Bearer {bootstrap_bearer}"},
        )
        assert audit_resp.status_code == 200
        audit_data = audit_resp.json()

        assert audit_data["count"] >= 1, (
            f"Expected at least 1 audit entry for task_id '{task_id_a}'"
        )
        for entry in audit_data["entries"]:
            assert entry.get("task_id") == task_id_a, (
                f"Audit filter by task_id returned entry with wrong task_id: "
                f"expected '{task_id_a}', got '{entry.get('task_id')}'"
            )

    def test_audit_filter_by_parent_invocation_id(self, client, bootstrap_bearer, read_capability, all_scopes, sample_inputs):
        """Audit query with ?parent_invocation_id=X should return only matching entries."""
        cap_name, _ = read_capability
        token = issue_token(client, all_scopes, cap_name, bootstrap_bearer)
        parent_id_a = "inv-00000000aa01"
        parent_id_b = "inv-00000000bb02"
        params = sample_inputs.get(cap_name, {})

        # Invoke twice with different parent_invocation_ids
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

        # Allow async audit writes to complete
        time.sleep(1)

        # Filter audit by parent_invocation_id_a — use bootstrap bearer
        audit_resp = client.post(
            f"/anip/audit?parent_invocation_id={parent_id_a}",
            headers={"Authorization": f"Bearer {bootstrap_bearer}"},
        )
        assert audit_resp.status_code == 200
        audit_data = audit_resp.json()

        assert audit_data["count"] >= 1, (
            f"Expected at least 1 audit entry for parent_invocation_id '{parent_id_a}'"
        )
        for entry in audit_data["entries"]:
            assert entry.get("parent_invocation_id") == parent_id_a, (
                f"Audit filter by parent_invocation_id returned entry with wrong value: "
                f"expected '{parent_id_a}', got '{entry.get('parent_invocation_id')}'"
            )
