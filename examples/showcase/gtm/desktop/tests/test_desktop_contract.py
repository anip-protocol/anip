from pathlib import Path
import re


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
    sidecar = (ROOT / "sidecar" / "gtm_desktop_entry.py").read_text()

    assert '@app.get("/desktop/health")' in sidecar
    assert "SERVICE_MODULES" in sidecar
    assert "gtm_pipeline_q2_review.app" in sidecar
    assert 'fallback = "gtm_pipeline_q2_review"' in sidecar
    assert "gtm_agent_app" in sidecar
    assert "ANIP_AGENT_SERVICES_JSON" in sidecar
    assert "CORSMiddleware" in sidecar
    assert "tauri://localhost" in sidecar
    assert "os.chdir(data_dir)" in sidecar
    assert "_ensure_key_file(data_dir)" in sidecar
    assert "SQLite/DuckDB local marts are the next desktop data-portability milestone" in sidecar


def test_sidecar_build_packages_generated_runtime_assets():
    script = (ROOT / "scripts" / "build-desktop-sidecar.sh").read_text()
    windows_workflow = (ROOT.parents[3] / ".github" / "workflows" / "publish-gtm-agent-desktop-windows.yml").read_text()
    build_requirements = (ROOT / "sidecar" / "desktop-build-requirements.txt").read_text().splitlines()
    runtime_requirements = (ROOT / "sidecar" / "requirements.txt").read_text()

    assert "generated/language-parity/python/src" in script
    assert "generated/language-parity/python/agent-consumption" in script
    assert "packages/python/anip-server/src" in script
    assert "--hidden-import gtm_pipeline_q2_review.app" in script
    assert "--hidden-import gtm_pipeline_q2_review.services.gtm_outreach_service.app" in script
    assert 'SIDECAR_FILE="${SIDECAR_NAME}.exe"' in script
    assert "gtm-agent-desktop-runtime-${TARGET_TRIPLE}.exe" in windows_workflow
    assert "-r requirements.txt" in build_requirements
    assert "uvicorn" in runtime_requirements
    assert "fastapi" in runtime_requirements
    assert "PyJWT[crypto]" in runtime_requirements
    assert "psycopg[binary]" in runtime_requirements
    assert (ROOT / "src-tauri" / "bin" / "gtm-agent-desktop-runtime-placeholder").exists()


def test_tauri_launches_runtime_sidecar():
    source = (ROOT / "src-tauri" / "src" / "lib.rs").read_text()
    config = (ROOT / "src-tauri" / "tauri.conf.json").read_text()
    boot = (ROOT / "src" / "main.ts").read_text()

    assert "gtm-agent-desktop-runtime-" in source
    assert "GTM_DESKTOP_API_PORT" in source
    assert "CREATE_NO_WINDOW" in source
    assert "LOCALAPPDATA" in source
    assert "stop_runtime_sidecar" in source
    assert "external_link_navigation_plugin" in source
    assert "open_external_url" in source
    assert "https://anip.dev/" in source
    assert "https://github.com/anip-protocol/anip/" in source
    assert "bin/gtm-agent-desktop-runtime-*" in config
    assert "gtm_agent_base_url" in boot
    assert "/desktop/health" in boot


def test_data_portability_document_defines_sqlite_or_duckdb_path():
    doc = (ROOT / "DATA_PORTABILITY.md").read_text()

    assert "Postgres remains the Docker verification path" in doc
    assert "SQLite" in doc or "DuckDB" in doc
    assert "dbt marts must be prebuilt" in doc


def test_desktop_sources_do_not_embed_llm_api_keys():
    secret_pattern = re.compile(r"sk-[A-Za-z0-9_-]{20,}")
    checked_suffixes = {".html", ".json", ".md", ".py", ".rs", ".sh", ".toml", ".ts", ".txt"}

    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in checked_suffixes:
            continue
        relative = path.relative_to(ROOT)
        assert not secret_pattern.search(path.read_text(errors="ignore")), relative
