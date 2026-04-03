"""Thin CRUD layer over Postgres for ANIP Studio.

All SQL lives in this module.  Functions accept a psycopg connection
(obtained via ``with get_pool().connection() as conn``) and use ``%s``
parameter placeholders.  JSONB columns are written with
``psycopg.types.json.Json`` and read as plain Python dicts thanks to
``dict_row``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from psycopg.types.json import Json

from .hashing import content_hash


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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REF_TABLE_MAP: dict[str, str] = {
    "requirements_id": "requirements_sets",
    "scenario_id": "scenarios",
    "proposal_id": "proposals",
}


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
# Projects
# ---------------------------------------------------------------------------

def list_projects(conn: Any) -> list[dict]:
    return conn.execute(
        "SELECT * FROM projects ORDER BY updated_at DESC"
    ).fetchall()


def get_project(conn: Any, project_id: str) -> dict:
    row = conn.execute(
        "SELECT * FROM projects WHERE id = %s", (project_id,)
    ).fetchone()
    if row is None:
        raise NotFoundError("project", project_id)
    return row


def get_project_detail(conn: Any, project_id: str) -> dict:
    row = conn.execute(
        "SELECT p.*,"
        "  (SELECT count(*) FROM requirements_sets WHERE project_id = p.id) AS requirements_count,"
        "  (SELECT count(*) FROM scenarios WHERE project_id = p.id) AS scenarios_count,"
        "  (SELECT count(*) FROM proposals WHERE project_id = p.id) AS proposals_count,"
        "  (SELECT count(*) FROM evaluations WHERE project_id = p.id) AS evaluations_count"
        " FROM projects p WHERE p.id = %s",
        (project_id,),
    ).fetchone()
    if row is None:
        raise NotFoundError("project", project_id)
    return row


def create_project(conn: Any, project_id: str, name: str, summary: str = "",
                   domain: str = "", labels: list | None = None) -> dict:
    labels = labels if labels is not None else []
    row = conn.execute(
        "INSERT INTO projects (id, name, summary, domain, labels)"
        " VALUES (%s, %s, %s, %s, %s) RETURNING *",
        (project_id, name, summary, domain, Json(labels)),
    ).fetchone()
    conn.commit()
    return row


def update_project(conn: Any, project_id: str, **fields: Any) -> dict:
    # Build SET clause from provided fields
    allowed = {"name", "summary", "domain", "labels"}
    sets: list[str] = []
    params: list[Any] = []
    for key, value in fields.items():
        if key not in allowed or value is None:
            continue
        if key == "labels":
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
    return row


def delete_project(conn: Any, project_id: str) -> None:
    cur = conn.execute("DELETE FROM projects WHERE id = %s", (project_id,))
    if cur.rowcount == 0:
        raise NotFoundError("project", project_id)
    conn.commit()


# ---------------------------------------------------------------------------
# Generic Artifact CRUD (requirements_sets, scenarios)
# ---------------------------------------------------------------------------

def _list_artifacts(conn: Any, table: str, project_id: str) -> list[dict]:
    return conn.execute(
        f"SELECT * FROM {table} WHERE project_id = %s ORDER BY created_at DESC",
        (project_id,),
    ).fetchall()


def _get_artifact(conn: Any, table: str, project_id: str,
                  artifact_id: str) -> dict:
    row = conn.execute(
        f"SELECT * FROM {table} WHERE id = %s AND project_id = %s",
        (artifact_id, project_id),
    ).fetchone()
    if row is None:
        raise NotFoundError(table, artifact_id)
    return row


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
    return row


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
    return row


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
    return row


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


# ---------------------------------------------------------------------------
# Proposals
# ---------------------------------------------------------------------------

def list_proposals(conn: Any, project_id: str) -> list[dict]:
    return conn.execute(
        "SELECT * FROM proposals WHERE project_id = %s ORDER BY created_at DESC",
        (project_id,),
    ).fetchall()


def get_proposal(conn: Any, project_id: str, proposal_id: str) -> dict:
    row = conn.execute(
        "SELECT * FROM proposals WHERE id = %s AND project_id = %s",
        (proposal_id, project_id),
    ).fetchone()
    if row is None:
        raise NotFoundError("proposals", proposal_id)
    return row


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
    return row


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
    return row


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
# Evaluations
# ---------------------------------------------------------------------------

def _compute_staleness(eval_row: dict, current_req_hash: str,
                       current_prop_hash: str,
                       current_scn_hash: str) -> tuple[bool, list[str]]:
    """Compare stored per-artifact hashes against current hashes."""
    stale: list[str] = []
    if eval_row["requirements_hash"] != current_req_hash:
        stale.append("requirements")
    if eval_row["proposal_hash"] != current_prop_hash:
        stale.append("proposal")
    if eval_row["scenario_hash"] != current_scn_hash:
        stale.append("scenario")
    return len(stale) > 0, stale


def _enrich_evaluation_staleness(conn: Any, eval_dict: dict) -> dict:
    """Add is_stale and stale_artifacts to a single evaluation dict."""
    try:
        req_row = get_requirements(conn, eval_dict["project_id"],
                                   eval_dict["requirements_id"])
        prop_row = get_proposal(conn, eval_dict["project_id"],
                                eval_dict["proposal_id"])
        scn_row = get_scenario(conn, eval_dict["project_id"],
                               eval_dict["scenario_id"])
        is_stale, stale_artifacts = _compute_staleness(
            eval_dict,
            req_row["content_hash"],
            prop_row["content_hash"],
            scn_row["content_hash"],
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
                     proposal_id: Optional[str] = None) -> list[dict]:
    # Use a JOIN to avoid N+1 queries for staleness computation
    query = (
        "SELECT e.*,"
        "  rs.content_hash AS current_req_hash,"
        "  p.content_hash AS current_prop_hash,"
        "  s.content_hash AS current_scn_hash"
        " FROM evaluations e"
        " JOIN requirements_sets rs ON e.requirements_id = rs.id"
        " JOIN proposals p ON e.proposal_id = p.id"
        " JOIN scenarios s ON e.scenario_id = s.id"
        " WHERE e.project_id = %s"
    )
    params: list[Any] = [project_id]
    if scenario_id is not None:
        query += " AND e.scenario_id = %s"
        params.append(scenario_id)
    if proposal_id is not None:
        query += " AND e.proposal_id = %s"
        params.append(proposal_id)
    query += " ORDER BY e.created_at DESC"
    rows = conn.execute(query, params).fetchall()
    result = []
    for row in rows:
        is_stale, stale_artifacts = _compute_staleness(
            row,
            row.pop("current_req_hash", ""),
            row.pop("current_prop_hash", ""),
            row.pop("current_scn_hash", ""),
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
    return _enrich_evaluation_staleness(conn, row)


def create_evaluation(conn: Any, project_id: str, eval_id: str,
                      proposal_id: str, scenario_id: str,
                      requirements_id: str, source: str,
                      data: dict, input_snapshot: dict) -> dict:
    get_project(conn, project_id)
    assert_same_project(
        conn, project_id,
        proposal_id=proposal_id,
        scenario_id=scenario_id,
        requirements_id=requirements_id,
    )
    # Capture current content_hash of each linked artifact
    req_row = get_requirements(conn, project_id, requirements_id)
    prop_row = get_proposal(conn, project_id, proposal_id)
    scn_row = get_scenario(conn, project_id, scenario_id)
    requirements_hash = req_row["content_hash"]
    proposal_hash = prop_row["content_hash"]
    scenario_hash = scn_row["content_hash"]

    # Extract result from the evaluation data
    result = data.get("evaluation", {}).get("result", "REQUIRES_GLUE")
    row = conn.execute(
        "INSERT INTO evaluations"
        " (id, project_id, proposal_id, scenario_id, requirements_id,"
        "  result, source, data, input_snapshot,"
        "  requirements_hash, proposal_hash, scenario_hash)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *",
        (eval_id, project_id, proposal_id, scenario_id, requirements_id,
         result, source, Json(data), Json(input_snapshot),
         requirements_hash, proposal_hash, scenario_hash),
    ).fetchone()
    conn.commit()
    return row


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
