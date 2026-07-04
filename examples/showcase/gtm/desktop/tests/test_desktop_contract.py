from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_readme_positions_desktop_as_non_docker_path():
    readme = (ROOT / "README.md").read_text()

    assert "non-Docker path" in readme
    assert "Docker Compose remains the technical" in readme
    assert "Bundling Metabase" in readme


def test_desktop_contract_for_first_milestone():
    readme = (ROOT / "README.md").read_text()

    assert "one canonical generated implementation" in readme
    assert "OpenAI-compatible API key" in readme
    assert "embedded local ANIP service sidecars" in readme


def test_tauri_shell_files_exist():
    expected = [
        "package.json",
        "tsconfig.json",
        "index.html",
        "src/main.ts",
        "src-tauri/build.rs",
        "src-tauri/Cargo.toml",
        "src-tauri/src/main.rs",
        "src-tauri/src/lib.rs",
        "src-tauri/tauri.conf.json",
    ]

    for relative_path in expected:
        assert (ROOT / relative_path).exists(), relative_path


def test_sidecar_exposes_desktop_health_and_runtime_contract():
    sidecar = (ROOT / "sidecar" / "gtm_desktop_api.py").read_text()

    assert '@app.get("/desktop/health")' in sidecar
    assert '@app.get("/desktop/config")' in sidecar
    assert "requires_api_key" in sidecar
    assert "docker_required" in sidecar


def test_data_portability_document_defines_sqlite_or_duckdb_path():
    doc = (ROOT / "DATA_PORTABILITY.md").read_text()

    assert "Postgres remains the Docker verification path" in doc
    assert "SQLite" in doc or "DuckDB" in doc
    assert "dbt marts must be prebuilt" in doc
