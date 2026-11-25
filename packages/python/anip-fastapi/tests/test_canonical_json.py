"""The shared RFC 8785 vectors, parsed the way the binding parses a request
body (``starlette.requests.Request.json``) and then canonicalised."""
import json
from pathlib import Path

import pytest
from starlette.requests import Request

from anip_service.v023 import canonical_json, sha256_digest

VECTORS_PATH = (
    Path(__file__).resolve().parents[3] / "canonical-json-fixtures" / "rfc8785-vectors.json"
)
VECTORS = json.loads(VECTORS_PATH.read_text(encoding="utf-8"))["vectors"]


async def _parse_as_request_body(text: str):
    body = text.encode("utf-8")

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    scope = {"type": "http", "method": "POST", "path": "/", "headers": [
        (b"content-type", b"application/json")]}
    return await Request(scope, receive).json()


def test_the_shared_vectors_are_all_here():
    assert len(VECTORS) >= 65


@pytest.mark.parametrize("vector", VECTORS, ids=[v["name"] for v in VECTORS])
async def test_shared_vector_through_the_request_parser(vector):
    value = await _parse_as_request_body(vector["input"])

    assert canonical_json(value).encode("utf-8").hex() == vector["canonical_utf8_hex"]
    assert sha256_digest(value) == vector["sha256"]
