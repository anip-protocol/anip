from pathlib import Path

from studio.server import runtime_paths


def test_repo_root_defaults_to_repository_root():
    assert (runtime_paths.repo_root() / "studio" / "server").exists()


def test_repo_root_can_be_overridden(monkeypatch, tmp_path):
    monkeypatch.setenv("ANIP_STUDIO_RUNTIME_ROOT", str(tmp_path))

    assert runtime_paths.repo_root() == tmp_path.resolve()
    assert runtime_paths.server_path("migrations") == tmp_path.resolve() / "studio" / "server" / "migrations"
    assert runtime_paths.tooling_schema_path("requirements.schema.json") == (
        tmp_path.resolve() / "tooling" / "schemas" / "requirements.schema.json"
    )
