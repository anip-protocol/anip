"""Thin CRUD layer over Postgres for ANIP Studio.

All SQL lives in this module.  Functions accept a psycopg connection
(obtained via ``with get_pool().connection() as conn``) and use ``%s``
parameter placeholders.  JSONB columns are written with
``psycopg.types.json.Json`` and read as plain Python dicts thanks to
``dict_row``.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from psycopg.types.json import Json

from .hashing import content_hash
from .shape_integrity import ShapeIntegrityError, validate_shape_integrity


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class NotFoundError(Exception):
    """Raised when a requested entity does not exist."""

    def __init__(self, entity: str, entity_id: str) -> None:
        self.entity = entity
        self.entity_id = entity_id
        super().__init__(f"{entity} {entity_id!r} not found")


class ReferentialIntegrityError(Exception):
    """Raised when a delete is blocked by dependent records."""

    def __init__(
        self, entity: str, entity_id: str, blocked_by: str, refs: list[str]
    ) -> None:
        self.entity = entity
        self.entity_id = entity_id
        self.blocked_by = blocked_by
        self.refs = refs
        super().__init__(
            f"Cannot delete {entity} {entity_id!r}: "
            f"referenced by {blocked_by} {refs}"
        )


class ProjectCoherenceError(Exception):
    """Raised when cross-artifact references violate project boundaries."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class LocalPublicationExistsError(Exception):
    """Raised when a Studio-local package/version already exists."""

    def __init__(self, project_id: str, package_id: str, package_version: str) -> None:
        self.project_id = project_id
        self.package_id = package_id
        self.package_version = package_version
        super().__init__(
            f"Local publication {package_id!r}@{package_version!r} already exists for project {project_id!r}"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REF_TABLE_MAP: dict[str, str] = {
    "requirements_id": "requirements_sets",
    "scenario_id": "scenarios",
    "proposal_id": "proposals",
    "shape_id": "shapes",
}


_JSON_FIELD_FALLBACKS: dict[str, Any] = {
    "allowed_project_refs": [],
    "data": {},
    "derived_expectations": None,
    "input_schema_summary": {},
    "input_snapshot": {},
    "integration_profile": {"kind": "none", "systems": []},
    "labels": [],
    "metadata": {},
    "package_record": {},
    "receipt": {},
    "risk_notes": [],
    "state": {},
    "tags": [],
}


def _json_value(value: Any, fallback: Any) -> Any:
    if value is None:
        return deepcopy(fallback)
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return deepcopy(fallback)
    return deepcopy(fallback)


def _plain_row(row: Any) -> dict | None:
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    return dict(row)


def _decode_json_fields(row: Any) -> dict | None:
    decoded = _plain_row(row)
    if decoded is None:
        return None
    for field, fallback in _JSON_FIELD_FALLBACKS.items():
        if field in decoded:
            decoded[field] = _json_value(decoded[field], fallback)
    return decoded


def _decode_json_rows(rows: list[Any]) -> list[dict]:
    return [_decode_json_fields(row) for row in rows]


def _decode_studio_settings_fields(row: Any) -> dict | None:
    decoded = _plain_row(row)
    if decoded is None:
        return None
    if "value" in decoded:
        decoded["value"] = _json_value(decoded["value"], {})
    return decoded


def assert_same_project(conn: Any, project_id: str, **refs: str) -> None:
    """Verify that every referenced record belongs to *project_id*.

    Accepts keyword arguments like ``requirements_id="req-1"``.  Looks up
    each record's ``project_id`` and raises ``ProjectCoherenceError`` if it
    does not match.
    """
    for ref_name, ref_id in refs.items():
        table = _REF_TABLE_MAP.get(ref_name)
        if table is None:
            raise ValueError(f"Unknown reference: {ref_name}")
        row = conn.execute(
            f"SELECT project_id FROM {table} WHERE id = %s", (ref_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(table, ref_id)
        if row["project_id"] != project_id:
            raise ProjectCoherenceError(
                f"{ref_name} {ref_id!r} belongs to project "
                f"{row['project_id']!r}, not {project_id!r}"
            )


# ---------------------------------------------------------------------------
# Workspaces
# ---------------------------------------------------------------------------

def list_workspaces(conn: Any) -> list[dict]:
    return _decode_json_rows(conn.execute(
        "SELECT w.*, "
        "  (SELECT count(*) FROM projects WHERE workspace_id = w.id) AS projects_count "
        "FROM workspaces w ORDER BY updated_at DESC, name ASC"
    ).fetchall())


def get_workspace(conn: Any, workspace_id: str) -> dict:
    row = conn.execute(
        "SELECT w.*, "
        "  (SELECT count(*) FROM projects WHERE workspace_id = w.id) AS projects_count "
        "FROM workspaces w WHERE id = %s",
        (workspace_id,),
    ).fetchone()
    if row is None:
        raise NotFoundError("workspace", workspace_id)
    return _decode_json_fields(row)


def get_default_workspace_id(conn: Any) -> str:
    row = conn.execute(
        "SELECT id FROM workspaces ORDER BY created_at ASC LIMIT 1"
    ).fetchone()
    if row is None:
        row = conn.execute(
            "INSERT INTO workspaces (id, name, summary) VALUES (%s, %s, %s) RETURNING id",
            ("default", "Default Workspace", "Default Studio workspace"),
        ).fetchone()
        conn.commit()
    return row["id"]


def create_workspace(conn: Any, workspace_id: str, name: str, summary: str = "") -> dict:
    row = conn.execute(
        "INSERT INTO workspaces (id, name, summary) VALUES (%s, %s, %s) RETURNING *, 0 AS projects_count",
        (workspace_id, name, summary),
    ).fetchone()
    conn.commit()
    return _decode_json_fields(row)


def update_workspace(conn: Any, workspace_id: str, **fields: Any) -> dict:
    allowed = {"name", "summary"}
    sets: list[str] = []
    params: list[Any] = []
    for key, value in fields.items():
        if key not in allowed or value is None:
            continue
        sets.append(f"{key} = %s")
        params.append(value)
    if not sets:
        return get_workspace(conn, workspace_id)
    sets.append("updated_at = now()")
    params.append(workspace_id)
    row = conn.execute(
        f"UPDATE workspaces SET {', '.join(sets)} WHERE id = %s RETURNING *",
        params,
    ).fetchone()
    if row is None:
        raise NotFoundError("workspace", workspace_id)
    conn.commit()
    return get_workspace(conn, workspace_id)


def delete_workspace(conn: Any, workspace_id: str) -> None:
    cur = conn.execute("DELETE FROM workspaces WHERE id = %s", (workspace_id,))
    if cur.rowcount == 0:
        raise NotFoundError("workspace", workspace_id)
    conn.commit()


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

def list_projects(conn: Any, workspace_id: str | None = None) -> list[dict]:
    if workspace_id is None:
        return _decode_json_rows(conn.execute(
            "SELECT * FROM projects ORDER BY updated_at DESC"
        ).fetchall())
    return _decode_json_rows(conn.execute(
        "SELECT * FROM projects WHERE workspace_id = %s ORDER BY updated_at DESC",
        (workspace_id,),
    ).fetchall())


def get_project(conn: Any, project_id: str) -> dict:
    row = conn.execute(
        "SELECT * FROM projects WHERE id = %s", (project_id,)
    ).fetchone()
    if row is None:
        raise NotFoundError("project", project_id)
    return _decode_json_fields(row)


def get_project_detail(conn: Any, project_id: str) -> dict:
    row = conn.execute(
        "SELECT p.*,"
        "  (SELECT count(*) FROM requirements_sets WHERE project_id = p.id) AS requirements_count,"
        "  (SELECT count(*) FROM scenarios WHERE project_id = p.id) AS scenarios_count,"
        "  (SELECT count(*) FROM proposals WHERE project_id = p.id) AS proposals_count,"
        "  (SELECT count(*) FROM evaluations WHERE project_id = p.id) AS evaluations_count,"
        "  (SELECT count(*) FROM shapes WHERE project_id = p.id) AS shapes_count,"
        "  (SELECT count(*) FROM project_documents WHERE project_id = p.id) AS documents_count,"
        "  (SELECT count(*) FROM pm_artifacts WHERE project_id = p.id) AS pm_artifacts_count"
        " FROM projects p WHERE p.id = %s",
        (project_id,),
    ).fetchone()
    if row is None:
        raise NotFoundError("project", project_id)
    return _decode_json_fields(row)


def create_project(conn: Any, project_id: str, name: str, summary: str = "",
                   domain: str = "", labels: list | None = None,
                   workspace_id: str | None = None,
                   project_type: str = "standard",
                   integration_profile: dict[str, Any] | None = None) -> dict:
    labels = labels if labels is not None else []
    integration_profile = integration_profile or {"kind": "none", "systems": []}
    workspace_id = workspace_id or get_default_workspace_id(conn)
    get_workspace(conn, workspace_id)
    row = conn.execute(
        "INSERT INTO projects (id, workspace_id, name, summary, domain, labels, project_type, integration_profile)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING *",
        (project_id, workspace_id, name, summary, domain, Json(labels), project_type, Json(integration_profile)),
    ).fetchone()
    conn.commit()
    return _decode_json_fields(row)


def update_project(conn: Any, project_id: str, **fields: Any) -> dict:
    # Build SET clause from provided fields
    allowed = {"name", "summary", "domain", "labels", "project_type", "integration_profile"}
    sets: list[str] = []
    params: list[Any] = []
    for key, value in fields.items():
        if key not in allowed or value is None:
            continue
        if key in {"labels", "integration_profile"}:
            sets.append(f"{key} = %s")
            params.append(Json(value))
        else:
            sets.append(f"{key} = %s")
            params.append(value)
    if not sets:
        return get_project(conn, project_id)
    sets.append("updated_at = now()")
    params.append(project_id)
    row = conn.execute(
        f"UPDATE projects SET {', '.join(sets)} WHERE id = %s RETURNING *",
        params,
    ).fetchone()
    if row is None:
        raise NotFoundError("project", project_id)
    conn.commit()
    return _decode_json_fields(row)


def delete_project(conn: Any, project_id: str) -> None:
    cur = conn.execute("DELETE FROM projects WHERE id = %s", (project_id,))
    if cur.rowcount == 0:
        raise NotFoundError("project", project_id)
    conn.commit()


def _generated_clone_id(prefix: str) -> str:
    if prefix == "project":
        return str(uuid4())
    return f"{prefix}-{uuid4()}"


def _remap_nested_ids(value: Any, id_map: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {key: _remap_nested_ids(item, id_map) for key, item in value.items()}
    if isinstance(value, list):
        return [_remap_nested_ids(item, id_map) for item in value]
    if isinstance(value, str):
        if value in id_map:
            return id_map[value]
        remapped = value
        # Some artifact references embed IDs inside stable target strings, for
        # example developer_definition.scenario_formalization:<scenario_id>:...
        # Those must move with the cloned artifacts or automatic coverage
        # recomputation will point back to the source project.
        for old_id, new_id in sorted(id_map.items(), key=lambda item: len(item[0]), reverse=True):
            if old_id in remapped:
                remapped = remapped.replace(old_id, new_id)
        return remapped
    return value


def _clone_generic_artifact_rows(
    conn: Any,
    *,
    table: str,
    source_project_id: str,
    target_project_id: str,
    id_map: dict[str, str],
    include_role: bool = False,
) -> dict[str, str]:
    rows = _decode_json_rows(conn.execute(
        f"SELECT * FROM {table} WHERE project_id = %s ORDER BY created_at ASC",
        (source_project_id,),
    ).fetchall())
    content_hash_map: dict[str, str] = {}
    for row in rows:
        old_id = row["id"]
        new_id = id_map.setdefault(old_id, _generated_clone_id(table.rstrip("s")))
        data = _remap_nested_ids(row["data"], id_map)
        columns = ["id", "project_id", "title", "status", "data", "content_hash"]
        values: list[Any] = [
            new_id,
            target_project_id,
            row["title"],
            row["status"],
            Json(data),
            content_hash(data),
        ]
        if include_role:
            columns.append("role")
            values.append(row.get("role") or "alternative")
        conn.execute(
            f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(['%s'] * len(columns))})",
            values,
        )
        content_hash_map[old_id] = values[5]
    return content_hash_map


def _clone_project_into(
    conn: Any,
    *,
    source_project_id: str,
    target_project_id: str,
    target_workspace_id: str,
    target_name: str,
    target_summary: str,
) -> dict:
    source_project = get_project(conn, source_project_id)
    get_workspace(conn, target_workspace_id)
    conn.execute(
        "INSERT INTO projects (id, workspace_id, name, summary, domain, labels, project_type, integration_profile)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (
            target_project_id,
            target_workspace_id,
            target_name,
            target_summary,
            source_project["domain"],
            Json(source_project["labels"]),
            source_project.get("project_type") or "standard",
            Json(source_project.get("integration_profile") or {"kind": "none", "systems": []}),
        ),
    )

    id_map: dict[str, str] = {
        source_project_id: target_project_id,
    }
    preallocate_tables = [
        ("requirements_sets", "requirement"),
        ("scenarios", "scenario"),
        ("service_metadata_artifacts", "service-metadata"),
        ("integration_discovery_records", "integration-discovery"),
        ("pm_artifacts", "pm-artifact"),
        ("proposals", "proposal"),
        ("shapes", "shape"),
        ("evaluations", "evaluation"),
        ("project_documents", "document"),
    ]
    for table, prefix in preallocate_tables:
        rows = conn.execute(
            f"SELECT id FROM {table} WHERE project_id = %s",
            (source_project_id,),
        ).fetchall()
        for row in rows:
            id_map.setdefault(row["id"], _generated_clone_id(prefix))
    for table, prefix in [
        ("data_access_projects", "data-access"),
        ("application_integration_projects", "app-int"),
    ]:
        rows = conn.execute(
            f"SELECT id FROM {table} WHERE studio_project_id = %s",
            (source_project_id,),
        ).fetchall()
        for row in rows:
            id_map.setdefault(row["id"], _generated_clone_id(prefix))

    requirements_hash_map = _clone_generic_artifact_rows(
        conn,
        table="requirements_sets",
        source_project_id=source_project_id,
        target_project_id=target_project_id,
        id_map=id_map,
        include_role=True,
    )
    scenario_hash_by_old_id = _clone_generic_artifact_rows(
        conn,
        table="scenarios",
        source_project_id=source_project_id,
        target_project_id=target_project_id,
        id_map=id_map,
    )
    _clone_generic_artifact_rows(
        conn,
        table="service_metadata_artifacts",
        source_project_id=source_project_id,
        target_project_id=target_project_id,
        id_map=id_map,
    )
    discovery_rows = _decode_json_rows(conn.execute(
        "SELECT * FROM integration_discovery_records WHERE project_id = %s ORDER BY created_at ASC",
        (source_project_id,),
    ).fetchall())
    for row in discovery_rows:
        old_id = row["id"]
        new_id = id_map.setdefault(old_id, _generated_clone_id("integration-discovery"))
        data = _remap_nested_ids(row["data"], id_map)
        record_payload = {
            "connection_id": row.get("connection_id"),
            "operation_id": row["operation_id"],
            "backend_kind": row["backend_kind"],
            "method": row["method"],
            "path_template": row["path_template"],
            "side_effect_level": row["side_effect_level"],
            "input_schema_summary": row["input_schema_summary"],
            "risk_notes": row["risk_notes"],
            "data": data,
        }
        conn.execute(
            "INSERT INTO integration_discovery_records"
            " (id, project_id, connection_id, operation_id, backend_kind, method, path_template,"
            "  side_effect_level, input_schema_summary, risk_notes, data, content_hash)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                new_id,
                target_project_id,
                row.get("connection_id"),
                row["operation_id"],
                row["backend_kind"],
                row["method"],
                row["path_template"],
                row["side_effect_level"],
                Json(row["input_schema_summary"]),
                Json(row["risk_notes"]),
                Json(data),
                content_hash(record_payload),
            ),
        )
    _clone_generic_artifact_rows(
        conn,
        table="pm_artifacts",
        source_project_id=source_project_id,
        target_project_id=target_project_id,
        id_map=id_map,
    )

    proposal_hash_map: dict[str, str] = {}
    proposal_rows = _decode_json_rows(conn.execute(
        "SELECT * FROM proposals WHERE project_id = %s ORDER BY created_at ASC",
        (source_project_id,),
    ).fetchall())
    for row in proposal_rows:
        old_id = row["id"]
        new_id = id_map.setdefault(old_id, _generated_clone_id("proposal"))
        data = _remap_nested_ids(row["data"], id_map)
        new_requirements_id = id_map[row["requirements_id"]]
        hash_value = content_hash(data)
        conn.execute(
            "INSERT INTO proposals (id, project_id, requirements_id, title, status, data, content_hash)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (
                new_id,
                target_project_id,
                new_requirements_id,
                row["title"],
                row["status"],
                Json(data),
                hash_value,
            ),
        )
        proposal_hash_map[old_id] = hash_value

    shape_hash_map: dict[str, str] = {}
    shape_rows = _decode_json_rows(conn.execute(
        "SELECT * FROM shapes WHERE project_id = %s ORDER BY created_at ASC",
        (source_project_id,),
    ).fetchall())
    for row in shape_rows:
        old_id = row["id"]
        new_id = id_map.setdefault(old_id, _generated_clone_id("shape"))
        data = _remap_nested_ids(row["data"], id_map)
        new_requirements_id = id_map[row["requirements_id"]]
        hash_value = content_hash(data)
        conn.execute(
            "INSERT INTO shapes (id, project_id, requirements_id, title, status, data, content_hash)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (
                new_id,
                target_project_id,
                new_requirements_id,
                row["title"],
                row["status"],
                Json(data),
                hash_value,
            ),
        )
        shape_hash_map[old_id] = hash_value

    evaluation_rows = _decode_json_rows(conn.execute(
        "SELECT * FROM evaluations WHERE project_id = %s ORDER BY created_at ASC",
        (source_project_id,),
    ).fetchall())
    for row in evaluation_rows:
        old_id = row["id"]
        new_id = id_map.setdefault(old_id, _generated_clone_id("evaluation"))
        evaluation_data = _remap_nested_ids(row["data"], id_map)
        input_snapshot = _remap_nested_ids(row["input_snapshot"], id_map)
        derived_expectations = _remap_nested_ids(row.get("derived_expectations"), id_map)
        old_proposal_id = row.get("proposal_id")
        old_shape_id = row.get("shape_id")
        old_scenario_id = row["scenario_id"]
        conn.execute(
            "INSERT INTO evaluations"
            " (id, project_id, proposal_id, scenario_id, requirements_id, result, source, data, input_snapshot,"
            "  requirements_hash, proposal_hash, scenario_hash, shape_id, shape_hash, derived_expectations)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                new_id,
                target_project_id,
                id_map.get(old_proposal_id) if old_proposal_id else None,
                id_map[old_scenario_id],
                id_map[row["requirements_id"]],
                row["result"],
                row["source"],
                Json(evaluation_data),
                Json(input_snapshot),
                requirements_hash_map.get(row["requirements_id"], row["requirements_hash"]),
                proposal_hash_map.get(old_proposal_id, row["proposal_hash"]) if old_proposal_id else "",
                scenario_hash_by_old_id.get(old_scenario_id, row["scenario_hash"]),
                id_map.get(old_shape_id) if old_shape_id else None,
                shape_hash_map.get(old_shape_id, row["shape_hash"]) if old_shape_id else "",
                Json(derived_expectations) if derived_expectations is not None else None,
            ),
        )

    document_rows = conn.execute(
        "SELECT * FROM project_documents WHERE project_id = %s ORDER BY created_at ASC",
        (source_project_id,),
    ).fetchall()
    for row in document_rows:
        old_id = row["id"]
        new_id = id_map.setdefault(old_id, _generated_clone_id("document"))
        conn.execute(
            "INSERT INTO project_documents"
            " (id, project_id, title, kind, filename, media_type, source_path, content, content_hash)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                new_id,
                target_project_id,
                row["title"],
                row["kind"],
                row["filename"],
                row["media_type"],
                row["source_path"],
                row["content"],
                row["content_hash"],
            ),
        )

    data_access_rows = _decode_json_rows(conn.execute(
        "SELECT * FROM data_access_projects WHERE studio_project_id = %s ORDER BY created_at ASC",
        (source_project_id,),
    ).fetchall())
    for row in data_access_rows:
        old_id = row["id"]
        new_id = id_map.setdefault(old_id, _generated_clone_id("data-access"))
        state = _remap_nested_ids(row["state"], id_map)
        conn.execute(
            "INSERT INTO data_access_projects (id, name, studio_project_id, state)"
            " VALUES (%s, %s, %s, %s)",
            (new_id, row["name"], target_project_id, Json(state)),
        )

    integration_rows = _decode_json_rows(conn.execute(
        "SELECT * FROM application_integration_projects WHERE studio_project_id = %s ORDER BY created_at ASC",
        (source_project_id,),
    ).fetchall())
    for row in integration_rows:
        old_id = row["id"]
        new_id = id_map.setdefault(old_id, _generated_clone_id("app-int"))
        state = _remap_nested_ids(row["state"], id_map)
        conn.execute(
            "INSERT INTO application_integration_projects (id, title, studio_project_id, state)"
            " VALUES (%s, %s, %s, %s)",
            (new_id, row["title"], target_project_id, Json(state)),
        )

    return get_project(conn, target_project_id)


def clone_project(
    conn: Any,
    source_project_id: str,
    *,
    target_project_id: str | None = None,
    target_workspace_id: str | None = None,
    name: str | None = None,
    summary: str | None = None,
) -> dict:
    source_project = get_project(conn, source_project_id)
    cloned = _clone_project_into(
        conn,
        source_project_id=source_project_id,
        target_project_id=target_project_id or _generated_clone_id("project"),
        target_workspace_id=target_workspace_id or source_project["workspace_id"],
        target_name=name or f"{source_project['name']} Copy",
        target_summary=source_project["summary"] if summary is None else summary,
    )
    conn.commit()
    return cloned


def clone_workspace(
    conn: Any,
    source_workspace_id: str,
    *,
    target_workspace_id: str | None = None,
    name: str | None = None,
    summary: str | None = None,
) -> dict:
    source_workspace = get_workspace(conn, source_workspace_id)
    new_workspace_id = target_workspace_id or _generated_clone_id("workspace")
    conn.execute(
        "INSERT INTO workspaces (id, name, summary) VALUES (%s, %s, %s)",
        (
            new_workspace_id,
            name or f"{source_workspace['name']} Copy",
            source_workspace["summary"] if summary is None else summary,
        ),
    )
    projects = list_projects(conn, workspace_id=source_workspace_id)
    for project in projects:
        _clone_project_into(
            conn,
            source_project_id=project["id"],
            target_project_id=_generated_clone_id("project"),
            target_workspace_id=new_workspace_id,
            target_name=project["name"],
            target_summary=project["summary"],
        )
    conn.commit()
    return get_workspace(conn, new_workspace_id)


# ---------------------------------------------------------------------------
# Project Documents
# ---------------------------------------------------------------------------

def list_project_documents(conn: Any, project_id: str) -> list[dict]:
    get_project(conn, project_id)
    return conn.execute(
        "SELECT id, project_id, title, kind, filename, media_type, source_path, content_hash, created_at, updated_at "
        "FROM project_documents WHERE project_id = %s ORDER BY updated_at DESC, created_at DESC",
        (project_id,),
    ).fetchall()


def get_project_document(conn: Any, project_id: str, document_id: str) -> dict:
    row = conn.execute(
        "SELECT * FROM project_documents WHERE project_id = %s AND id = %s",
        (project_id, document_id),
    ).fetchone()
    if row is None:
        raise NotFoundError("project_document", document_id)
    return _decode_json_fields(row)


def create_project_document(
    conn: Any,
    *,
    project_id: str,
    document_id: str,
    title: str,
    kind: str,
    filename: str,
    media_type: str,
    source_path: str,
    content: bytes,
) -> dict:
    get_project(conn, project_id)
    digest = hashlib.sha256(content).hexdigest()
    row = conn.execute(
        "INSERT INTO project_documents "
        "(id, project_id, title, kind, filename, media_type, source_path, content, content_hash) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
        "RETURNING id, project_id, title, kind, filename, media_type, source_path, content_hash, created_at, updated_at",
        (document_id, project_id, title, kind, filename, media_type, source_path, content, digest),
    ).fetchone()
    conn.commit()
    return _decode_json_fields(row)


def delete_project_document(conn: Any, project_id: str, document_id: str) -> None:
    cur = conn.execute(
        "DELETE FROM project_documents WHERE project_id = %s AND id = %s",
        (project_id, document_id),
    )
    if cur.rowcount == 0:
        raise NotFoundError("project_document", document_id)
    conn.commit()


# ---------------------------------------------------------------------------
# Integration Fronting Foundation
# ---------------------------------------------------------------------------

def list_workspace_connections(conn: Any, workspace_id: str) -> list[dict]:
    get_workspace(conn, workspace_id)
    return _decode_json_rows(conn.execute(
        "SELECT * FROM workspace_connections WHERE workspace_id = %s ORDER BY updated_at DESC, created_at DESC",
        (workspace_id,),
    ).fetchall())


def get_workspace_connection(conn: Any, workspace_id: str, connection_id: str) -> dict:
    row = conn.execute(
        "SELECT * FROM workspace_connections WHERE workspace_id = %s AND id = %s",
        (workspace_id, connection_id),
    ).fetchone()
    if row is None:
        raise NotFoundError("workspace_connection", connection_id)
    return _decode_json_fields(row)


def create_workspace_connection(
    conn: Any,
    *,
    workspace_id: str,
    connection_id: str,
    display_name: str,
    backend_kind: str,
    system_kind: str = "",
    endpoint_ref: str = "",
    auth_mode: str,
    identity_provider_ref: str = "",
    secret_ref: str = "",
    allowed_project_refs: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict:
    get_workspace(conn, workspace_id)
    allowed_project_refs = allowed_project_refs or []
    metadata = metadata or {}
    row = conn.execute(
        "INSERT INTO workspace_connections"
        " (id, workspace_id, display_name, backend_kind, system_kind, endpoint_ref, auth_mode,"
        "  identity_provider_ref, secret_ref, allowed_project_refs, metadata)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *",
        (
            connection_id,
            workspace_id,
            display_name,
            backend_kind,
            system_kind,
            endpoint_ref,
            auth_mode,
            identity_provider_ref,
            secret_ref,
            Json(allowed_project_refs),
            Json(metadata),
        ),
    ).fetchone()
    conn.commit()
    return _decode_json_fields(row)


def update_workspace_connection(
    conn: Any,
    workspace_id: str,
    connection_id: str,
    **fields: Any,
) -> dict:
    allowed = {
        "display_name",
        "backend_kind",
        "system_kind",
        "endpoint_ref",
        "auth_mode",
        "identity_provider_ref",
        "secret_ref",
        "allowed_project_refs",
        "metadata",
    }
    sets: list[str] = []
    params: list[Any] = []
    for key, value in fields.items():
        if key not in allowed or value is None:
            continue
        if key in {"allowed_project_refs", "metadata"}:
            sets.append(f"{key} = %s")
            params.append(Json(value))
        else:
            sets.append(f"{key} = %s")
            params.append(value)
    if not sets:
        return get_workspace_connection(conn, workspace_id, connection_id)
    sets.append("updated_at = now()")
    params.extend([workspace_id, connection_id])
    row = conn.execute(
        f"UPDATE workspace_connections SET {', '.join(sets)} WHERE workspace_id = %s AND id = %s RETURNING *",
        params,
    ).fetchone()
    if row is None:
        raise NotFoundError("workspace_connection", connection_id)
    conn.commit()
    return _decode_json_fields(row)


def delete_workspace_connection(conn: Any, workspace_id: str, connection_id: str) -> None:
    cur = conn.execute(
        "DELETE FROM workspace_connections WHERE workspace_id = %s AND id = %s",
        (workspace_id, connection_id),
    )
    if cur.rowcount == 0:
        raise NotFoundError("workspace_connection", connection_id)
    conn.commit()


def _assert_connection_available_for_project(conn: Any, project: dict, connection_id: str | None) -> None:
    if not connection_id:
        return
    connection = get_workspace_connection(conn, project["workspace_id"], connection_id)
    allowed_refs = connection.get("allowed_project_refs") or []
    if allowed_refs and project["id"] not in allowed_refs:
        raise ProjectCoherenceError(
            f"workspace_connection {connection_id!r} is not allowed for project {project['id']!r}"
        )


def _discovery_record_hash(payload: dict[str, Any]) -> str:
    return content_hash(payload)


def list_integration_discovery_records(conn: Any, project_id: str) -> list[dict]:
    get_project(conn, project_id)
    return _decode_json_rows(conn.execute(
        "SELECT * FROM integration_discovery_records WHERE project_id = %s ORDER BY updated_at DESC, created_at DESC",
        (project_id,),
    ).fetchall())


def get_integration_discovery_record(conn: Any, project_id: str, record_id: str) -> dict:
    row = conn.execute(
        "SELECT * FROM integration_discovery_records WHERE project_id = %s AND id = %s",
        (project_id, record_id),
    ).fetchone()
    if row is None:
        raise NotFoundError("integration_discovery_record", record_id)
    return _decode_json_fields(row)


def create_integration_discovery_record(
    conn: Any,
    *,
    project_id: str,
    record_id: str,
    connection_id: str | None = None,
    operation_id: str,
    backend_kind: str,
    method: str = "",
    path_template: str = "",
    side_effect_level: str = "read",
    input_schema_summary: dict[str, Any] | None = None,
    risk_notes: list[str] | None = None,
    data: dict[str, Any] | None = None,
) -> dict:
    project = get_project(conn, project_id)
    _assert_connection_available_for_project(conn, project, connection_id)
    input_schema_summary = input_schema_summary or {}
    risk_notes = risk_notes or []
    data = data or {}
    payload = {
        "connection_id": connection_id,
        "operation_id": operation_id,
        "backend_kind": backend_kind,
        "method": method,
        "path_template": path_template,
        "side_effect_level": side_effect_level,
        "input_schema_summary": input_schema_summary,
        "risk_notes": risk_notes,
        "data": data,
    }
    row = conn.execute(
        "INSERT INTO integration_discovery_records"
        " (id, project_id, connection_id, operation_id, backend_kind, method, path_template,"
        "  side_effect_level, input_schema_summary, risk_notes, data, content_hash)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *",
        (
            record_id,
            project_id,
            connection_id,
            operation_id,
            backend_kind,
            method,
            path_template,
            side_effect_level,
            Json(input_schema_summary),
            Json(risk_notes),
            Json(data),
            _discovery_record_hash(payload),
        ),
    ).fetchone()
    conn.commit()
    return _decode_json_fields(row)


def update_integration_discovery_record(
    conn: Any,
    project_id: str,
    record_id: str,
    **fields: Any,
) -> dict:
    existing = get_integration_discovery_record(conn, project_id, record_id)
    project = get_project(conn, project_id)
    next_payload = {
        "connection_id": existing.get("connection_id"),
        "operation_id": existing["operation_id"],
        "backend_kind": existing["backend_kind"],
        "method": existing["method"],
        "path_template": existing["path_template"],
        "side_effect_level": existing["side_effect_level"],
        "input_schema_summary": existing["input_schema_summary"],
        "risk_notes": existing["risk_notes"],
        "data": existing["data"],
    }
    for key, value in fields.items():
        if value is not None and key in next_payload:
            next_payload[key] = value
    _assert_connection_available_for_project(conn, project, next_payload.get("connection_id"))
    row = conn.execute(
        "UPDATE integration_discovery_records"
        " SET connection_id = %s, operation_id = %s, backend_kind = %s, method = %s, path_template = %s,"
        " side_effect_level = %s, input_schema_summary = %s, risk_notes = %s, data = %s,"
        " content_hash = %s, updated_at = now()"
        " WHERE project_id = %s AND id = %s RETURNING *",
        (
            next_payload["connection_id"],
            next_payload["operation_id"],
            next_payload["backend_kind"],
            next_payload["method"],
            next_payload["path_template"],
            next_payload["side_effect_level"],
            Json(next_payload["input_schema_summary"]),
            Json(next_payload["risk_notes"]),
            Json(next_payload["data"]),
            _discovery_record_hash(next_payload),
            project_id,
            record_id,
        ),
    ).fetchone()
    if row is None:
        raise NotFoundError("integration_discovery_record", record_id)
    conn.commit()
    return _decode_json_fields(row)


def delete_integration_discovery_record(conn: Any, project_id: str, record_id: str) -> None:
    cur = conn.execute(
        "DELETE FROM integration_discovery_records WHERE project_id = %s AND id = %s",
        (project_id, record_id),
    )
    if cur.rowcount == 0:
        raise NotFoundError("integration_discovery_record", record_id)
    conn.commit()


# ---------------------------------------------------------------------------
# Data Access Projects
# ---------------------------------------------------------------------------

def list_data_access_projects(conn: Any, studio_project_id: str | None = None) -> list[dict]:
    if studio_project_id:
        return conn.execute(
            "SELECT id, name, studio_project_id, created_at, updated_at FROM data_access_projects"
            " WHERE studio_project_id = %s ORDER BY updated_at DESC",
            (studio_project_id,),
        ).fetchall()
    return conn.execute(
        "SELECT id, name, studio_project_id, created_at, updated_at FROM data_access_projects ORDER BY updated_at DESC"
    ).fetchall()


def get_data_access_project(conn: Any, project_id: str) -> dict:
    row = conn.execute(
        "SELECT * FROM data_access_projects WHERE id = %s",
        (project_id,),
    ).fetchone()
    if row is None:
        raise NotFoundError("data_access_project", project_id)
    return _decode_json_fields(row)


def create_data_access_project(
    conn: Any,
    project_id: str,
    state: dict[str, Any],
    *,
    studio_project_id: str | None = None,
) -> dict:
    name = str(state.get("name") or project_id)
    if studio_project_id:
        get_project(conn, studio_project_id)
    row = conn.execute(
        "INSERT INTO data_access_projects (id, name, studio_project_id, state) VALUES (%s, %s, %s, %s) RETURNING *",
        (project_id, name, studio_project_id, Json(state)),
    ).fetchone()
    conn.commit()
    return _decode_json_fields(row)


def update_data_access_project(
    conn: Any,
    project_id: str,
    state: dict[str, Any],
    *,
    studio_project_id: str | None = None,
) -> dict:
    name = str(state.get("name") or project_id)
    if studio_project_id:
        get_project(conn, studio_project_id)
    row = conn.execute(
        "UPDATE data_access_projects"
        " SET name = %s, studio_project_id = COALESCE(%s, studio_project_id), state = %s, updated_at = now()"
        " WHERE id = %s RETURNING *",
        (name, studio_project_id, Json(state), project_id),
    ).fetchone()
    if row is None:
        raise NotFoundError("data_access_project", project_id)
    conn.commit()
    return _decode_json_fields(row)


def delete_data_access_project(conn: Any, project_id: str) -> None:
    cur = conn.execute(
        "DELETE FROM data_access_projects WHERE id = %s",
        (project_id,),
    )
    if cur.rowcount == 0:
        raise NotFoundError("data_access_project", project_id)
    conn.commit()


# ---------------------------------------------------------------------------
# Application Integration Projects
# ---------------------------------------------------------------------------

def list_application_integration_projects(conn: Any, studio_project_id: str | None = None) -> list[dict]:
    if studio_project_id:
        return conn.execute(
            "SELECT id, title, studio_project_id, created_at, updated_at FROM application_integration_projects"
            " WHERE studio_project_id = %s ORDER BY updated_at DESC",
            (studio_project_id,),
        ).fetchall()
    return conn.execute(
        "SELECT id, title, studio_project_id, created_at, updated_at FROM application_integration_projects ORDER BY updated_at DESC"
    ).fetchall()


def get_application_integration_project(conn: Any, project_id: str) -> dict:
    row = conn.execute(
        "SELECT * FROM application_integration_projects WHERE id = %s",
        (project_id,),
    ).fetchone()
    if row is None:
        raise NotFoundError("application_integration_project", project_id)
    return _decode_json_fields(row)


def create_application_integration_project(
    conn: Any,
    project_id: str,
    state: dict[str, Any],
    *,
    studio_project_id: str | None = None,
) -> dict:
    title = str(state.get("title") or project_id)
    if studio_project_id:
        get_project(conn, studio_project_id)
    row = conn.execute(
        "INSERT INTO application_integration_projects (id, title, studio_project_id, state) VALUES (%s, %s, %s, %s) RETURNING *",
        (project_id, title, studio_project_id, Json(state)),
    ).fetchone()
    conn.commit()
    return _decode_json_fields(row)


def update_application_integration_project(
    conn: Any,
    project_id: str,
    state: dict[str, Any],
    *,
    studio_project_id: str | None = None,
) -> dict:
    title = str(state.get("title") or project_id)
    if studio_project_id:
        get_project(conn, studio_project_id)
    row = conn.execute(
        "UPDATE application_integration_projects"
        " SET title = %s, studio_project_id = COALESCE(%s, studio_project_id), state = %s, updated_at = now()"
        " WHERE id = %s RETURNING *",
        (title, studio_project_id, Json(state), project_id),
    ).fetchone()
    if row is None:
        raise NotFoundError("application_integration_project", project_id)
    conn.commit()
    return _decode_json_fields(row)


def delete_application_integration_project(conn: Any, project_id: str) -> None:
    cur = conn.execute(
        "DELETE FROM application_integration_projects WHERE id = %s",
        (project_id,),
    )
    if cur.rowcount == 0:
        raise NotFoundError("application_integration_project", project_id)
    conn.commit()


# ---------------------------------------------------------------------------
# Generic Artifact CRUD (requirements_sets, scenarios)
# ---------------------------------------------------------------------------

def _list_artifacts(conn: Any, table: str, project_id: str) -> list[dict]:
    return _decode_json_rows(conn.execute(
        f"SELECT * FROM {table} WHERE project_id = %s ORDER BY created_at DESC",
        (project_id,),
    ).fetchall())


def _get_artifact(conn: Any, table: str, project_id: str,
                  artifact_id: str) -> dict:
    row = conn.execute(
        f"SELECT * FROM {table} WHERE id = %s AND project_id = %s",
        (artifact_id, project_id),
    ).fetchone()
    if row is None:
        raise NotFoundError(table, artifact_id)
    return _decode_json_fields(row)


def _create_artifact(conn: Any, table: str, project_id: str,
                     artifact_id: str, title: str, data: dict,
                     extra_cols: dict[str, Any] | None = None) -> dict:
    # Ensure the project exists
    get_project(conn, project_id)
    cols = ["id", "project_id", "title", "data", "content_hash"]
    vals = [artifact_id, project_id, title, Json(data), content_hash(data)]
    if extra_cols:
        for k, v in extra_cols.items():
            cols.append(k)
            vals.append(v)
    placeholders = ", ".join(["%s"] * len(cols))
    col_names = ", ".join(cols)
    row = conn.execute(
        f"INSERT INTO {table} ({col_names})"
        f" VALUES ({placeholders}) RETURNING *",
        vals,
    ).fetchone()
    conn.commit()
    return _decode_json_fields(row)


def _update_artifact(conn: Any, table: str, project_id: str,
                     artifact_id: str, **fields: Any) -> dict:
    allowed = {"title", "status", "data"}
    sets: list[str] = []
    params: list[Any] = []
    for key, value in fields.items():
        if key not in allowed or value is None:
            continue
        if key == "data":
            sets.append(f"{key} = %s")
            params.append(Json(value))
            # Recompute content_hash when data changes
            sets.append("content_hash = %s")
            params.append(content_hash(value))
        else:
            sets.append(f"{key} = %s")
            params.append(value)
    if not sets:
        return _get_artifact(conn, table, project_id, artifact_id)
    sets.append("updated_at = now()")
    params.extend([artifact_id, project_id])
    row = conn.execute(
        f"UPDATE {table} SET {', '.join(sets)}"
        f" WHERE id = %s AND project_id = %s RETURNING *",
        params,
    ).fetchone()
    if row is None:
        raise NotFoundError(table, artifact_id)
    conn.commit()
    return _decode_json_fields(row)


def _delete_artifact(conn: Any, table: str, project_id: str,
                     artifact_id: str,
                     blocked_by_table: Optional[str] = None,
                     blocked_by_fk: Optional[str] = None) -> None:
    # Check for blocking references before delete
    if blocked_by_table and blocked_by_fk:
        refs = conn.execute(
            f"SELECT id FROM {blocked_by_table} WHERE {blocked_by_fk} = %s",
            (artifact_id,),
        ).fetchall()
        if refs:
            raise ReferentialIntegrityError(
                table, artifact_id, blocked_by_table,
                [r["id"] for r in refs],
            )
    cur = conn.execute(
        f"DELETE FROM {table} WHERE id = %s AND project_id = %s",
        (artifact_id, project_id),
    )
    if cur.rowcount == 0:
        raise NotFoundError(table, artifact_id)
    conn.commit()


# --- Requirements Sets ---

def list_requirements(conn: Any, project_id: str) -> list[dict]:
    return _list_artifacts(conn, "requirements_sets", project_id)


def get_requirements(conn: Any, project_id: str, req_id: str) -> dict:
    return _get_artifact(conn, "requirements_sets", project_id, req_id)


def create_requirements(conn: Any, project_id: str, req_id: str,
                        title: str, data: dict) -> dict:
    # Auto-assign role: first requirements set in project is 'primary'
    has_primary = conn.execute(
        "SELECT 1 FROM requirements_sets"
        " WHERE project_id = %s AND role = 'primary' LIMIT 1",
        (project_id,),
    ).fetchone()
    role = "alternative" if has_primary else "primary"
    return _create_artifact(conn, "requirements_sets", project_id,
                            req_id, title, data,
                            extra_cols={"role": role})


def update_requirements(conn: Any, project_id: str, req_id: str,
                        **fields: Any) -> dict:
    return _update_artifact(conn, "requirements_sets", project_id,
                            req_id, **fields)


def delete_requirements(conn: Any, project_id: str, req_id: str) -> None:
    # Also blocked by shapes referencing this requirements set
    shape_refs = conn.execute(
        "SELECT id FROM shapes WHERE requirements_id = %s",
        (req_id,),
    ).fetchall()
    if shape_refs:
        raise ReferentialIntegrityError(
            "requirements_sets", req_id, "shapes",
            [r["id"] for r in shape_refs],
        )
    _delete_artifact(conn, "requirements_sets", project_id, req_id,
                     blocked_by_table="proposals",
                     blocked_by_fk="requirements_id")


def set_requirements_role(conn: Any, project_id: str, req_id: str,
                          role: str) -> dict:
    """Set the role of a requirements set ('primary' or 'alternative').

    If promoting to 'primary', the current primary is first demoted to
    'alternative'.  Both changes happen in the same transaction so the
    partial unique index is never violated.
    """
    if role not in ("primary", "alternative"):
        raise ValueError(f"Invalid role: {role!r}")

    # Verify the target exists
    _get_artifact(conn, "requirements_sets", project_id, req_id)

    if role == "primary":
        # Demote the current primary (if any) before promoting
        conn.execute(
            "UPDATE requirements_sets SET role = 'alternative'"
            " WHERE project_id = %s AND role = 'primary'",
            (project_id,),
        )

    row = conn.execute(
        "UPDATE requirements_sets SET role = %s"
        " WHERE id = %s AND project_id = %s RETURNING *",
        (role, req_id, project_id),
    ).fetchone()
    if row is None:
        raise NotFoundError("requirements_sets", req_id)
    conn.commit()
    return _decode_json_fields(row)


# --- Scenarios ---

def list_scenarios(conn: Any, project_id: str) -> list[dict]:
    return _list_artifacts(conn, "scenarios", project_id)


def get_scenario(conn: Any, project_id: str, scenario_id: str) -> dict:
    return _get_artifact(conn, "scenarios", project_id, scenario_id)


def create_scenario(conn: Any, project_id: str, scenario_id: str,
                    title: str, data: dict) -> dict:
    return _create_artifact(conn, "scenarios", project_id,
                            scenario_id, title, data)


def update_scenario(conn: Any, project_id: str, scenario_id: str,
                    **fields: Any) -> dict:
    return _update_artifact(conn, "scenarios", project_id,
                            scenario_id, **fields)


def delete_scenario(conn: Any, project_id: str, scenario_id: str) -> None:
    _delete_artifact(conn, "scenarios", project_id, scenario_id,
                     blocked_by_table="evaluations",
                     blocked_by_fk="scenario_id")


# --- Service Metadata Artifacts ---

def list_service_metadata_artifacts(conn: Any, project_id: str) -> list[dict]:
    return _list_artifacts(conn, "service_metadata_artifacts", project_id)


def get_service_metadata_artifact(conn: Any, project_id: str, artifact_id: str) -> dict:
    return _get_artifact(conn, "service_metadata_artifacts", project_id, artifact_id)


def create_service_metadata_artifact(
    conn: Any,
    project_id: str,
    artifact_id: str,
    title: str,
    data: dict,
) -> dict:
    return _create_artifact(
        conn,
        "service_metadata_artifacts",
        project_id,
        artifact_id,
        title,
        data,
    )


def update_service_metadata_artifact(
    conn: Any,
    project_id: str,
    artifact_id: str,
    **fields: Any,
) -> dict:
    return _update_artifact(
        conn,
        "service_metadata_artifacts",
        project_id,
        artifact_id,
        **fields,
    )


def delete_service_metadata_artifact(conn: Any, project_id: str, artifact_id: str) -> None:
    _delete_artifact(conn, "service_metadata_artifacts", project_id, artifact_id)


# --- PM Artifacts ---

def list_pm_artifacts(conn: Any, project_id: str) -> list[dict]:
    return _list_artifacts(conn, "pm_artifacts", project_id)


def get_pm_artifact(conn: Any, project_id: str, artifact_id: str) -> dict:
    return _get_artifact(conn, "pm_artifacts", project_id, artifact_id)


def create_pm_artifact(
    conn: Any,
    project_id: str,
    artifact_id: str,
    title: str,
    data: dict,
) -> dict:
    return _create_artifact(
        conn,
        "pm_artifacts",
        project_id,
        artifact_id,
        title,
        data,
    )


def update_pm_artifact(
    conn: Any,
    project_id: str,
    artifact_id: str,
    **fields: Any,
) -> dict:
    return _update_artifact(
        conn,
        "pm_artifacts",
        project_id,
        artifact_id,
        **fields,
    )


def delete_pm_artifact(conn: Any, project_id: str, artifact_id: str) -> None:
    _delete_artifact(conn, "pm_artifacts", project_id, artifact_id)


# --- Studio-local publication records ---

def _local_publication_summary(row: dict) -> dict:
    row = _decode_json_fields(row)
    package_record = row.get("package_record") or {}
    receipt = row.get("receipt") or {}
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "authority": row.get("authority") or "local-studio",
        "publication": {
            "package_id": row["package_id"],
            "package_version": row["package_version"],
            "project_ref": row["project_ref"],
            "product_revision_ref": row["product_revision_ref"],
            "developer_revision_ref": row["developer_revision_ref"],
            "contract_signature": row["contract_signature"],
            "lineage": package_record.get("lineage") or package_record.get("manifest", {}).get("lineage") or package_record.get("recommended_lock", {}).get("lineage") or {},
            "published_at": row["published_at"].isoformat() if hasattr(row["published_at"], "isoformat") else row["published_at"],
        },
        "package": package_record,
        "receipt": receipt,
        "created_at": row["created_at"].isoformat() if hasattr(row["created_at"], "isoformat") else row["created_at"],
    }


def list_local_publications(conn: Any, project_id: str) -> list[dict]:
    get_project(conn, project_id)
    rows = _decode_json_rows(conn.execute(
        "SELECT * FROM local_publications WHERE project_id = %s ORDER BY published_at DESC",
        (project_id,),
    ).fetchall())
    return [_local_publication_summary(row) for row in rows]


def get_local_publication(conn: Any, project_id: str, publication_id: str) -> dict:
    get_project(conn, project_id)
    row = conn.execute(
        "SELECT * FROM local_publications WHERE project_id = %s AND id = %s",
        (project_id, publication_id),
    ).fetchone()
    if row is None:
        raise NotFoundError("local_publication", publication_id)
    return _local_publication_summary(row)


def create_local_publication(
    conn: Any,
    *,
    project_id: str,
    publication_id: str,
    package_id: str,
    package_version: str,
    project_ref: str,
    product_revision_ref: str,
    developer_revision_ref: str,
    contract_signature: str,
    schema_version: str,
    manifest_digest: str,
    definition_digest: str,
    package_record: dict,
    receipt: dict,
) -> dict:
    get_project(conn, project_id)
    existing = conn.execute(
        "SELECT id FROM local_publications WHERE project_id = %s AND package_id = %s AND package_version = %s",
        (project_id, package_id, package_version),
    ).fetchone()
    if existing is not None:
        raise LocalPublicationExistsError(project_id, package_id, package_version)
    row = conn.execute(
        "INSERT INTO local_publications"
        " (id, project_id, package_id, package_version, project_ref, product_revision_ref,"
        "  developer_revision_ref, contract_signature, schema_version, manifest_digest,"
        "  definition_digest, package_record, receipt)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
        " RETURNING *",
        (
            publication_id,
            project_id,
            package_id,
            package_version,
            project_ref,
            product_revision_ref,
            developer_revision_ref,
            contract_signature,
            schema_version,
            manifest_digest,
            definition_digest,
            Json(package_record),
            Json(receipt),
        ),
    ).fetchone()
    conn.commit()
    return _local_publication_summary(row)


# ---------------------------------------------------------------------------
# Proposals
# ---------------------------------------------------------------------------

def list_proposals(conn: Any, project_id: str) -> list[dict]:
    return _decode_json_rows(conn.execute(
        "SELECT * FROM proposals WHERE project_id = %s ORDER BY created_at DESC",
        (project_id,),
    ).fetchall())


def get_proposal(conn: Any, project_id: str, proposal_id: str) -> dict:
    row = conn.execute(
        "SELECT * FROM proposals WHERE id = %s AND project_id = %s",
        (proposal_id, project_id),
    ).fetchone()
    if row is None:
        raise NotFoundError("proposals", proposal_id)
    return _decode_json_fields(row)


def create_proposal(conn: Any, project_id: str, proposal_id: str,
                    title: str, requirements_id: str, data: dict) -> dict:
    get_project(conn, project_id)
    assert_same_project(conn, project_id, requirements_id=requirements_id)
    row = conn.execute(
        "INSERT INTO proposals (id, project_id, requirements_id, title, data, content_hash)"
        " VALUES (%s, %s, %s, %s, %s, %s) RETURNING *",
        (proposal_id, project_id, requirements_id, title, Json(data),
         content_hash(data)),
    ).fetchone()
    conn.commit()
    return _decode_json_fields(row)


def update_proposal(conn: Any, project_id: str, proposal_id: str,
                    **fields: Any) -> dict:
    allowed = {"title", "status", "data"}
    sets: list[str] = []
    params: list[Any] = []
    for key, value in fields.items():
        if key not in allowed or value is None:
            continue
        if key == "data":
            sets.append(f"{key} = %s")
            params.append(Json(value))
            # Recompute content_hash when data changes
            sets.append("content_hash = %s")
            params.append(content_hash(value))
        else:
            sets.append(f"{key} = %s")
            params.append(value)
    if not sets:
        return get_proposal(conn, project_id, proposal_id)
    sets.append("updated_at = now()")
    params.extend([proposal_id, project_id])
    row = conn.execute(
        f"UPDATE proposals SET {', '.join(sets)}"
        " WHERE id = %s AND project_id = %s RETURNING *",
        params,
    ).fetchone()
    if row is None:
        raise NotFoundError("proposals", proposal_id)
    conn.commit()
    return _decode_json_fields(row)


def delete_proposal(conn: Any, project_id: str, proposal_id: str) -> None:
    # Blocked by evaluations
    refs = conn.execute(
        "SELECT id FROM evaluations WHERE proposal_id = %s",
        (proposal_id,),
    ).fetchall()
    if refs:
        raise ReferentialIntegrityError(
            "proposals", proposal_id, "evaluations",
            [r["id"] for r in refs],
        )
    cur = conn.execute(
        "DELETE FROM proposals WHERE id = %s AND project_id = %s",
        (proposal_id, project_id),
    )
    if cur.rowcount == 0:
        raise NotFoundError("proposals", proposal_id)
    conn.commit()


# ---------------------------------------------------------------------------
# Shapes
# ---------------------------------------------------------------------------

def list_shapes(conn: Any, project_id: str) -> list[dict]:
    return _decode_json_rows(conn.execute(
        "SELECT * FROM shapes WHERE project_id = %s ORDER BY created_at DESC",
        (project_id,),
    ).fetchall())


def get_shape(conn: Any, project_id: str, shape_id: str) -> dict:
    row = conn.execute(
        "SELECT * FROM shapes WHERE id = %s AND project_id = %s",
        (shape_id, project_id),
    ).fetchone()
    if row is None:
        raise NotFoundError("shapes", shape_id)
    return _decode_json_fields(row)


def create_shape(conn: Any, project_id: str, shape_id: str,
                 title: str, requirements_id: str, data: dict) -> dict:
    get_project(conn, project_id)
    assert_same_project(conn, project_id, requirements_id=requirements_id)
    validate_shape_integrity(data)
    row = conn.execute(
        "INSERT INTO shapes (id, project_id, requirements_id, title, data, content_hash)"
        " VALUES (%s, %s, %s, %s, %s, %s) RETURNING *",
        (shape_id, project_id, requirements_id, title, Json(data),
         content_hash(data)),
    ).fetchone()
    conn.commit()
    return _decode_json_fields(row)


def update_shape(conn: Any, project_id: str, shape_id: str,
                 **fields: Any) -> dict:
    allowed = {"title", "status", "data"}
    sets: list[str] = []
    params: list[Any] = []
    for key, value in fields.items():
        if key not in allowed or value is None:
            continue
        if key == "data":
            # Revalidate integrity when data changes
            validate_shape_integrity(value)
            sets.append(f"{key} = %s")
            params.append(Json(value))
            sets.append("content_hash = %s")
            params.append(content_hash(value))
        else:
            sets.append(f"{key} = %s")
            params.append(value)
    if not sets:
        return get_shape(conn, project_id, shape_id)
    sets.append("updated_at = now()")
    params.extend([shape_id, project_id])
    row = conn.execute(
        f"UPDATE shapes SET {', '.join(sets)}"
        " WHERE id = %s AND project_id = %s RETURNING *",
        params,
    ).fetchone()
    if row is None:
        raise NotFoundError("shapes", shape_id)
    conn.commit()
    return _decode_json_fields(row)


def delete_shape(conn: Any, project_id: str, shape_id: str) -> None:
    # Blocked by evaluations
    refs = conn.execute(
        "SELECT id FROM evaluations WHERE shape_id = %s",
        (shape_id,),
    ).fetchall()
    if refs:
        raise ReferentialIntegrityError(
            "shapes", shape_id, "evaluations",
            [r["id"] for r in refs],
        )
    cur = conn.execute(
        "DELETE FROM shapes WHERE id = %s AND project_id = %s",
        (shape_id, project_id),
    )
    if cur.rowcount == 0:
        raise NotFoundError("shapes", shape_id)
    conn.commit()


# ---------------------------------------------------------------------------
# Evaluations
# ---------------------------------------------------------------------------

def _compute_staleness(eval_row: dict, current_req_hash: str,
                       current_prop_hash: str,
                       current_scn_hash: str,
                       current_shape_hash: str = "") -> tuple[bool, list[str]]:
    """Compare stored per-artifact hashes against current hashes."""
    stale: list[str] = []
    if eval_row["requirements_hash"] != current_req_hash:
        stale.append("requirements")
    if eval_row["proposal_hash"] != current_prop_hash:
        stale.append("proposal")
    if eval_row["scenario_hash"] != current_scn_hash:
        stale.append("scenario")
    # Shape staleness (only for shape-backed evaluations)
    if eval_row.get("shape_id") and eval_row.get("shape_hash", "") != current_shape_hash:
        stale.append("shape")
    return len(stale) > 0, stale


def _enrich_evaluation_staleness(conn: Any, eval_dict: dict) -> dict:
    """Add is_stale and stale_artifacts to a single evaluation dict."""
    try:
        req_row = get_requirements(conn, eval_dict["project_id"],
                                   eval_dict["requirements_id"])
        current_prop_hash = ""
        if eval_dict.get("proposal_id"):
            prop_row = get_proposal(conn, eval_dict["project_id"],
                                    eval_dict["proposal_id"])
            current_prop_hash = prop_row["content_hash"]
        scn_row = get_scenario(conn, eval_dict["project_id"],
                               eval_dict["scenario_id"])
        current_shape_hash = ""
        if eval_dict.get("shape_id"):
            shape_row = get_shape(conn, eval_dict["project_id"],
                                  eval_dict["shape_id"])
            current_shape_hash = shape_row["content_hash"]
        is_stale, stale_artifacts = _compute_staleness(
            eval_dict,
            req_row["content_hash"],
            current_prop_hash,
            scn_row["content_hash"],
            current_shape_hash,
        )
    except NotFoundError:
        # If a linked artifact has been deleted, mark as stale
        is_stale = True
        stale_artifacts = ["unknown"]
    eval_dict["is_stale"] = is_stale
    eval_dict["stale_artifacts"] = stale_artifacts
    return eval_dict


def list_evaluations(conn: Any, project_id: str, *,
                     scenario_id: Optional[str] = None,
                     proposal_id: Optional[str] = None,
                     shape_id: Optional[str] = None) -> list[dict]:
    # Use JOINs to avoid N+1 queries for staleness computation
    # LEFT JOIN proposals since proposal_id is now optional (shape-backed evals)
    query = (
        "SELECT e.*,"
        "  rs.content_hash AS current_req_hash,"
        "  COALESCE(p.content_hash, '') AS current_prop_hash,"
        "  s.content_hash AS current_scn_hash,"
        "  COALESCE(sh.content_hash, '') AS current_shape_hash"
        " FROM evaluations e"
        " JOIN requirements_sets rs ON e.requirements_id = rs.id"
        " LEFT JOIN proposals p ON e.proposal_id = p.id"
        " JOIN scenarios s ON e.scenario_id = s.id"
        " LEFT JOIN shapes sh ON e.shape_id = sh.id"
        " WHERE e.project_id = %s"
    )
    params: list[Any] = [project_id]
    if scenario_id is not None:
        query += " AND e.scenario_id = %s"
        params.append(scenario_id)
    if proposal_id is not None:
        query += " AND e.proposal_id = %s"
        params.append(proposal_id)
    if shape_id is not None:
        query += " AND e.shape_id = %s"
        params.append(shape_id)
    query += " ORDER BY e.created_at DESC"
    rows = conn.execute(query, params).fetchall()
    result = []
    for row in _decode_json_rows(rows):
        is_stale, stale_artifacts = _compute_staleness(
            row,
            row.pop("current_req_hash", ""),
            row.pop("current_prop_hash", ""),
            row.pop("current_scn_hash", ""),
            row.pop("current_shape_hash", ""),
        )
        row["is_stale"] = is_stale
        row["stale_artifacts"] = stale_artifacts
        result.append(row)
    return result


def get_evaluation(conn: Any, project_id: str, eval_id: str) -> dict:
    row = conn.execute(
        "SELECT * FROM evaluations WHERE id = %s AND project_id = %s",
        (eval_id, project_id),
    ).fetchone()
    if row is None:
        raise NotFoundError("evaluations", eval_id)
    return _enrich_evaluation_staleness(conn, _decode_json_fields(row))


def create_evaluation(conn: Any, project_id: str, eval_id: str,
                      proposal_id: Optional[str], scenario_id: str,
                      requirements_id: str, source: str,
                      data: dict, input_snapshot: dict,
                      shape_id: Optional[str] = None) -> dict:
    get_project(conn, project_id)
    # Build coherence checks dynamically (proposal_id and shape_id are optional)
    coherence_refs: dict[str, str] = {
        "scenario_id": scenario_id,
        "requirements_id": requirements_id,
    }
    if proposal_id:
        coherence_refs["proposal_id"] = proposal_id
    if shape_id:
        coherence_refs["shape_id"] = shape_id
    assert_same_project(conn, project_id, **coherence_refs)

    # Capture current content_hash of each linked artifact
    req_row = get_requirements(conn, project_id, requirements_id)
    requirements_hash = req_row["content_hash"]

    proposal_hash = ""
    if proposal_id:
        prop_row = get_proposal(conn, project_id, proposal_id)
        proposal_hash = prop_row["content_hash"]

    scn_row = get_scenario(conn, project_id, scenario_id)
    scenario_hash = scn_row["content_hash"]

    shape_hash = ""
    derived_expectations_snapshot = None
    if shape_id:
        shape_row = get_shape(conn, project_id, shape_id)
        shape_hash = shape_row["content_hash"]
        # Derive and snapshot contract expectations
        from .derivation import derive_contract_expectations
        derived_expectations_snapshot = derive_contract_expectations(
            shape_row["data"], req_row["data"],
        )

    # Extract result from the evaluation data
    result = data.get("evaluation", {}).get("result", "REQUIRES_GLUE")
    row = conn.execute(
        "INSERT INTO evaluations"
        " (id, project_id, proposal_id, scenario_id, requirements_id,"
        "  result, source, data, input_snapshot,"
        "  requirements_hash, proposal_hash, scenario_hash,"
        "  shape_id, shape_hash, derived_expectations)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
        " RETURNING *",
        (eval_id, project_id, proposal_id, scenario_id, requirements_id,
         result, source, Json(data), Json(input_snapshot),
         requirements_hash, proposal_hash, scenario_hash,
         shape_id, shape_hash,
         Json(derived_expectations_snapshot) if derived_expectations_snapshot is not None else None),
    ).fetchone()
    conn.commit()
    return _decode_json_fields(row)


def delete_evaluation(conn: Any, project_id: str, eval_id: str) -> None:
    cur = conn.execute(
        "DELETE FROM evaluations WHERE id = %s AND project_id = %s",
        (eval_id, project_id),
    )
    if cur.rowcount == 0:
        raise NotFoundError("evaluations", eval_id)
    conn.commit()


# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

def list_vocabulary(conn: Any, *,
                    category: Optional[str] = None,
                    project_id: Optional[str] = None) -> list[dict]:
    """Return vocabulary entries merging global (NULL project_id) and project-local."""
    query = "SELECT * FROM vocabulary WHERE (project_id IS NULL"
    params: list[Any] = []
    if project_id is not None:
        query += " OR project_id = %s"
        params.append(project_id)
    query += ")"
    if category is not None:
        query += " AND category = %s"
        params.append(category)
    query += " ORDER BY category, value"
    return conn.execute(query, params).fetchall()


def create_vocabulary(conn: Any, project_id: Optional[str],
                      category: str, value: str,
                      origin: str = "custom",
                      description: str = "") -> dict:
    row = conn.execute(
        "INSERT INTO vocabulary (project_id, category, value, origin, description)"
        " VALUES (%s, %s, %s, %s, %s) RETURNING *",
        (project_id, category, value, origin, description),
    ).fetchone()
    conn.commit()
    return row


def delete_vocabulary(conn: Any, vocab_id: int) -> None:
    cur = conn.execute("DELETE FROM vocabulary WHERE id = %s", (vocab_id,))
    if cur.rowcount == 0:
        raise NotFoundError("vocabulary", str(vocab_id))
    conn.commit()


def load_vocabulary_defaults(conn: Any, defaults_path: str | Path) -> int:
    """Load canonical vocabulary entries from a JSON file.

    Returns the number of entries inserted (duplicates are skipped).
    """
    defaults_path = Path(defaults_path)
    if not defaults_path.exists():
        return 0
    with open(defaults_path) as f:
        entries = json.load(f)
    inserted = 0
    for entry in entries:
        try:
            conn.execute(
                "INSERT INTO vocabulary"
                " (project_id, category, value, origin, description, evaluator_recognized)"
                " VALUES (NULL, %s, %s, %s, %s, %s)"
                " ON CONFLICT DO NOTHING",
                (entry["category"], entry["value"],
                 entry.get("origin", "canonical"),
                 entry.get("description", ""),
                 entry.get("evaluator_recognized", False)),
            )
            inserted += 1
        except Exception:
            pass  # skip duplicates or malformed entries
    conn.commit()
    return inserted
