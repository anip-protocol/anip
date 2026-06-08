"""Shared fixtures for ANIP Studio backend tests.

Sets DATABASE_URL before importing the app, provides a TestClient,
and isolates tests in a per-module Postgres schema so they never mutate
the live local Studio data.
"""

import os
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

import psycopg


def _with_search_path(database_url: str, schema_name: str) -> str:
    parsed = urlsplit(database_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["options"] = f"-csearch_path={schema_name}"
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))


BASE_DATABASE_URL = os.environ.get(
    "STUDIO_TEST_BASE_DATABASE_URL",
    "postgresql://anip:anip@localhost:5432/anip_studio",
)
TEST_SCHEMA = f"studio_test_{uuid4().hex[:12]}"

with psycopg.connect(BASE_DATABASE_URL, autocommit=True) as bootstrap_conn:
    bootstrap_conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{TEST_SCHEMA}"')

# Keep backend tests independent from the developer shell. Individual tests that
# need env-managed providers set these values explicitly with monkeypatch.
for _key in (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "STUDIO_ASSISTANT_API_KEY",
    "STUDIO_SIMULATOR_API_KEY",
):
    os.environ.pop(_key, None)

# Must be set before any import of studio.server.app / db
os.environ["DATABASE_URL"] = _with_search_path(BASE_DATABASE_URL, TEST_SCHEMA)

import pytest
from fastapi.testclient import TestClient

from studio.server.app import app, VOCAB_DEFAULTS_PATH
from studio.server.db import close_pool, get_pool
from studio.server.repository import load_vocabulary_defaults


@pytest.fixture(scope="module")
def client():
    """A FastAPI TestClient whose lifespan (init_db + vocab load) runs once per module.

    After the lifespan has run (tables exist, canonical vocab loaded), we
    clean ALL data tables and re-seed canonical vocabulary so every module
    starts from a perfectly clean slate.
    """
    with psycopg.connect(BASE_DATABASE_URL, autocommit=True) as bootstrap_conn:
        bootstrap_conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{TEST_SCHEMA}"')

    with TestClient(app) as c:
        # Lifespan has now executed — tables exist.
        # Wipe everything in dependency order, including vocabulary.
        with get_pool().connection() as conn:
            # Truncate in dependency order (children before parents)
            conn.execute("DELETE FROM evaluations")
            conn.execute("DELETE FROM shapes")
            conn.execute("DELETE FROM proposals")
            conn.execute("DELETE FROM scenarios")
            conn.execute("DELETE FROM requirements_sets")
            conn.execute("DELETE FROM project_documents")
            conn.execute("DELETE FROM local_publications")
            conn.execute("DELETE FROM integration_discovery_records")
            conn.execute("DELETE FROM application_integration_projects")
            conn.execute("DELETE FROM data_access_projects")
            conn.execute("DELETE FROM workspace_connections")
            conn.execute("DELETE FROM projects")
            conn.execute("DELETE FROM workspaces")
            conn.execute("DELETE FROM studio_settings")
            conn.execute("DELETE FROM vocabulary")
            conn.commit()
            # Re-seed canonical vocabulary entries from the defaults file.
            load_vocabulary_defaults(conn, str(VOCAB_DEFAULTS_PATH))
            conn.commit()
        yield c

    close_pool()
    with psycopg.connect(BASE_DATABASE_URL, autocommit=True) as bootstrap_conn:
        bootstrap_conn.execute(f'DROP SCHEMA IF EXISTS "{TEST_SCHEMA}" CASCADE')
