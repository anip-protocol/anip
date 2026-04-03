"""Shared fixtures for ANIP Studio backend tests.

Sets DATABASE_URL before importing the app, provides a TestClient,
and truncates data tables between test modules so tests stay isolated.
"""

import os

# Must be set before any import of studio.server.app / db
os.environ["DATABASE_URL"] = "postgresql://anip:anip@localhost:5432/anip_studio"

import pytest
from fastapi.testclient import TestClient

from studio.server.app import app, VOCAB_DEFAULTS_PATH
from studio.server.db import get_pool
from studio.server.repository import load_vocabulary_defaults


@pytest.fixture(scope="module")
def client():
    """A FastAPI TestClient whose lifespan (init_db + vocab load) runs once per module.

    After the lifespan has run (tables exist, canonical vocab loaded), we
    clean ALL data tables and re-seed canonical vocabulary so every module
    starts from a perfectly clean slate.
    """
    with TestClient(app) as c:
        # Lifespan has now executed — tables exist.
        # Wipe everything in dependency order, including vocabulary.
        with get_pool().connection() as conn:
            conn.execute("DELETE FROM evaluations")
            conn.execute("DELETE FROM proposals")
            conn.execute("DELETE FROM scenarios")
            conn.execute("DELETE FROM requirements_sets")
            conn.execute("DELETE FROM projects")
            conn.execute("DELETE FROM vocabulary")
            conn.commit()
            # Re-seed canonical vocabulary entries from the defaults file.
            load_vocabulary_defaults(conn, str(VOCAB_DEFAULTS_PATH))
        yield c
