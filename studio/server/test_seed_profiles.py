"""Tests for Studio showcase seed profile selection."""

from studio.server import seed
from studio.server import project_snapshots
from studio.server.seed_catalog import SEED_PROJECTS


def _public_seed_projects() -> list[dict]:
    return [item for item in SEED_PROJECTS if seed._seed_item_enabled(item, "public_showcase")]


def test_read_only_seed_defaults_to_public_showcase(monkeypatch):
    monkeypatch.delenv("STUDIO_SEED_PROFILE", raising=False)
    monkeypatch.setenv("STUDIO_READ_ONLY", "true")

    assert seed._seed_profile() == "public_showcase"


def test_public_showcase_catalog_is_snapshot_only():
    items = _public_seed_projects()

    assert items == []


def test_public_showcase_gtm_project_is_snapshot_backed(monkeypatch):
    monkeypatch.setenv("STUDIO_READ_ONLY", "true")

    assert seed._seed_profile() == "public_showcase"
    snapshot = project_snapshots.load_snapshot_file(
        project_snapshots._DEFAULT_SNAPSHOT_DIR / "gtm-pipeline-q2-review-0.4.3.studio-project-snapshot.json"
    )
    assert snapshot["project"]["id"]
    assert snapshot["published_packages"][0]["package_id"] == "gtm-pipeline-q2-review"
    assert snapshot["published_packages"][0]["package_version"] == "0.4.3"


def test_snapshot_showcase_profile_skips_catalog_projects():
    items = [item for item in SEED_PROJECTS if seed._seed_item_enabled(item, "showcase_snapshots")]

    assert items == []


def test_latest_snapshot_selection_keeps_newest_package_versions():
    paths = sorted(project_snapshots._DEFAULT_SNAPSHOT_DIR.glob("*.studio-project-snapshot.json"))
    selected_names = {path.name for path in project_snapshots._latest_snapshot_paths(paths)}

    assert "gtm-pipeline-q2-review-0.4.3.studio-project-snapshot.json" in selected_names
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
