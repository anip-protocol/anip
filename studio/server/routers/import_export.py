"""Routes for import, export, and seed operations."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import jsonschema
from fastapi import APIRouter, HTTPException

from ..db import get_pool
from ..hashing import content_hash
from ..models import ImportRequest, ImportResult
from ..repository import (
    NotFoundError,
    ProjectCoherenceError,
    ReferentialIntegrityError,
)
from .. import repository
from ..seed import seed_from_examples

router = APIRouter(tags=["import_export"])

# ---------------------------------------------------------------------------
# Schema loading
# ---------------------------------------------------------------------------

_SCHEMAS_DIR = Path(__file__).parent.parent.parent.parent / "tooling" / "schemas"

_SCHEMA_FILES: dict[str, str] = {
    "requirements": "requirements.schema.json",
    "scenario": "scenario.schema.json",
    "proposal": "proposal.schema.json",
    "evaluation": "evaluation.schema.json",
}

_loaded_schemas: dict[str, dict] = {}


def _get_schema(artifact_type: str) -> dict | None:
    """Return the loaded JSON schema for the given artifact type, or None."""
    if artifact_type not in _SCHEMA_FILES:
        return None
    if artifact_type not in _loaded_schemas:
        path = _SCHEMAS_DIR / _SCHEMA_FILES[artifact_type]
        if path.exists():
            with open(path) as f:
                _loaded_schemas[artifact_type] = json.load(f)
        else:
            return None
    return _loaded_schemas[artifact_type]


def _validate_against_schema(artifact_type: str, data: dict) -> list[str]:
    """Validate *data* against the schema for *artifact_type*.

    Returns a list of human-readable error messages (empty means valid).
    """
    schema = _get_schema(artifact_type)
    if schema is None:
        return []
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    return [f"{'.'.join(str(p) for p in e.path) or '<root>'}: {e.message}"
            for e in errors]


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

@router.post("/api/projects/{pid}/import", response_model=ImportResult)
def import_artifacts(pid: str, body: ImportRequest):
    """Import individual artifacts into an existing project."""
    imported = 0
    errors: list[str] = []

    with get_pool().connection() as conn:
        # Verify the project exists
        try:
            repository.get_project(conn, pid)
        except NotFoundError:
            raise HTTPException(status_code=404, detail=f"Project {pid!r} not found")

        for i, artifact in enumerate(body.artifacts):
            try:
                art_type = artifact.type
                data = artifact.data

                if art_type == "requirements":
                    art_id = data.get("id", f"imp-req-{i}")
                    title = data.get("title", f"Imported requirements {i}")
                    art_data = data.get("data", data)

                    # Schema validation
                    schema_errors = _validate_against_schema("requirements", art_data)
                    if schema_errors:
                        errors.append(
                            f"Artifact {i} (requirements {art_id!r}): "
                            f"schema validation failed: {'; '.join(schema_errors)}"
                        )
                        continue

                    # Duplicate ID check
                    existing = conn.execute(
                        "SELECT id FROM requirements_sets WHERE id = %s", (art_id,)
                    ).fetchone()
                    if existing:
                        errors.append(
                            f"Artifact {i} (requirements {art_id!r}): "
                            f"duplicate ID — a requirements set with id {art_id!r} already exists"
                        )
                        continue

                    repository.create_requirements(
                        conn, project_id=pid, req_id=art_id,
                        title=title, data=art_data,
                    )

                elif art_type == "scenario":
                    art_id = data.get("id", f"imp-scn-{i}")
                    title = data.get("title", f"Imported scenario {i}")
                    art_data = data.get("data", data)

                    # Schema validation
                    schema_errors = _validate_against_schema("scenario", art_data)
                    if schema_errors:
                        errors.append(
                            f"Artifact {i} (scenario {art_id!r}): "
                            f"schema validation failed: {'; '.join(schema_errors)}"
                        )
                        continue

                    # Duplicate ID check
                    existing = conn.execute(
                        "SELECT id FROM scenarios WHERE id = %s", (art_id,)
                    ).fetchone()
                    if existing:
                        errors.append(
                            f"Artifact {i} (scenario {art_id!r}): "
                            f"duplicate ID — a scenario with id {art_id!r} already exists"
                        )
                        continue

                    repository.create_scenario(
                        conn, project_id=pid, scenario_id=art_id,
                        title=title, data=art_data,
                    )

                elif art_type == "proposal":
                    art_id = data.get("id", f"imp-prop-{i}")
                    title = data.get("title", f"Imported approach {i}")
                    requirements_id = data.get("requirements_id")
                    art_data = data.get("data", data)

                    if not requirements_id:
                        errors.append(
                            f"Artifact {i} (proposal {art_id!r}): approach requires requirements_id"
                        )
                        continue

                    # Validate requirements_id exists in the target project
                    req_row = conn.execute(
                        "SELECT id FROM requirements_sets WHERE id = %s AND project_id = %s",
                        (requirements_id, pid),
                    ).fetchone()
                    if req_row is None:
                        errors.append(
                            f"Artifact {i} (proposal {art_id!r}): "
                            f"requirements_id {requirements_id!r} does not exist in project {pid!r}"
                        )
                        continue

                    # Schema validation
                    schema_errors = _validate_against_schema("proposal", art_data)
                    if schema_errors:
                        errors.append(
                            f"Artifact {i} (proposal {art_id!r}): "
                            f"schema validation failed: {'; '.join(schema_errors)}"
                        )
                        continue

                    # Duplicate ID check
                    existing = conn.execute(
                        "SELECT id FROM proposals WHERE id = %s", (art_id,)
                    ).fetchone()
                    if existing:
                        errors.append(
                            f"Artifact {i} (proposal {art_id!r}): "
                            f"duplicate ID — a proposal with id {art_id!r} already exists"
                        )
                        continue

                    repository.create_proposal(
                        conn, project_id=pid, proposal_id=art_id,
                        title=title, requirements_id=requirements_id,
                        data=art_data,
                    )

                elif art_type == "evaluation":
                    art_id = data.get("id", f"imp-eval-{i}")
                    art_data = data.get("data", data)

                    # Check required reference fields
                    missing_refs = [
                        ref for ref in ("proposal_id", "scenario_id", "requirements_id")
                        if ref not in data
                    ]
                    if missing_refs:
                        for ref in missing_refs:
                            errors.append(
                                f"Artifact {i} (evaluation {art_id!r}): "
                                f"evaluation requires {ref}"
                            )
                        continue

                    # Validate that all referenced artifacts exist in the target project
                    ref_checks = [
                        ("requirements_id", "requirements_sets"),
                        ("proposal_id", "proposals"),
                        ("scenario_id", "scenarios"),
                    ]
                    ref_error = False
                    for ref_field, ref_table in ref_checks:
                        ref_id = data[ref_field]
                        ref_row = conn.execute(
                            f"SELECT id FROM {ref_table} WHERE id = %s AND project_id = %s",
                            (ref_id, pid),
                        ).fetchone()
                        if ref_row is None:
                            errors.append(
                                f"Artifact {i} (evaluation {art_id!r}): "
                                f"{ref_field} {ref_id!r} does not exist in project {pid!r}"
                            )
                            ref_error = True
                    if ref_error:
                        continue

                    # Require input_snapshot
                    input_snapshot = data.get("input_snapshot")
                    if not input_snapshot:
                        errors.append(
                            f"Artifact {i} (evaluation {art_id!r}): "
                            f"evaluation must include input_snapshot"
                        )
                        continue

                    # Schema validation
                    schema_errors = _validate_against_schema("evaluation", art_data)
                    if schema_errors:
                        errors.append(
                            f"Artifact {i} (evaluation {art_id!r}): "
                            f"schema validation failed: {'; '.join(schema_errors)}"
                        )
                        continue

                    # Duplicate ID check
                    existing = conn.execute(
                        "SELECT id FROM evaluations WHERE id = %s", (art_id,)
                    ).fetchone()
                    if existing:
                        errors.append(
                            f"Artifact {i} (evaluation {art_id!r}): "
                            f"duplicate ID — an evaluation with id {art_id!r} already exists"
                        )
                        continue

                    # Compute missing per-artifact hashes from snapshot content
                    requirements_hash_val = data.get("requirements_hash")
                    proposal_hash_val = data.get("proposal_hash")
                    scenario_hash_val = data.get("scenario_hash")

                    if not (requirements_hash_val and proposal_hash_val and scenario_hash_val):
                        snap_req = input_snapshot.get("requirements", {})
                        snap_prop = input_snapshot.get("proposal", {})
                        snap_scn = input_snapshot.get("scenario", {})
                        if not requirements_hash_val and snap_req:
                            requirements_hash_val = content_hash(snap_req)
                        if not proposal_hash_val and snap_prop:
                            proposal_hash_val = content_hash(snap_prop)
                        if not scenario_hash_val and snap_scn:
                            scenario_hash_val = content_hash(snap_scn)

                    # Fall back to empty string if snapshot sections are also missing
                    requirements_hash_val = requirements_hash_val or ""
                    proposal_hash_val = proposal_hash_val or ""
                    scenario_hash_val = scenario_hash_val or ""

                    result = art_data.get("evaluation", {}).get("result", "REQUIRES_GLUE")
                    conn.execute(
                        "INSERT INTO evaluations"
                        " (id, project_id, proposal_id, scenario_id, requirements_id,"
                        "  result, source, data, input_snapshot,"
                        "  requirements_hash, proposal_hash, scenario_hash)"
                        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s)",
                        (
                            art_id, pid,
                            data["proposal_id"], data["scenario_id"], data["requirements_id"],
                            result,
                            data.get("source", "imported"),
                            json.dumps(art_data),
                            json.dumps(input_snapshot),
                            requirements_hash_val,
                            proposal_hash_val,
                            scenario_hash_val,
                        ),
                    )
                    conn.commit()

                else:
                    errors.append(f"Artifact {i}: unknown type {art_type!r}")
                    continue

                imported += 1
            except ProjectCoherenceError as e:
                errors.append(f"Artifact {i}: {e}")
            except ReferentialIntegrityError as e:
                errors.append(f"Artifact {i}: {e}")
            except NotFoundError as e:
                errors.append(f"Artifact {i}: {e}")
            except Exception as e:
                errors.append(f"Artifact {i}: {e}")

    return ImportResult(imported=imported, errors=errors)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

@router.get("/api/projects/{pid}/export")
def export_project(pid: str):
    """Export all artifacts for a project as a JSON object graph."""
    with get_pool().connection() as conn:
        try:
            project = repository.get_project(conn, pid)
        except NotFoundError:
            raise HTTPException(status_code=404, detail=f"Project {pid!r} not found")

        evaluations_raw = repository.list_evaluations(conn, pid)
        # Strip is_stale — it's environment-relative, not durable export truth.
        # Importers can recompute staleness from the per-artifact hashes after import.
        evaluations_export = []
        for ev in evaluations_raw:
            ev_clean = {k: v for k, v in ev.items()
                        if k not in ("is_stale", "stale_artifacts")}
            evaluations_export.append(ev_clean)

        return {
            "metadata": {
                "exported_at": datetime.now(timezone.utc).isoformat(),
            },
            "project": project,
            "requirements": repository.list_requirements(conn, pid),
            "scenarios": repository.list_scenarios(conn, pid),
            "proposals": repository.list_proposals(conn, pid),
            "evaluations": evaluations_export,
        }


# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------

@router.post("/api/seed")
def seed():
    """Seed the database from example packs (dev/demo only)."""
    with get_pool().connection() as conn:
        return seed_from_examples(conn)
