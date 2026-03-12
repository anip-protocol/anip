import httpx
import pytest
from fastapi.testclient import TestClient
from anip_server.main import app


@pytest.fixture
def client():
    return TestClient(app)


def pytest_addoption(parser):
    parser.addoption(
        "--anip-url", default=None,
        help="ANIP service URL for conformance tests (default: in-process TestClient)",
    )
    parser.addoption(
        "--anip-api-key", default="demo-human-key",
        help="API key for authenticated ANIP requests",
    )


class LiveServiceClient:
    """Thin wrapper around httpx that matches TestClient interface for conformance tests."""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def get(self, path, **kwargs):
        return httpx.get(f"{self.base_url}{path}", **kwargs)

    def post(self, path, json=None, headers=None, **kwargs):
        headers = dict(headers or {})
        return httpx.post(f"{self.base_url}{path}", json=json, headers=headers, **kwargs)


@pytest.fixture
def service(request):
    """Service client — in-process TestClient or live HTTP client."""
    url = request.config.getoption("--anip-url")
    if url:
        api_key = request.config.getoption("--anip-api-key")
        return LiveServiceClient(url, api_key)
    return TestClient(app)


@pytest.fixture
def auth_headers(request):
    api_key = request.config.getoption("--anip-api-key", default="demo-human-key")
    return {"Authorization": f"Bearer {api_key}"}
