"""v0.24 conformance — input resolution metadata parse + validate (Python reference)."""
# Python reference only; per-runtime parsing covered by runtime-specific test files in packages/*.
# When the conformance suite runs against a non-Python target (TS/Go/Java/C#),
# anip_core is not installed in the environment — skip the entire module rather than failing collection.
import json
import pytest
from pathlib import Path

anip_core_models = pytest.importorskip(
    "anip_core.models",
    reason="anip_core not installed in this conformance environment (non-Python target)",
)
pydantic = pytest.importorskip("pydantic")

CapabilityInput = anip_core_models.CapabilityInput
ValidationError = pydantic.ValidationError

FIXTURE = Path(__file__).parent / "samples" / "v024_input_resolution_examples.json"
_DATA = json.loads(FIXTURE.read_text())


@pytest.mark.parametrize("case", _DATA["valid"], ids=lambda c: c["name"])
def test_valid_inputs_parse_and_round_trip(case):
    inp = CapabilityInput.model_validate(case["input"])
    raw = inp.model_dump_json()
    parsed = CapabilityInput.model_validate_json(raw)
    assert parsed == inp


@pytest.mark.parametrize("case", _DATA["invalid"], ids=lambda c: c["name"])
def test_invalid_inputs_rejected(case):
    with pytest.raises(ValidationError):
        CapabilityInput.model_validate(case["input"])
