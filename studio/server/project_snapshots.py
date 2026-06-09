"""Versioned Studio project snapshots for published showcase restoration.

These snapshots are intentionally separate from curated seed data.  Seed data
is useful for loose demos; a published package needs a frozen Studio project
state that can be restored exactly enough to explain where the package came
from.
"""

from __future__ import annotations

import base64
import copy
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from psycopg.types.json import Json

from . import repository

SNAPSHOT_SCHEMA_VERSION = "anip-studio-project-snapshot/v1"
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_SNAPSHOT_DIR = _REPO_ROOT / "studio" / "server" / "showcase_snapshots"


def _jsonable(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"encoding": "base64", "data": base64.b64encode(value).decode("ascii")}
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def _bytes_from_snapshot(value: Any) -> bytes:
    if isinstance(value, dict) and value.get("encoding") == "base64":
        return base64.b64decode(str(value.get("data") or ""))
    if isinstance(value, str):
        return value.encode("utf-8")
    raise ValueError("snapshot document content must be base64 encoded")


def _select_rows(conn: Any, table: str, project_column: str, project_id: str) -> list[dict[str, Any]]:
    return [
        _jsonable(dict(row))
        for row in conn.execute(
            f"SELECT * FROM {table} WHERE {project_column} = %s ORDER BY created_at ASC",
            (project_id,),
        ).fetchall()
    ]


def _project_documents(conn: Any, project_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM project_documents WHERE project_id = %s ORDER BY created_at ASC",
        (project_id,),
    ).fetchall()
    return [_jsonable(dict(row)) for row in rows]


def export_project_snapshot(
    conn: Any,
    project_id: str,
    *,
    published_packages: list[dict[str, Any]] | None = None,
    source: str = "studio",
) -> dict[str, Any]:
    """Export a complete restoreable Studio project snapshot."""

    project = repository.get_project(conn, project_id)
    workspace = repository.get_workspace(conn, project["workspace_id"])
    workspace_connections = [
        _jsonable(dict(row))
        for row in conn.execute(
            "SELECT * FROM workspace_connections WHERE workspace_id = %s ORDER BY created_at ASC",
            (project["workspace_id"],),
        ).fetchall()
    ]
    local_publications = [
        _jsonable(dict(row))
        for row in conn.execute(
            "SELECT * FROM local_publications WHERE project_id = %s ORDER BY published_at ASC, created_at ASC",
            (project_id,),
        ).fetchall()
    ]

    snapshot = {
        "snapshot_schema_version": SNAPSHOT_SCHEMA_VERSION,
        "snapshot_id": f"{project_id}@{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "exported_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": source,
        "workspace": _jsonable(dict(workspace)),
        "project": _jsonable(dict(project)),
        "workspace_connections": workspace_connections,
        "records": {
            "requirements_sets": _select_rows(conn, "requirements_sets", "project_id", project_id),
            "scenarios": _select_rows(conn, "scenarios", "project_id", project_id),
            "service_metadata_artifacts": _select_rows(conn, "service_metadata_artifacts", "project_id", project_id),
            "integration_discovery_records": _select_rows(conn, "integration_discovery_records", "project_id", project_id),
            "pm_artifacts": _select_rows(conn, "pm_artifacts", "project_id", project_id),
            "proposals": _select_rows(conn, "proposals", "project_id", project_id),
            "shapes": _select_rows(conn, "shapes", "project_id", project_id),
            "evaluations": _select_rows(conn, "evaluations", "project_id", project_id),
            "project_documents": _project_documents(conn, project_id),
            "data_access_projects": _select_rows(conn, "data_access_projects", "studio_project_id", project_id),
            "application_integration_projects": _select_rows(conn, "application_integration_projects", "studio_project_id", project_id),
            "local_publications": local_publications,
        },
        "published_packages": published_packages or _published_packages_from_local_publications(local_publications),
    }
    return snapshot


def _published_packages_from_local_publications(local_publications: list[dict[str, Any]]) -> list[dict[str, Any]]:
    packages: list[dict[str, Any]] = []
    for row in local_publications:
        package_record = row.get("package_record") or {}
        packages.append(
            {
                "package_id": row.get("package_id"),
                "package_version": row.get("package_version"),
                "registry_url": package_record.get("registry_url") or "",
                "contract_signature": row.get("contract_signature"),
                "project_ref": row.get("project_ref"),
                "product_revision_ref": row.get("product_revision_ref"),
                "developer_revision_ref": row.get("developer_revision_ref"),
            }
        )
    return packages


def _assert_snapshot(snapshot: dict[str, Any]) -> None:
    version = snapshot.get("snapshot_schema_version")
    if version != SNAPSHOT_SCHEMA_VERSION:
        raise ValueError(f"unsupported Studio snapshot schema version: {version!r}")
    if not isinstance(snapshot.get("project"), dict):
        raise ValueError("Studio snapshot must contain project")
    if not isinstance(snapshot.get("workspace"), dict):
        raise ValueError("Studio snapshot must contain workspace")
    if not isinstance(snapshot.get("records"), dict):
        raise ValueError("Studio snapshot must contain records")


def _insert_workspace(conn: Any, workspace: dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO workspaces (id, name, summary, created_at, updated_at)"
        " VALUES (%s, %s, %s, COALESCE(%s::timestamptz, now()), COALESCE(%s::timestamptz, now()))"
        " ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, summary = EXCLUDED.summary, updated_at = EXCLUDED.updated_at",
        (
            workspace["id"],
            workspace["name"],
            workspace.get("summary", ""),
            workspace.get("created_at"),
            workspace.get("updated_at"),
        ),
    )


def _insert_project(conn: Any, project: dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO projects"
        " (id, workspace_id, name, summary, domain, labels, project_type, integration_profile, created_at, updated_at)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, COALESCE(%s::timestamptz, now()), COALESCE(%s::timestamptz, now()))",
        (
            project["id"],
            project["workspace_id"],
            project["name"],
            project.get("summary", ""),
            project.get("domain", ""),
            Json(project.get("labels") or []),
            project.get("project_type") or "standard",
            Json(project.get("integration_profile") or {"kind": "none", "systems": []}),
            project.get("created_at"),
            project.get("updated_at"),
        ),
    )


def _insert_workspace_connection(conn: Any, row: dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO workspace_connections"
        " (id, workspace_id, display_name, backend_kind, system_kind, endpoint_ref, auth_mode,"
        "  identity_provider_ref, secret_ref, allowed_project_refs, metadata, created_at, updated_at)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, COALESCE(%s::timestamptz, now()), COALESCE(%s::timestamptz, now()))"
        " ON CONFLICT (id) DO UPDATE SET display_name = EXCLUDED.display_name, backend_kind = EXCLUDED.backend_kind,"
        " system_kind = EXCLUDED.system_kind, endpoint_ref = EXCLUDED.endpoint_ref, auth_mode = EXCLUDED.auth_mode,"
        " identity_provider_ref = EXCLUDED.identity_provider_ref, secret_ref = EXCLUDED.secret_ref,"
        " allowed_project_refs = EXCLUDED.allowed_project_refs, metadata = EXCLUDED.metadata, updated_at = EXCLUDED.updated_at",
        (
            row["id"],
            row["workspace_id"],
            row["display_name"],
            row["backend_kind"],
            row.get("system_kind", ""),
            row.get("endpoint_ref", ""),
            row["auth_mode"],
            row.get("identity_provider_ref", ""),
            row.get("secret_ref", ""),
            Json(row.get("allowed_project_refs") or []),
            Json(row.get("metadata") or {}),
            row.get("created_at"),
            row.get("updated_at"),
        ),
    )


def _insert_generic_artifact(conn: Any, table: str, row: dict[str, Any], *, include_role: bool = False) -> None:
    columns = ["id", "project_id", "title", "status", "data", "content_hash", "created_at", "updated_at"]
    values: list[Any] = [
        row["id"],
        row["project_id"],
        row["title"],
        row.get("status", "draft"),
        Json(row.get("data") or {}),
        row.get("content_hash", ""),
        row.get("created_at"),
        row.get("updated_at"),
    ]
    if include_role:
        columns.insert(4, "role")
        values.insert(4, row.get("role") or "alternative")
    placeholders = ["%s"] * (len(columns) - 2) + ["COALESCE(%s::timestamptz, now())", "COALESCE(%s::timestamptz, now())"]
    conn.execute(
        f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(placeholders)})",
        values,
    )


def _insert_proposal(conn: Any, row: dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO proposals"
        " (id, project_id, requirements_id, title, status, data, content_hash, created_at, updated_at)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, COALESCE(%s::timestamptz, now()), COALESCE(%s::timestamptz, now()))",
        (
            row["id"],
            row["project_id"],
            row["requirements_id"],
            row["title"],
            row.get("status", "draft"),
            Json(row.get("data") or {}),
            row.get("content_hash", ""),
            row.get("created_at"),
            row.get("updated_at"),
        ),
    )


def _insert_shape(conn: Any, row: dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO shapes"
        " (id, project_id, requirements_id, title, status, data, content_hash, created_at, updated_at)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, COALESCE(%s::timestamptz, now()), COALESCE(%s::timestamptz, now()))",
        (
            row["id"],
            row["project_id"],
            row["requirements_id"],
            row["title"],
            row.get("status", "draft"),
            Json(row.get("data") or {}),
            row.get("content_hash", ""),
            row.get("created_at"),
            row.get("updated_at"),
        ),
    )


def _insert_evaluation(conn: Any, row: dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO evaluations"
        " (id, project_id, proposal_id, scenario_id, requirements_id, result, source, data, input_snapshot,"
        "  requirements_hash, proposal_hash, scenario_hash, shape_id, shape_hash, derived_expectations, created_at)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, COALESCE(%s::timestamptz, now()))",
        (
            row["id"],
            row["project_id"],
            row.get("proposal_id"),
            row["scenario_id"],
            row["requirements_id"],
            row.get("result", "REQUIRES_GLUE"),
            row.get("source", "manual"),
            Json(row.get("data") or {}),
            Json(row.get("input_snapshot") or {}),
            row.get("requirements_hash", ""),
            row.get("proposal_hash", ""),
            row.get("scenario_hash", ""),
            row.get("shape_id"),
            row.get("shape_hash", ""),
            Json(row.get("derived_expectations")) if row.get("derived_expectations") is not None else None,
            row.get("created_at"),
        ),
    )


def _insert_project_document(conn: Any, row: dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO project_documents"
        " (id, project_id, title, kind, filename, media_type, source_path, content, content_hash, created_at, updated_at)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, COALESCE(%s::timestamptz, now()), COALESCE(%s::timestamptz, now()))",
        (
            row["id"],
            row["project_id"],
            row["title"],
            row.get("kind", "reference"),
            row["filename"],
            row.get("media_type", "application/octet-stream"),
            row.get("source_path", ""),
            _bytes_from_snapshot(row.get("content")),
            row.get("content_hash", ""),
            row.get("created_at"),
            row.get("updated_at"),
        ),
    )


def _insert_integration_discovery_record(conn: Any, row: dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO integration_discovery_records"
        " (id, project_id, connection_id, operation_id, backend_kind, method, path_template, side_effect_level,"
        "  input_schema_summary, risk_notes, data, content_hash, created_at, updated_at)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, COALESCE(%s::timestamptz, now()), COALESCE(%s::timestamptz, now()))",
        (
            row["id"],
            row["project_id"],
            row.get("connection_id"),
            row["operation_id"],
            row["backend_kind"],
            row.get("method", ""),
            row.get("path_template", ""),
            row.get("side_effect_level", "read"),
            Json(row.get("input_schema_summary") or {}),
            Json(row.get("risk_notes") or []),
            Json(row.get("data") or {}),
            row.get("content_hash", ""),
            row.get("created_at"),
            row.get("updated_at"),
        ),
    )


def _insert_saved_design_project(conn: Any, table: str, row: dict[str, Any]) -> None:
    name_column = "name" if table == "data_access_projects" else "title"
    name_value = row.get(name_column) or row["id"]
    conn.execute(
        f"INSERT INTO {table} (id, {name_column}, studio_project_id, state, created_at, updated_at)"
        " VALUES (%s, %s, %s, %s, COALESCE(%s::timestamptz, now()), COALESCE(%s::timestamptz, now()))",
        (
            row["id"],
            name_value,
            row.get("studio_project_id"),
            Json(row.get("state") or {}),
            row.get("created_at"),
            row.get("updated_at"),
        ),
    )


def _insert_local_publication(conn: Any, row: dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO local_publications"
        " (id, project_id, package_id, package_version, project_ref, product_revision_ref, developer_revision_ref,"
        "  contract_signature, schema_version, manifest_digest, definition_digest, package_record, receipt, authority, published_at, created_at)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, COALESCE(%s::timestamptz, now()), COALESCE(%s::timestamptz, now()))",
        (
            row["id"],
            row["project_id"],
            row["package_id"],
            row["package_version"],
            row["project_ref"],
            row["product_revision_ref"],
            row["developer_revision_ref"],
            row["contract_signature"],
            row["schema_version"],
            row["manifest_digest"],
            row["definition_digest"],
            Json(row.get("package_record") or {}),
            Json(row.get("receipt") or {}),
            row.get("authority") or "local-studio",
            row.get("published_at"),
            row.get("created_at"),
        ),
    )


def import_project_snapshot(conn: Any, snapshot: dict[str, Any], *, replace_existing: bool = True) -> dict[str, Any]:
    """Restore a Studio project snapshot.

    With ``replace_existing=True`` the target project is deleted first, letting
    foreign-key cascades remove project-owned records before the frozen
    snapshot is inserted.
    """

    _assert_snapshot(snapshot)
    project = snapshot["project"]
    workspace = snapshot["workspace"]
    records = snapshot["records"]

    _insert_workspace(conn, workspace)
    for connection in snapshot.get("workspace_connections") or []:
        _insert_workspace_connection(conn, connection)

    try:
        repository.get_project(conn, project["id"])
        if not replace_existing:
            return {"project_id": project["id"], "status": "skipped_existing"}
        conn.execute("DELETE FROM projects WHERE id = %s", (project["id"],))
    except repository.NotFoundError:
        pass

    _insert_project(conn, project)
    for row in records.get("requirements_sets") or []:
        _insert_generic_artifact(conn, "requirements_sets", row, include_role=True)
    for row in records.get("scenarios") or []:
        _insert_generic_artifact(conn, "scenarios", row)
    for row in records.get("service_metadata_artifacts") or []:
        _insert_generic_artifact(conn, "service_metadata_artifacts", row)
    for row in records.get("integration_discovery_records") or []:
        _insert_integration_discovery_record(conn, row)
    for row in records.get("pm_artifacts") or []:
        _insert_generic_artifact(conn, "pm_artifacts", row)
    for row in records.get("proposals") or []:
        _insert_proposal(conn, row)
    for row in records.get("shapes") or []:
        _insert_shape(conn, row)
    for row in records.get("evaluations") or []:
        _insert_evaluation(conn, row)
    for row in records.get("project_documents") or []:
        _insert_project_document(conn, row)
    for row in records.get("data_access_projects") or []:
        _insert_saved_design_project(conn, "data_access_projects", row)
    for row in records.get("application_integration_projects") or []:
        _insert_saved_design_project(conn, "application_integration_projects", row)
    for row in records.get("local_publications") or []:
        _insert_local_publication(conn, row)

    conn.commit()
    return {"project_id": project["id"], "status": "imported"}


def load_snapshot_file(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _primary_published_package(snapshot: dict[str, Any]) -> dict[str, Any]:
    packages = snapshot.get("published_packages")
    if not isinstance(packages, list):
        return {}
    for package in packages:
        if not isinstance(package, dict):
            continue
        package_id = str(package.get("package_id") or "").strip()
        package_kind = str(package.get("package_kind") or "").strip()
        if package_id and package_kind != "anip_starter_template" and not package_id.endswith("-starter"):
            return package
    for package in packages:
        if isinstance(package, dict) and str(package.get("package_id") or "").strip():
            return package
    return {}


def _version_sort_key(version: str) -> tuple[tuple[int, ...], str]:
    parts = tuple(int(part) for part in re.findall(r"\d+", version))
    return parts, version


def _latest_snapshot_paths(paths: list[Path]) -> list[Path]:
    latest: dict[str, tuple[tuple[tuple[int, ...], str], str, Path]] = {}
    passthrough: list[Path] = []
    for path in paths:
        snapshot = load_snapshot_file(path)
        package = _primary_published_package(snapshot)
        package_id = str(package.get("package_id") or "").strip()
        package_version = str(package.get("package_version") or "").strip()
        if not package_id or not package_version:
            passthrough.append(path)
            continue
        candidate = (_version_sort_key(package_version), path.name, path)
        existing = latest.get(package_id)
        if existing is None or candidate > existing:
            latest[package_id] = candidate
    return sorted([*passthrough, *(value[2] for value in latest.values())])


def import_showcase_snapshots_from_disk(
    conn: Any,
    *,
    snapshot_dir: Path | None = None,
    replace_existing: bool = True,
    latest_only: bool = False,
    workspace_override: dict[str, str] | None = None,
) -> dict[str, Any]:
    directory = snapshot_dir or _DEFAULT_SNAPSHOT_DIR
    if not directory.exists():
        return {"snapshot_dir": str(directory), "imported": 0, "skipped": 0, "snapshots": []}

    imported = 0
    skipped = 0
    results: list[dict[str, Any]] = []
    paths = sorted(directory.glob("*.studio-project-snapshot.json"))
    if latest_only:
        paths = _latest_snapshot_paths(paths)
    for path in paths:
        snapshot = load_snapshot_file(path)
        if workspace_override is not None:
            snapshot = copy.deepcopy(snapshot)
            snapshot["workspace"] = {
                **snapshot["workspace"],
                **workspace_override,
            }
            snapshot["project"]["workspace_id"] = workspace_override["id"]
            for connection in snapshot.get("workspace_connections") or []:
                connection["workspace_id"] = workspace_override["id"]
        result = import_project_snapshot(
            conn,
            snapshot,
            replace_existing=replace_existing,
        )
        result["path"] = str(path)
        results.append(result)
        if result["status"] == "imported":
            imported += 1
        else:
            skipped += 1
    return {"snapshot_dir": str(directory), "imported": imported, "skipped": skipped, "snapshots": results}
