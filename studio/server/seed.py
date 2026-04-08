"""Seed Studio with curated built-in demo projects."""

from __future__ import annotations

from typing import Any

from . import repository
from .seed_catalog import SEED_PROJECTS


def seed_from_examples(conn: Any) -> dict:
    """Create curated seed projects for local demos.

    Existing projects are matched by ID and skipped, making the seed
    operation idempotent.
    """

    created = 0
    skipped = 0

    for item in SEED_PROJECTS:
        project = item["project"]
        project_id = project["id"]
        try:
            repository.get_project(conn, project_id)
            skipped += 1
            continue
        except repository.NotFoundError:
            pass

        repository.create_project(
            conn,
            project_id=project_id,
            name=project["name"],
            summary=project["summary"],
            domain=project["domain"],
        )

        requirements = item["requirements"]
        repository.create_requirements(
            conn,
            project_id=project_id,
            req_id=requirements["id"],
            title=requirements["title"],
            data=requirements["data"],
        )

        scenario = item["scenario"]
        repository.create_scenario(
            conn,
            project_id=project_id,
            scenario_id=scenario["id"],
            title=scenario["title"],
            data=scenario["data"],
        )

        proposal = item["proposal"]
        repository.create_proposal(
            conn,
            project_id=project_id,
            proposal_id=proposal["id"],
            title=proposal["title"],
            requirements_id=requirements["id"],
            data=proposal["data"],
        )

        shape = item["shape"]
        repository.create_shape(
            conn,
            project_id=project_id,
            shape_id=shape["id"],
            title=shape["title"],
            requirements_id=requirements["id"],
            data=shape["data"],
        )

        evaluation = item["evaluation"]
        input_snapshot = {
            "requirements": requirements["data"],
            "proposal": proposal["data"],
            "scenario": scenario["data"],
        }
        repository.create_evaluation(
            conn,
            project_id=project_id,
            eval_id=evaluation["id"],
            proposal_id=proposal["id"],
            scenario_id=scenario["id"],
            requirements_id=requirements["id"],
            source=evaluation["source"],
            data=evaluation["data"],
            input_snapshot=input_snapshot,
            shape_id=shape["id"],
        )

        created += 1

    return {"created_projects": created, "skipped": skipped}
