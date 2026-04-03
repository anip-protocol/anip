"""Seed the database from example packs in tooling/examples/."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from . import repository

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "tooling" / "examples"


def _load_yaml(path: Path) -> dict:
    """Load a YAML file and return its contents as a dict."""
    with open(path) as f:
        return yaml.safe_load(f) or {}


def seed_from_examples(conn: Any) -> dict:
    """Import example packs into the database as seed projects.

    One project is created per pack directory.  Existing projects
    (matched by ID) are silently skipped, making this function
    idempotent.

    Returns ``{"created_projects": N, "skipped": N}``.
    """
    if not EXAMPLES_DIR.is_dir():
        return {"created_projects": 0, "skipped": 0}

    created = 0
    skipped = 0

    for pack_dir in sorted(EXAMPLES_DIR.iterdir()):
        if not pack_dir.is_dir():
            continue

        pack = pack_dir.name
        req_path = pack_dir / "requirements.yaml"
        if not req_path.exists():
            continue

        # Check whether the project already exists
        try:
            repository.get_project(conn, pack)
            skipped += 1
            continue
        except repository.NotFoundError:
            pass  # project does not exist — create it

        # Load artifacts
        requirements_data = _load_yaml(req_path)
        scenario_data = _load_yaml(pack_dir / "scenario.yaml") if (pack_dir / "scenario.yaml").exists() else {}
        proposal_data = _load_yaml(pack_dir / "proposal.yaml") if (pack_dir / "proposal.yaml").exists() else {}
        evaluation_data = _load_yaml(pack_dir / "evaluation.yaml") if (pack_dir / "evaluation.yaml").exists() else {}

        # Derive project metadata from requirements
        system = requirements_data.get("system", {})
        project_name = system.get("name", pack)
        project_domain = system.get("domain", "")

        # Create project
        repository.create_project(
            conn,
            project_id=pack,
            name=project_name,
            summary=f"Imported from example pack: {pack}",
            domain=project_domain,
        )

        # Create requirements set
        req_id = f"req-{pack}"
        req_title = f"{project_name} requirements"
        repository.create_requirements(
            conn,
            project_id=pack,
            req_id=req_id,
            title=req_title,
            data=requirements_data,
        )

        # Create scenario
        scn_id = f"scn-{pack}"
        scn_name = scenario_data.get("scenario", {}).get("name", f"{pack} scenario")
        repository.create_scenario(
            conn,
            project_id=pack,
            scenario_id=scn_id,
            title=scn_name,
            data=scenario_data,
        )

        # Create approach
        prop_id = f"prop-{pack}"
        prop_title = f"{project_name} approach"
        repository.create_proposal(
            conn,
            project_id=pack,
            proposal_id=prop_id,
            title=prop_title,
            requirements_id=req_id,
            data=proposal_data,
        )

        # Create evaluation with frozen input_snapshot
        eval_id = f"eval-{pack}"
        input_snapshot = {
            "requirements": requirements_data,
            "proposal": proposal_data,
            "scenario": scenario_data,
        }
        repository.create_evaluation(
            conn,
            project_id=pack,
            eval_id=eval_id,
            proposal_id=prop_id,
            scenario_id=scn_id,
            requirements_id=req_id,
            source="imported",
            data=evaluation_data,
            input_snapshot=input_snapshot,
        )

        created += 1

    return {"created_projects": created, "skipped": skipped}
