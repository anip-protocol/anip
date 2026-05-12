"""v0.24 conformance — input resolution metadata parse + validate (Python reference)."""
# Python reference only; per-runtime parsing covered by runtime-specific test files in packages/*.
import json
import pytest
from pathlib import Path
from anip_core.models import CapabilityInput
from pydantic import ValidationError

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
