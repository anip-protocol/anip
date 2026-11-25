"""Canonical JSON for approval digests is RFC 8785 (SPEC.md §4.7)."""
from __future__ import annotations

import hashlib
import json
import math
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from anip_core import (
    CapabilityDeclaration,
    CapabilityInput,
    CapabilityOutput,
    GrantPolicy,
    SideEffect,
    SideEffectType,
)

from anip_service import ANIPError, ANIPService, Capability
from anip_service.v023 import canonical_json, sha256_digest

VECTORS_PATH = (
    Path(__file__).resolve().parents[3] / "canonical-json-fixtures" / "rfc8785-vectors.json"
)
VECTORS = json.loads(VECTORS_PATH.read_text(encoding="utf-8"))["vectors"]


def test_the_shared_vectors_are_all_here():
    assert len(VECTORS) >= 65
    assert len({v["name"] for v in VECTORS}) == len(VECTORS)


@pytest.mark.parametrize("vector", VECTORS, ids=[v["name"] for v in VECTORS])
def test_shared_vector(vector):
    """Parse the JSON text the way the HTTP binding does (Starlette's
    ``Request.json()`` is ``json.loads``), canonicalise, compare bytes."""
    value = json.loads(vector["input"])

    canonical = canonical_json(value)

    assert canonical.encode("utf-8").hex() == vector["canonical_utf8_hex"]
    assert canonical == vector["canonical"]
    assert sha256_digest(value) == vector["sha256"]
    assert vector["sha256"] == "sha256:" + hashlib.sha256(
        bytes.fromhex(vector["canonical_utf8_hex"])).hexdigest()


class TestNumbers:
    @pytest.mark.parametrize("value,expected", [
        (5, "5"), (5.0, "5"), (-0.0, "0"), (0, "0"), (-5, "-5"),
        (True, "true"), (False, "false"),
        (2**53 + 1, "9007199254740992"),
        (10**21, "1e+21"), (10**20, "100000000000000000000"),
        (123456789012345678901234567890, "1.2345678901234568e+29"),
        (1e-7, "1e-7"), (1e-6, "0.000001"), (1.5e-7, "1.5e-7"),
        (5e-324, "5e-324"), (1.7976931348623157e308, "1.7976931348623157e+308"),
        (0.1 + 0.2, "0.30000000000000004"),
        (Decimal("5.00"), "5"), (Decimal("0.1"), "0.1"), (Decimal("1E+2"), "100"),
    ])
    def test_number(self, value, expected):
        assert canonical_json(value) == expected

    @pytest.mark.parametrize("value", [
        math.nan, math.inf, -math.inf, Decimal("NaN"), Decimal("Infinity"), 10**400,
    ])
    def test_numbers_json_cannot_carry_are_an_error(self, value):
        with pytest.raises(ValueError):
            canonical_json({"n": value})

    def test_integer_and_integral_float_have_one_digest(self):
        assert sha256_digest({"passengers": 5}) == sha256_digest({"passengers": 5.0})
        assert sha256_digest({"passengers": 5}) != sha256_digest({"passengers": 6})
        assert sha256_digest({"flag": True}) != sha256_digest({"flag": 1})


class TestStructure:
    def test_keys_are_sorted_by_utf16_code_units(self):
        # U+1F600 is the surrogate pair D83D DE00, which sorts before U+FF5E.
        value = {"～": 1, "\U0001f600": 2, "a": 3}
        assert canonical_json(value) == '{"a":3,"\U0001f600":2,"～":1}'

    def test_tuples_are_arrays(self):
        assert canonical_json({"a": (1, 2.0, "x")}) == '{"a":[1,2,"x"]}'

    def test_only_the_required_characters_are_escaped(self):
        assert canonical_json("</script>& \u007fé\"\\\n\x01") == (
            '"</script>& \u007fé\\"\\\\\\n\\u0001"')

    def test_object_keys_must_be_strings(self):
        with pytest.raises(TypeError):
            canonical_json({1: "a"})

    def test_a_value_json_cannot_carry_is_an_error(self):
        with pytest.raises(TypeError):
            canonical_json({"a": object()})

    def test_a_lone_surrogate_is_an_error(self):
        with pytest.raises(ValueError):
            canonical_json({"a": "\ud800"})


class TestGrantSigningIsUnchanged:
    """The grant signature is not an approval digest; its bytes stay as they
    were, so stored grants keep verifying."""

    def test_signing_bytes(self):
        from anip_service.v023 import _grant_signing_bytes

        grant = {"grant_id": "g", "max_uses": 1, "ratio": 5.0, "use_count": 3, "signature": "s"}
        assert _grant_signing_bytes(grant) == b'{"grant_id":"g","max_uses":1,"ratio":5.0}'


def _approval_capability() -> Capability:
    declaration = CapabilityDeclaration(
        name="transfer",
        description="Transfer",
        inputs=[
            CapabilityInput(name="amount", type="integer"),
            CapabilityInput(name="to_account", type="string"),
        ],
        output=CapabilityOutput(type="object", fields=["amount"]),
        side_effect=SideEffect(type=SideEffectType.IRREVERSIBLE, rollback_window="none"),
        minimum_scope=["transfer"],
        grant_policy=GrantPolicy(
            allowed_grant_types=["one_time"], default_grant_type="one_time",
            expires_in_seconds=900, max_uses=1),
    )

    def handler(ctx, params: dict[str, Any]) -> dict[str, Any]:
        if params["amount"] > 10000 and not ctx.approval_grant:
            raise ANIPError(
                "approval_required", "needs approval",
                resolution={"action": "request_approval", "recovery_class": "wait_then_retry"})
        return {"amount": params["amount"]}

    return Capability(declaration=declaration, handler=handler)


async def test_integral_float_continues_an_approved_integer():
    """SPEC.md §4.7: 5 and 5.0 are the same JSON number, so a continuation
    that writes the approved integer with a fraction part is not drift."""
    service = ANIPService(
        service_id="test-digest", capabilities=[_approval_capability()], storage=":memory:")
    token, _ = await service._engine.issue_root_token(
        authenticated_principal="human:test@example.com",
        subject="human:test@example.com",
        scope=["transfer"], capability="transfer", ttl_hours=1,
    )
    first = await service.invoke("transfer", token, {"amount": 50000, "to_account": "acct-1"})
    request_id = first["failure"]["approval_required"]["approval_request_id"]
    grant = await service.issue_approval_grant(
        request_id, "one_time", {"subject": "human:approver"})

    drifted = await service.invoke(
        "transfer", token, {"amount": 50001, "to_account": "acct-1"},
        approval_grant=grant["grant_id"])
    assert drifted["failure"]["type"] == "grant_param_drift"

    continued = await service.invoke(
        "transfer", token, {"to_account": "acct-1", "amount": 50000.0},
        approval_grant=grant["grant_id"])
    assert continued["success"] is True, continued
    assert continued["result"] == {"amount": 50000.0}
