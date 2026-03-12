import pytest
from fastapi.testclient import TestClient
from anip_server.main import app


@pytest.fixture
def client():
    return TestClient(app)
