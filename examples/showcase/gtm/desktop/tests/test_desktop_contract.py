from pathlib import Path
import re
import sqlite3


ROOT = Path(__file__).resolve().parents[1]


def test_readme_positions_desktop_as_non_docker_path():
    readme = (ROOT / "README.md").read_text()

    assert "non-Docker path" in readme
    assert "Docker Compose remains" in readme
    assert "technical verification path" in readme
    assert "prebuilt local GTM mart data" in readme
    assert "Metabase BI" in readme


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
    assert "_configure_local_data_backend(root)" in sidecar
    assert 'return "sqlite"' in sidecar
    assert '"configured": data_backend_kind != "not_configured"' in sidecar


def test_desktop_bundles_prebuilt_local_marts():
    script = (ROOT / "scripts" / "build-desktop-sidecar.sh").read_text()
    builder = (ROOT / "scripts" / "build_desktop_data.py").read_text()
    sidecar = (ROOT / "sidecar" / "gtm_desktop_entry.py").read_text()
    adapter = (
        ROOT.parents[0]
        / "generated"
        / "language-parity"
        / "python"
        / "src"
        / "gtm_pipeline_q2_review"
        / "backend_adapter.py"
    ).read_text()
    app = (ROOT.parents[0] / "agents" / "llm_runtime" / "app.py").read_text()
    entry = (ROOT.parents[0] / "agents" / "llm_runtime" / "entry.html").read_text()
    questions = (ROOT.parents[0] / "agents" / "llm_runtime" / "questions.html").read_text()
    runbook = (ROOT.parents[0] / "agents" / "llm_runtime" / "runbook.html").read_text()
    index = (ROOT.parents[0] / "agents" / "llm_runtime" / "index.html").read_text()
    metabase = (ROOT.parents[0] / "agents" / "llm_runtime" / "metabase.html").read_text()

    assert "build_desktop_data.py" in script
    assert "data/gtm_desktop.sqlite" in script
    assert "--add-data" in script
    assert "fct_gtm__opportunities" in builder
    assert "mart_gtm__account_enrichment" in builder
    assert "sqlite:///" in sidecar
    assert "sqlite3" in adapter
    assert "analytics_gtm" in adapter
    assert '"deployment_profile": deployment_profile' in app
    assert '"data_backend": data_backend' in app
    assert "@app.post(\"/api/settings/api-key\")" in app
    assert "def _current_model()" in app
    assert "def _current_base_url()" in app
    assert "settings[\"model\"] = model" in app
    assert "settings[\"base_url\"] = base_url.rstrip(\"/\")" in app
    assert "ANIP_AGENT_SETTINGS_PATH" in sidecar
    assert '"base_url": str(_settings_json().get("base_url")' in sidecar
    assert "bundled local GTM mart data" in entry
    assert "The 540-case GTM benchmark suite plus 24 hard-mode governance cases used for release validation." in entry
    assert "The 540-case GTM benchmark suite plus 24 hard-mode governance cases used for release validation." in questions
    assert "benchmarks/gtm-agent-comparison/scripts/build_gtm_benchmark_cases.py" in runbook
    assert "benchmarks/gtm-agent-comparison/cases/gtm-hard-mode.json" in runbook
    assert "gpt-5.4-mini" in index
    assert "ChatGPT subscription" in index
    assert "baseUrlInput" in index
    assert "https://api.openai.com/v1" in index
    assert "Save LLM Settings Locally" in index
    assert "Configure LLM Settings First" in index
    assert "Local Data Verification" in metabase


def test_desktop_data_builder_materializes_required_marts(tmp_path):
    import importlib.util

    module_path = ROOT / "scripts" / "build_desktop_data.py"
    spec = importlib.util.spec_from_file_location("build_desktop_data", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    output = module.build_database(tmp_path / "gtm_desktop.sqlite")
    assert output.exists()

    conn = sqlite3.connect(output)
    try:
        tables = {
            row[0]
            for row in conn.execute("select name from sqlite_master where type = 'table'")
        }
        assert "fct_gtm__opportunities" in tables
        assert "mart_gtm__account_enrichment" in tables
        q2_count = conn.execute(
            "select count(*) from fct_gtm__opportunities where engage_quarter = '2017-Q2'"
        ).fetchone()[0]
        assert q2_count > 0
        acme = conn.execute(
            "select icp_fit from mart_gtm__account_enrichment where account_name = 'Acme Corporation'"
        ).fetchone()[0]
        assert acme == "strong_fit"
    finally:
        conn.close()


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
    assert "icons/icon.icns" in config
    assert "../../../../../studio/src-tauri/icons" not in config
    assert "gtm_agent_base_url" in boot
    assert "/desktop/health" in boot
    assert "bundled GTM mart data" in boot
    assert "No Docker is required" not in boot
    assert (ROOT / "src-tauri" / "icons" / "gtm-agent-icon.svg").exists()
    assert (ROOT / "src-tauri" / "icons" / "icon.icns").exists()
    assert (ROOT / "src-tauri" / "icons" / "icon.ico").exists()


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
