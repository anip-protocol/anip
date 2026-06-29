"""Tests for Studio showcase seed profile selection."""

import json

from studio.server import seed
from studio.server import project_snapshots
from studio.server.seed_catalog import SEED_PROJECTS


def _public_seed_projects() -> list[dict]:
    return [item for item in SEED_PROJECTS if seed._seed_item_enabled(item, "public_showcase")]


def test_read_only_seed_defaults_to_public_showcase(monkeypatch):
    monkeypatch.delenv("STUDIO_SEED_PROFILE", raising=False)
    monkeypatch.setenv("STUDIO_READ_ONLY", "true")

    assert seed._seed_profile() == "public_showcase"


def test_showcase_seed_defaults_to_public_showcase(monkeypatch):
    monkeypatch.delenv("STUDIO_SEED_PROFILE", raising=False)
    monkeypatch.setenv("STUDIO_READ_ONLY", "false")
    monkeypatch.setenv("STUDIO_SEED_SHOWCASES", "true")

    assert seed._seed_profile() == "public_showcase"


def test_public_showcase_catalog_is_snapshot_only():
    items = _public_seed_projects()

    assert items == []


def test_public_showcase_gtm_project_is_snapshot_backed(monkeypatch):
    monkeypatch.setenv("STUDIO_READ_ONLY", "true")

    assert seed._seed_profile() == "public_showcase"
    snapshot = project_snapshots.load_snapshot_file(
        project_snapshots._DEFAULT_SNAPSHOT_DIR / "gtm-pipeline-q2-review-0.4.5.studio-project-snapshot.json"
    )
    assert snapshot["project"]["id"]
    assert snapshot["published_packages"][0]["package_id"] == "gtm-pipeline-q2-review"
    assert snapshot["published_packages"][0]["package_version"] == "0.4.5"


def test_snapshot_showcase_profile_skips_catalog_projects():
    items = [item for item in SEED_PROJECTS if seed._seed_item_enabled(item, "showcase_snapshots")]

    assert items == []


def test_latest_snapshot_selection_keeps_newest_package_versions():
    paths = sorted(project_snapshots._DEFAULT_SNAPSHOT_DIR.glob("*.studio-project-snapshot.json"))
    selected_names = {path.name for path in project_snapshots._latest_snapshot_paths(paths)}

    assert "gtm-pipeline-q2-review-0.4.5.studio-project-snapshot.json" in selected_names
    assert "gtm-pipeline-q2-review-0.4.4.studio-project-snapshot.json" not in selected_names
    assert "gtm-pipeline-q2-review-0.4.3.studio-project-snapshot.json" not in selected_names
    assert "gtm-pipeline-q2-review-0.4.1.studio-project-snapshot.json" not in selected_names
    assert "jira-fronting-showcase-0.2.3.studio-project-snapshot.json" in selected_names
    assert "jira-fronting-showcase-0.2.1.studio-project-snapshot.json" not in selected_names
    assert "github-fronting-showcase-0.2.0.studio-project-snapshot.json" in selected_names
    assert "slack-fronting-showcase-0.2.0.studio-project-snapshot.json" in selected_names


def test_local_demo_profile_keeps_legacy_issue_tracker_showcase():
    project_ids = {
        item["project"]["id"]
        for item in SEED_PROJECTS
        if seed._seed_item_enabled(item, "local_demo")
    }

    assert project_ids == {"project-issue-tracker-fronting-showcase"}


def test_public_showcase_seed_skips_snapshot_import_when_manifest_matches(monkeypatch, tmp_path):
    manifest_path = tmp_path / "seed-manifest.json"
    expected_manifest = {
        "profile": "public_showcase",
        "snapshots": [{"name": "demo.json", "size": 10}],
    }
    manifest_path.write_text(json.dumps(expected_manifest, sort_keys=True), encoding="utf-8")
    import_calls = []

    monkeypatch.setattr(seed, "_showcase_snapshot_manifest", lambda: expected_manifest)
    monkeypatch.setattr(seed, "_seed_manifest_path", lambda: manifest_path)
    monkeypatch.setattr(
        seed,
        "import_showcase_snapshots_from_disk",
        lambda *args, **kwargs: import_calls.append(kwargs),
    )

    result = seed._seed_public_showcase_snapshots(object())

    assert import_calls == []
    assert result["status"] == "skipped_unchanged"


def test_public_showcase_seed_imports_and_records_manifest_when_manifest_changes(monkeypatch, tmp_path):
    manifest_path = tmp_path / "seed-manifest.json"
    old_manifest = {
        "profile": "public_showcase",
        "snapshots": [{"name": "old.json", "size": 1}],
    }
    new_manifest = {
        "profile": "public_showcase",
        "snapshots": [{"name": "new.json", "size": 2}],
    }
    manifest_path.write_text(json.dumps(old_manifest, sort_keys=True), encoding="utf-8")
    import_calls = []

    monkeypatch.setattr(seed, "_showcase_snapshot_manifest", lambda: new_manifest)
    monkeypatch.setattr(seed, "_seed_manifest_path", lambda: manifest_path)

    def fake_import(*args, **kwargs):
        import_calls.append(kwargs)
        return {"imported": 1, "skipped": 0, "snapshots": []}

    monkeypatch.setattr(seed, "import_showcase_snapshots_from_disk", fake_import)

    result = seed._seed_public_showcase_snapshots(object())

    assert import_calls == [
        {
            "replace_existing": True,
            "latest_only": True,
            "workspace_override": seed.PUBLIC_SHOWCASE_WORKSPACE,
        }
    ]
    assert result["status"] == "imported"
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == new_manifest
