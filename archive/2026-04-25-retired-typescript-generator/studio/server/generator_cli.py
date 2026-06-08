from __future__ import annotations

import json
import mimetypes
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PACKAGES_TYPESCRIPT_DIR = ROOT / "packages" / "typescript"
GENERATOR_DIST_CLI = PACKAGES_TYPESCRIPT_DIR / "generator" / "dist" / "cli.js"


def _ensure_typescript_generator_built() -> None:
    if GENERATOR_DIST_CLI.exists():
        return
    subprocess.run(
        ["npm", "run", "build", "--workspace", "@anip-dev/generator-typescript"],
        cwd=PACKAGES_TYPESCRIPT_DIR,
        check=True,
        capture_output=True,
        text=True,
    )
    if not GENERATOR_DIST_CLI.exists():
        raise RuntimeError("TypeScript generator CLI was not produced after build.")


def _content_type_for_path(file_path: str) -> str:
    if file_path.endswith(".ts"):
        return "typescript"
    if file_path.endswith(".json"):
        return "json"
    if file_path.endswith(".md"):
        return "markdown"
    guessed, _ = mimetypes.guess_type(file_path)
    return guessed or "text"


def _normalize_service_definition(definition: dict[str, Any]) -> dict[str, Any]:
    if definition.get("kind") != "developer_definition":
        return definition

    compiled_identity = definition.get("identity") or {}
    source = definition.get("source") or {}
    developer_definition = source.get("developer_definition") or {}
    project = definition.get("project") or {}
    normalized_identity = developer_definition.get("identity") or {}
    normalized_generation = developer_definition.get("generation") or {}

    return {
        "artifact_type": developer_definition.get("artifact_type") or "anip_service_definition",
        "contract_schema_version": developer_definition.get("contract_schema_version") or "anip-service-definition/v1",
        "compiled_contract_identity": {
            "signature": compiled_identity.get("signature"),
            "signature_algorithm": compiled_identity.get("signature_algorithm"),
        },
        "identity": {
            "system_name": normalized_identity.get("system_name") or project.get("name"),
            "domain_name": normalized_identity.get("domain_name") or project.get("domain"),
            "delivery_model": normalized_identity.get("delivery_model"),
            "architecture_shape": normalized_identity.get("architecture_shape"),
        },
        "authority": developer_definition.get("authority") or {},
        "audit": developer_definition.get("audit") or {},
        "generation": {
            "protocols": normalized_generation.get("protocols") or [],
            "layout_strategy": normalized_generation.get("layout_strategy"),
            "selected_service_ids": normalized_generation.get("selected_service_ids") or [],
        },
        "service_topology_bindings": developer_definition.get("service_topology_bindings") or [],
        "capability_formalizations": developer_definition.get("capability_formalizations") or [],
        "integration_fronting": developer_definition.get("integration_fronting") or {"project_type": None, "capability_mappings": []},
    }


def generate_typescript_service_project(
    definition: dict[str, Any],
    package_name: str | None = None,
    dependency_source: str = "registry",
) -> dict[str, Any]:
    _ensure_typescript_generator_built()
    normalized_definition = _normalize_service_definition(definition)

    generated_at = datetime.now(timezone.utc).isoformat()
    with TemporaryDirectory(prefix="anip-ts-generator-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        definition_path = tmp_path / "anip-service-definition.json"
        output_dir = tmp_path / "generated"
        definition_path.write_text(json.dumps(normalized_definition, indent=2), encoding="utf-8")

        command = [
            "node",
            str(GENERATOR_DIST_CLI),
            "--definition",
            str(definition_path),
            "--output",
            str(output_dir),
            "--force",
        ]
        if package_name:
            command.extend(["--package-name", package_name])
        command.extend(["--dependency-source", dependency_source])

        result = subprocess.run(
            command,
            cwd=PACKAGES_TYPESCRIPT_DIR,
            check=True,
            capture_output=True,
            text=True,
        )
        summary = json.loads(result.stdout) if result.stdout.strip() else {}

        files: list[dict[str, Any]] = []
        for generated_file in sorted(output_dir.rglob("*")):
            if not generated_file.is_file():
                continue
            relative_path = generated_file.relative_to(output_dir).as_posix()
            content = generated_file.read_text(encoding="utf-8")
            files.append(
                {
                    "path": relative_path,
                    "content": content,
                    "content_type": _content_type_for_path(relative_path),
                    "content_length": len(content),
                }
            )

        return {
            "generated_at": generated_at,
            "system_name": summary.get("system_name") or normalized_definition.get("identity", {}).get("system_name"),
            "package_name": summary.get("package_name") or package_name,
            "file_count": len(files),
            "files": files,
        }
