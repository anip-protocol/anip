"""Routes for import, export, and seed operations."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..db import get_pool
from ..models import ImportRequest, ImportResult
from ..repository import (
    NotFoundError,
    ProjectCoherenceError,
    ReferentialIntegrityError,
)
from .. import repository
from ..seed import seed_from_examples

router = APIRouter(tags=["import_export"])


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
                    repository.create_requirements(
                        conn, project_id=pid, req_id=art_id,
                        title=title, data=data.get("data", data),
                    )
                elif art_type == "scenario":
                    art_id = data.get("id", f"imp-scn-{i}")
                    title = data.get("title", f"Imported scenario {i}")
                    repository.create_scenario(
                        conn, project_id=pid, scenario_id=art_id,
                        title=title, data=data.get("data", data),
                    )
                elif art_type == "proposal":
                    art_id = data.get("id", f"imp-prop-{i}")
                    title = data.get("title", f"Imported proposal {i}")
                    requirements_id = data.get("requirements_id")
                    if not requirements_id:
                        errors.append(
                            f"Artifact {i}: proposal requires requirements_id"
                        )
                        continue
                    repository.create_proposal(
                        conn, project_id=pid, proposal_id=art_id,
                        title=title, requirements_id=requirements_id,
                        data=data.get("data", data),
                    )
                elif art_type == "evaluation":
                    art_id = data.get("id", f"imp-eval-{i}")
                    for ref in ("proposal_id", "scenario_id", "requirements_id"):
                        if ref not in data:
                            errors.append(
                                f"Artifact {i}: evaluation requires {ref}"
                            )
                            break
                    else:
                        repository.create_evaluation(
                            conn, project_id=pid, eval_id=art_id,
                            proposal_id=data["proposal_id"],
                            scenario_id=data["scenario_id"],
                            requirements_id=data["requirements_id"],
                            source=data.get("source", "imported"),
                            data=data.get("data", data),
                            input_snapshot=data.get("input_snapshot", {}),
                        )
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


@router.get("/api/projects/{pid}/export")
def export_project(pid: str):
    """Export all artifacts for a project as a JSON object graph."""
    with get_pool().connection() as conn:
        try:
            project = repository.get_project(conn, pid)
        except NotFoundError:
            raise HTTPException(status_code=404, detail=f"Project {pid!r} not found")

        return {
            "project": project,
            "requirements": repository.list_requirements(conn, pid),
            "scenarios": repository.list_scenarios(conn, pid),
            "proposals": repository.list_proposals(conn, pid),
            "evaluations": repository.list_evaluations(conn, pid),
        }


@router.post("/api/seed")
def seed():
    """Seed the database from example packs (dev/demo only)."""
    with get_pool().connection() as conn:
        return seed_from_examples(conn)
