from studio.server import project_snapshots, repository
from studio.server.db import get_pool


def test_project_snapshot_round_trip_preserves_release_lineage(client):
    with get_pool().connection() as conn:
        repository.create_workspace(conn, workspace_id="ws-snapshot", name="Snapshot Workspace")
        repository.create_project(
            conn,
            project_id="proj-snapshot",
            workspace_id="ws-snapshot",
            name="Snapshot Project",
            summary="Published showcase project.",
            domain="Revenue Operations",
            labels=["showcase"],
        )
        repository.create_requirements(
            conn,
            project_id="proj-snapshot",
            req_id="req-snapshot",
            title="Requirements",
            data={"artifact_type": "requirements", "name": "Requirements"},
        )
        repository.create_scenario(
            conn,
            project_id="proj-snapshot",
            scenario_id="scenario-snapshot",
            title="Scenario",
            data={"scenario": {"name": "Scenario"}},
        )
        repository.create_pm_artifact(
            conn,
            project_id="proj-snapshot",
            artifact_id="proj-snapshot-developer-definition-revision-1",
            title="Developer Definition Revision 1",
            data={
                "artifact_type": "developer_definition_revision",
                "compiled_contract_identity": {"contract_signature": "sha256:test"},
            },
        )
        repository.create_project_document(
            conn,
            project_id="proj-snapshot",
            document_id="source-doc",
            title="Source Doc",
            kind="product_source",
            filename="source.md",
            media_type="text/markdown",
            source_path="",
            content=b"# Source\n",
        )
        repository.create_local_publication(
            conn,
            project_id="proj-snapshot",
            publication_id="local-publication-proj-snapshot-demo-1.0.0",
            package_id="demo",
            package_version="1.0.0",
            project_ref="studio:proj-snapshot",
            product_revision_ref="prod-r1",
            developer_revision_ref="dev-r1",
            contract_signature="sha256:test",
            schema_version="anip-service-definition/v1",
            manifest_digest="sha256:manifest",
            definition_digest="sha256:definition",
            package_record={"package_id": "demo", "package_version": "1.0.0"},
            receipt={"authority": "local-studio"},
        )

        snapshot = project_snapshots.export_project_snapshot(conn, "proj-snapshot", source="test")
        repository.delete_project(conn, "proj-snapshot")
        result = project_snapshots.import_project_snapshot(conn, snapshot)

        assert result == {"project_id": "proj-snapshot", "status": "imported"}
        restored = repository.get_project(conn, "proj-snapshot")
        assert restored["name"] == "Snapshot Project"
        restored_docs = conn.execute(
            "SELECT content FROM project_documents WHERE project_id = %s AND id = %s",
            ("proj-snapshot", "source-doc"),
        ).fetchone()
        assert restored_docs["content"] == b"# Source\n"
        publications = repository.list_local_publications(conn, "proj-snapshot")
        assert publications[0]["publication"]["package_id"] == "demo"
        assert publications[0]["publication"]["contract_signature"] == "sha256:test"


def test_project_snapshot_import_can_replace_existing_project(client):
    with get_pool().connection() as conn:
        repository.create_workspace(conn, workspace_id="ws-replace", name="Replace Workspace")
        repository.create_project(
            conn,
            project_id="proj-replace",
            workspace_id="ws-replace",
            name="Original",
        )
        snapshot = project_snapshots.export_project_snapshot(conn, "proj-replace", source="test")
        snapshot["project"]["name"] = "Restored"
        result = project_snapshots.import_project_snapshot(conn, snapshot, replace_existing=True)

        assert result == {"project_id": "proj-replace", "status": "imported"}
        assert repository.get_project(conn, "proj-replace")["name"] == "Restored"


def test_committed_gtm_showcase_snapshot_imports(client):
    snapshot_path = project_snapshots._DEFAULT_SNAPSHOT_DIR / "gtm-pipeline-q2-review-0.4.1.studio-project-snapshot.json"
    snapshot = project_snapshots.load_snapshot_file(snapshot_path)

    with get_pool().connection() as conn:
        result = project_snapshots.import_project_snapshot(conn, snapshot, replace_existing=True)

        assert result == {"project_id": "965f19b5-4d1e-410b-b474-c1fb2a324e49", "status": "imported"}
        assert len(repository.list_project_documents(conn, result["project_id"])) == 14
        assert len(repository.list_pm_artifacts(conn, result["project_id"])) == 27
        publications = repository.list_local_publications(conn, result["project_id"])
        assert publications[0]["publication"]["package_id"] == "gtm-pipeline-q2-review"
        assert publications[0]["publication"]["package_version"] == "0.4.1"
        assert publications[0]["publication"]["contract_signature"] == (
            "sha256:67d0799e380801a20922f047e394d603c81822244bba6cf6ad7377ca6f83fd1d"
        )
