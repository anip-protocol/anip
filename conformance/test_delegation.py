"""Conformance tests for delegation enforcement.

Spec references: §3.2 (delegation tokens: purpose-bound, scope narrowing),
§6.3 ("The service MUST validate the token's scope, purpose, expiry, and
constraints"), and the behavioral-conformance list: "Purpose-binding is
enforced: a token issued for book_flight cannot invoke search_flights",
"Scope narrowing: a child token cannot have broader scope than its parent",
"Delegation depth limits are respected".

These tests need a service with at least two capabilities whose minimum
scopes are unrelated (neither is a prefix of the other).
"""
import uuid

import pytest

from conftest import issue_token, issue_token_full


def _failure_type(body: dict) -> str | None:
    failure = body.get("failure")
    return failure.get("type") if isinstance(failure, dict) else None


def _invoke(client, token: str, capability: str, params: dict) -> dict:
    resp = client.post(
        f"/anip/invoke/{capability}",
        headers={"Authorization": f"Bearer {token}"},
        json={"parameters": params},
    )
    return resp.json()


def _scope_covers(parent_scope: list[str], child_scope: list[str]) -> bool:
    bases = [s.split(":")[0] for s in parent_scope]
    return all(
        any(c.split(":")[0] == b or c.split(":")[0].startswith(b + ".") for b in bases)
        for c in child_scope
    )


@pytest.fixture(scope="module")
def unrelated_capabilities(read_capability, write_capability):
    """(read_name, read_scope, write_name, write_scope) with unrelated scopes."""
    read_name, read_scope = read_capability
    write_name, write_scope = write_capability
    if not read_scope or not write_scope:
        pytest.skip("capabilities without a minimum_scope cannot exercise delegation rules")
    if _scope_covers(read_scope, write_scope) or _scope_covers(write_scope, read_scope):
        pytest.skip("read and write capability scopes overlap on this service")
    return read_name, read_scope, write_name, write_scope


class TestPurposeBinding:
    def test_token_bound_to_another_capability_is_rejected(
        self, client, bootstrap_bearer, unrelated_capabilities, all_scopes, sample_inputs
    ):
        """A token issued for one capability MUST NOT invoke another, even
        when its scope covers both."""
        read_name, _, write_name, _ = unrelated_capabilities
        token = issue_token(client, all_scopes, write_name, bootstrap_bearer, task_id=None)

        data = _invoke(client, token, read_name, sample_inputs.get(read_name, {}))

        assert data.get("success") is False, (
            f"A token bound to '{write_name}' was accepted for '{read_name}': {data}"
        )
        assert _failure_type(data) == "purpose_mismatch", (
            f"Expected failure type 'purpose_mismatch', got {data.get('failure')}"
        )

    def test_token_invokes_the_capability_it_is_bound_to(
        self, client, bootstrap_bearer, unrelated_capabilities, all_scopes, sample_inputs
    ):
        """Control: the same kind of token works for its own capability."""
        read_name, _, _, _ = unrelated_capabilities
        token = issue_token(client, all_scopes, read_name, bootstrap_bearer, task_id=None)

        data = _invoke(client, token, read_name, sample_inputs.get(read_name, {}))

        assert data.get("success") is True, f"Invoke failed: {data}"


class TestDelegatedIssuance:
    def test_delegated_token_invokes_its_capability(
        self, client, bootstrap_bearer, unrelated_capabilities, sample_inputs
    ):
        """Control: a child token narrowed from a parent works."""
        read_name, read_scope, _, _ = unrelated_capabilities
        status, root = issue_token_full(client, read_scope, read_name, bootstrap_bearer, task_id=None)
        assert status == 200 and root.get("issued") is True, f"Root issuance failed: {root}"

        status, child = issue_token_full(
            client, read_scope, read_name, bootstrap_bearer, task_id=None,
            parent_token=root["token_id"],
        )
        assert status == 200 and child.get("issued") is True, f"Delegated issuance failed: {child}"

        data = _invoke(client, child["token"], read_name, sample_inputs.get(read_name, {}))
        assert data.get("success") is True, f"Invoke with the delegated token failed: {data}"

    def test_delegated_token_cannot_widen_scope(
        self, client, bootstrap_bearer, unrelated_capabilities
    ):
        """A child token MUST NOT carry scope its parent does not have."""
        read_name, read_scope, write_name, write_scope = unrelated_capabilities
        status, root = issue_token_full(client, read_scope, read_name, bootstrap_bearer, task_id=None)
        assert status == 200 and root.get("issued") is True, f"Root issuance failed: {root}"

        _, child = issue_token_full(
            client, read_scope + write_scope, write_name, bootstrap_bearer, task_id=None,
            parent_token=root["token_id"],
        )

        assert child.get("issued") is not True and "token" not in child, (
            f"A child token with scope {read_scope + write_scope} was issued from a "
            f"parent holding only {read_scope}"
        )
        assert _failure_type(child) == "scope_escalation", (
            f"Expected failure type 'scope_escalation', got {child}"
        )

    @pytest.mark.parametrize("child_budget", ["900", "NaN", "-1", "lots", None],
                             ids=["raised", "nan", "negative", "unparseable", "dropped"])
    def test_delegated_token_cannot_loosen_a_scope_budget(
        self, client, bootstrap_bearer, unrelated_capabilities, child_budget
    ):
        """A budget carried by a parent scope ("scope:max_$500") may be kept
        or lowered by a child, never raised, dropped, or replaced by a value
        that is not a finite, non-negative amount."""
        _, _, write_name, write_scope = unrelated_capabilities
        base = write_scope[0]
        status, root = issue_token_full(
            client, [f"{base}:max_$500"], write_name, bootstrap_bearer, task_id=None)
        assert status == 200 and root.get("issued") is True, f"Root issuance failed: {root}"

        child_scope = base if child_budget is None else f"{base}:max_${child_budget}"
        _, child = issue_token_full(
            client, [child_scope], write_name, bootstrap_bearer, task_id=None,
            parent_token=root["token_id"],
        )

        assert child.get("issued") is not True and "token" not in child, (
            f"A child token with scope '{child_scope}' was issued from a parent "
            f"holding '{base}:max_$500'"
        )
        assert _failure_type(child) == "scope_escalation", (
            f"Expected failure type 'scope_escalation', got {child}"
        )

    def test_sub_scope_cannot_shed_the_parents_scope_budget(
        self, client, bootstrap_bearer, unrelated_capabilities
    ):
        """A budget on a parent scope bounds every scope beneath it: a child
        of "x:max_$500" cannot hold "x.sub" without a budget."""
        _, _, write_name, write_scope = unrelated_capabilities
        base = write_scope[0]
        if "." not in base:
            pytest.skip("needs a dotted scope to form a parent scope")
        parent_base = base.rsplit(".", 1)[0]
        status, root = issue_token_full(
            client, [f"{parent_base}:max_$500"], write_name, bootstrap_bearer, task_id=None)
        assert status == 200 and root.get("issued") is True, f"Root issuance failed: {root}"

        _, child = issue_token_full(
            client, [base], write_name, bootstrap_bearer, task_id=None,
            parent_token=root["token_id"],
        )

        assert child.get("issued") is not True and "token" not in child, (
            f"A child token with scope '{base}' (no budget) was issued from a parent "
            f"holding '{parent_base}:max_$500'"
        )
        assert _failure_type(child) == "scope_escalation", (
            f"Expected failure type 'scope_escalation', got {child}"
        )

    def test_delegated_token_can_lower_a_scope_budget(
        self, client, bootstrap_bearer, unrelated_capabilities
    ):
        """Control: lowering a scope budget is allowed."""
        _, _, write_name, write_scope = unrelated_capabilities
        base = write_scope[0]
        status, root = issue_token_full(
            client, [f"{base}:max_$500"], write_name, bootstrap_bearer, task_id=None)
        assert status == 200 and root.get("issued") is True, f"Root issuance failed: {root}"

        status, child = issue_token_full(
            client, [f"{base}:max_$100"], write_name, bootstrap_bearer, task_id=None,
            parent_token=root["token_id"],
        )
        assert status == 200 and child.get("issued") is True, f"Lowering a scope budget was refused: {child}"

    def test_only_the_parent_subject_can_delegate(
        self, client, bootstrap_bearer, unrelated_capabilities
    ):
        """Only the principal a token was issued to may delegate from it."""
        read_name, read_scope, _, _ = unrelated_capabilities
        # Parent held by the bootstrap principal.
        status, parent = issue_token_full(client, read_scope, read_name, bootstrap_bearer, task_id=None)
        assert status == 200 and parent.get("issued") is True, f"Root issuance failed: {parent}"

        # A token for a different principal, used as that principal's credential.
        other_subject = f"agent:conformance-{uuid.uuid4().hex[:8]}"
        resp = client.post(
            "/anip/tokens",
            headers={"Authorization": f"Bearer {bootstrap_bearer}"},
            json={"subject": other_subject, "scope": read_scope, "capability": read_name,
                  "purpose_parameters": {}},
        )
        other = resp.json()
        assert resp.status_code == 200 and other.get("issued") is True, f"Issuance failed: {other}"

        resp = client.post(
            "/anip/tokens",
            headers={"Authorization": f"Bearer {other['token']}"},
            json={"scope": read_scope, "capability": read_name, "purpose_parameters": {},
                  "parent_token": parent["token_id"]},
        )
        body = resp.json()

        assert body.get("issued") is not True and "token" not in body, (
            f"'{other_subject}' delegated from a token it does not hold: {body}"
        )
        assert _failure_type(body) == "insufficient_authority", (
            f"Expected failure type 'insufficient_authority', got {body}"
        )


class TestTokenAsCredential:
    """§6.3: root issuance authenticates with the bootstrap credential;
    delegated issuance authenticates with an existing token and names a
    parent_token. A token is a credential for delegating, never for minting
    a fresh root token."""

    def _held_token(self, client, bootstrap_bearer, subject, scope, capability):
        resp = client.post(
            "/anip/tokens",
            headers={"Authorization": f"Bearer {bootstrap_bearer}"},
            json={"subject": subject, "scope": scope, "capability": capability,
                  "purpose_parameters": {}},
        )
        body = resp.json()
        assert resp.status_code == 200 and body.get("issued") is True, f"Issuance failed: {body}"
        return body

    def test_holder_delegates_using_its_token_as_credential(
        self, client, bootstrap_bearer, unrelated_capabilities, sample_inputs
    ):
        read_name, read_scope, _, _ = unrelated_capabilities
        subject = f"agent:conformance-{uuid.uuid4().hex[:8]}"
        held = self._held_token(client, bootstrap_bearer, subject, read_scope, read_name)

        resp = client.post(
            "/anip/tokens",
            headers={"Authorization": f"Bearer {held['token']}"},
            json={"scope": read_scope, "capability": read_name, "purpose_parameters": {},
                  "parent_token": held["token_id"]},
        )
        child = resp.json()
        assert resp.status_code == 200 and child.get("issued") is True, (
            f"The holder could not delegate from its own token: {resp.status_code} {child}"
        )

        data = _invoke(client, child["token"], read_name, sample_inputs.get(read_name, {}))
        assert data.get("success") is True, f"Invoke with the delegated token failed: {data}"

    def test_token_credential_cannot_issue_a_root_token(
        self, client, bootstrap_bearer, unrelated_capabilities
    ):
        """The holder of a narrow token MUST NOT obtain a root token, with
        any scope, by presenting that token as its credential."""
        read_name, read_scope, write_name, write_scope = unrelated_capabilities
        subject = f"agent:conformance-{uuid.uuid4().hex[:8]}"
        held = self._held_token(client, bootstrap_bearer, subject, read_scope, read_name)

        resp = client.post(
            "/anip/tokens",
            headers={"Authorization": f"Bearer {held['token']}"},
            json={"scope": read_scope + write_scope, "capability": write_name,
                  "purpose_parameters": {}},
        )
        body = resp.json()

        assert body.get("issued") is not True and "token" not in body, (
            f"A token holding {read_scope} was used as a credential to issue a root "
            f"token with scope {read_scope + write_scope}"
        )
        assert _failure_type(body) == "insufficient_authority", (
            f"Expected failure type 'insufficient_authority', got {body}"
        )


class TestDelegationDepth:
    def test_chain_deeper_than_the_limit_is_rejected(
        self, client, bootstrap_bearer, unrelated_capabilities, sample_inputs
    ):
        """The default max_delegation_depth is 3. A token four delegations
        below the root MUST be rejected, at issuance or at invocation."""
        read_name, read_scope, _, _ = unrelated_capabilities
        status, token = issue_token_full(client, read_scope, read_name, bootstrap_bearer, task_id=None)
        assert status == 200 and token.get("issued") is True, f"Root issuance failed: {token}"

        for depth in range(1, 5):
            _, child = issue_token_full(
                client, read_scope, read_name, bootstrap_bearer, task_id=None,
                parent_token=token["token_id"],
            )
            if child.get("issued") is not True:
                assert depth == 4, f"Delegation at depth {depth} (within the limit) was refused: {child}"
                assert _failure_type(child) == "delegation_depth_exceeded", (
                    f"Expected failure type 'delegation_depth_exceeded', got {child}"
                )
                return
            token = child

        data = _invoke(client, token["token"], read_name, sample_inputs.get(read_name, {}))
        assert data.get("success") is False, (
            f"A token at delegation depth 4 was accepted (limit is 3): {data}"
        )
        assert _failure_type(data) == "delegation_depth_exceeded", (
            f"Expected failure type 'delegation_depth_exceeded', got {data.get('failure')}"
        )
