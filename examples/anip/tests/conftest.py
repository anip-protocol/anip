import pytest
from fastapi.testclient import TestClient
from app import app, service


@pytest.fixture
def client():
    return TestClient(app)
