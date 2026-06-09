#!/usr/bin/env python3
"""Verify public Studio showcase seeds match registry release artifacts.

This is a release gate, not a unit test. It intentionally compares the
artifacts people will see in the hosted read-only Studio with the packages and
templates we publish to the registry.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_VERSION = "anip/0.24"
TEMPLATE_VERSION = "0.1.0"

FRONTING_PACKAGE_VERSIONS = {
    "github": "0.2.0",
    "gitlab": "0.2.0",
    "jira": "0.2.0",
    "linear": "0.2.0",
    "notion": "0.2.0",
    "slack": "0.2.0",
    "superset": "0.2.0",
}

GTm_PACKAGE_ID = "gtm-pipeline-q2-review"
GTM_PACKAGE_VERSION = "0.4.1"


class ReleaseParityError(Exception):
    pass


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ReleaseParityError(f"missing file: {path.relative_to(REPO_ROOT)}") from exc


def load_seed_projects() -> list[dict[str, Any]]:
    seed_path = REPO_ROOT / "studio/server/seed_catalog.py"
    spec = importlib.util.spec_from_file_location("studio_seed_catalog_for_parity", seed_path)
    if spec is None or spec.loader is None:
        raise ReleaseParityError(f"failed to load seed catalog: {seed_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    projects = getattr(module, "SEED_PROJECTS", None)
    if not isinstance(projects, list):
        raise ReleaseParityError("studio/server/seed_catalog.py does not expose SEED_PROJECTS")
    return projects


def normalize_signature(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("signature") or value.get("contract_signature")
    text = str(value or "").strip()
    return text.removeprefix("sha256:")


def capability_ids_from_service_definition(definition: dict[str, Any]) -> list[str]:
    capabilities = definition.get("capability_formalizations")
    if not isinstance(capabilities, list):
        return []
    return sorted(str(item.get("capability_id", "")).strip() for item in capabilities if item.get("capability_id"))


def capability_ids_from_template(template: dict[str, Any]) -> list[str]:
    mappings = template.get("capabilityMappings")
    if not isinstance(mappings, list):
        return []
    ids: list[str] = []
    for mapping in mappings:
        data = mapping.get("data") if isinstance(mapping, dict) else None
        if isinstance(data, dict) and data.get("capability_id"):
            ids.append(str(data["capability_id"]).strip())
    return sorted(ids)


def input_names_by_capability(definition: dict[str, Any]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for capability in definition.get("capability_formalizations", []) or []:
        capability_id = str(capability.get("capability_id") or "").strip()
        if not capability_id:
            continue
        inputs = capability.get("inputs") or []
        result[capability_id] = sorted(
            str(item.get("input_name") or "").strip()
            for item in inputs
            if isinstance(item, dict) and item.get("input_name")
        )
    return result


def input_names_by_template_capability(template: dict[str, Any]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for mapping in template.get("capabilityMappings", []) or []:
        data = mapping.get("data") if isinstance(mapping, dict) else None
        if not isinstance(data, dict):
            continue
        capability_id = str(data.get("capability_id") or "").strip()
        if not capability_id:
            continue
        result[capability_id] = sorted(
            str(item.get("input_name") or "").strip()
            for item in data.get("inputs", []) or []
            if isinstance(item, dict) and item.get("input_name")
        )
    return result


def source_input_scenario_ids(artifact: dict[str, Any] | None) -> list[str]:
    if not isinstance(artifact, dict):
        return []
    source_inputs = artifact.get("source_inputs")
    if not isinstance(source_inputs, dict):
        return []
    return [str(item) for item in (source_inputs.get("scenario_ids") or [])]


def package_scenario_pack_ids(definition: dict[str, Any]) -> list[str]:
    baseline = ((definition.get("source") or {}).get("product_design_baseline") or {})
    scenario_pack = baseline.get("scenario_pack") if isinstance(baseline, dict) else None
    if not isinstance(scenario_pack, list):
        return []
    return [str(item.get("id")) for item in scenario_pack if isinstance(item, dict) and item.get("id")]


def assert_equal(label: str, actual: Any, expected: Any, errors: list[str]) -> None:
    if actual != expected:
        errors.append(f"{label}: expected {expected!r}, got {actual!r}")


def assert_set_equal(label: str, actual: list[str], expected: list[str], errors: list[str]) -> None:
    actual_set = set(actual)
    expected_set = set(expected)
    if actual_set == expected_set:
        return
    missing = sorted(expected_set - actual_set)
    extra = sorted(actual_set - expected_set)
    detail = []
    if missing:
        detail.append(f"missing {missing}")
    if extra:
        detail.append(f"extra {extra}")
    errors.append(f"{label}: {'; '.join(detail)}")


def verify_package_bundle(package_path: Path, package_id: str, package_version: str, errors: list[str]) -> dict[str, Any]:
    bundle = load_json(package_path)
    rel = package_path.relative_to(REPO_ROOT)
    manifest = bundle.get("manifest") or {}
    package = bundle.get("package") or {}
    service_definition = bundle.get("service_definition") or {}
    lock = bundle.get("lock") or {}

    assert_equal(f"{rel} manifest.package_id", manifest.get("package_id"), package_id, errors)
    assert_equal(f"{rel} manifest.package_version", manifest.get("package_version"), package_version, errors)
    assert_equal(f"{rel} manifest.anip_spec_version", manifest.get("anip_spec_version"), SPEC_VERSION, errors)
    assert_equal(f"{rel} package.package_id", package.get("package_id"), package_id, errors)
    assert_equal(f"{rel} package.package_version", package.get("package_version"), package_version, errors)
    assert_equal(f"{rel} lock.anip_spec_version", lock.get("anip_spec_version"), SPEC_VERSION, errors)

    sidecar = package_path.with_name(package_path.name.replace(".anip-package.json", "-service-definition.json"))
    if sidecar.exists():
        sidecar_definition = load_json(sidecar)
        if sidecar_definition != service_definition:
            errors.append(f"{sidecar.relative_to(REPO_ROOT)} does not match embedded package service_definition")
    else:
        errors.append(f"missing service-definition sidecar for {rel}")

    capability_ids = capability_ids_from_service_definition(service_definition)
    assert_equal(f"{rel} manifest.capability_count", manifest.get("capability_count"), len(capability_ids), errors)
    lock_capability_ids = sorted(str(item) for item in (lock.get("capability_ids") or []))
    assert_set_equal(f"{rel} lock.capability_ids", lock_capability_ids, capability_ids, errors)
    return bundle


def verify_fronting_showcase(system: str, errors: list[str]) -> None:
    package_version = FRONTING_PACKAGE_VERSIONS[system]
    package_id = f"{system}-fronting-showcase"
    package_path = (
        REPO_ROOT
        / "examples/showcase"
        / f"{system}_fronting"
        / "registry-packages"
        / f"{package_id}-{package_version}.anip-package.json"
    )
    bundle = verify_package_bundle(package_path, package_id, package_version, errors)
    service_definition = bundle.get("service_definition") or {}
    package_capabilities = capability_ids_from_service_definition(service_definition)
    package_inputs = input_names_by_capability(service_definition)

    template_path = (
        REPO_ROOT
        / "examples/showcase/templates/registry-templates"
        / f"{system}-fronting-starter-{TEMPLATE_VERSION}.anip-template.json"
    )
    if not template_path.exists():
        errors.append(
            f"{system}: seeded fronting project has package {package_id}@{package_version} "
            f"but no registry template {template_path.relative_to(REPO_ROOT)}"
        )
        return

    template_request = load_json(template_path)
    manifest = template_request.get("manifest") or {}
    template = template_request.get("template") or {}
    assert_equal(f"{template_path.relative_to(REPO_ROOT)} template_id", template_request.get("template_id"), f"{system}-fronting-starter", errors)
    assert_equal(f"{template_path.relative_to(REPO_ROOT)} template_version", template_request.get("template_version"), TEMPLATE_VERSION, errors)
    assert_equal(f"{template_path.relative_to(REPO_ROOT)} manifest.anip_spec_version", manifest.get("anip_spec_version"), SPEC_VERSION, errors)
    assert_equal(f"{template_path.relative_to(REPO_ROOT)} template.anipSpecVersion", template.get("anipSpecVersion"), SPEC_VERSION, errors)

    template_capabilities = capability_ids_from_template(template)
    assert_set_equal(f"{system} template/package capabilities", template_capabilities, package_capabilities, errors)

    template_inputs = input_names_by_template_capability(template)
    for capability_id in sorted(set(template_inputs) & set(package_inputs)):
        assert_set_equal(
            f"{system} {capability_id} template/package inputs",
            template_inputs[capability_id],
            package_inputs[capability_id],
            errors,
        )


def verify_gtm(seed_projects: list[dict[str, Any]], errors: list[str]) -> None:
    seed = next((item for item in seed_projects if item.get("project", {}).get("id") == GTm_PACKAGE_ID), None)
    if seed is None:
        errors.append(f"missing seeded Studio project {GTm_PACKAGE_ID}")
        return

    package_path = (
        REPO_ROOT
        / "examples/showcase/gtm/registry-packages"
        / f"{GTm_PACKAGE_ID}-{GTM_PACKAGE_VERSION}.anip-package.json"
    )
    bundle = verify_package_bundle(package_path, GTm_PACKAGE_ID, GTM_PACKAGE_VERSION, errors)
    service_definition = bundle.get("service_definition") or {}
    package_capabilities = capability_ids_from_service_definition(service_definition)

    lineage_project_ref = str((bundle.get("lineage") or {}).get("project_ref") or "")
    assert_equal(
        f"{package_path.relative_to(REPO_ROOT)} lineage.project_ref",
        lineage_project_ref,
        f"studio:{GTm_PACKAGE_ID}",
        errors,
    )

    seed_artifact_path = REPO_ROOT / str(seed.get("static_pm_artifacts_path") or "")
    seed_artifacts = load_json(seed_artifact_path)
    definition = next(
        (
            item.get("data")
            for item in seed_artifacts
            if isinstance(item, dict)
            and isinstance(item.get("data"), dict)
            and item["data"].get("artifact_type") == "developer_definition"
        ),
        None,
    )
    if not isinstance(definition, dict):
        errors.append(f"{seed_artifact_path.relative_to(REPO_ROOT)} is missing developer_definition")
        return

    package_scenario_order = package_scenario_pack_ids(service_definition)

    for artifact_type in ["developer_baseline", "design_traceability", "developer_definition_revision", "developer_definition"]:
        artifact = next(
            (
                item.get("data")
                for item in seed_artifacts
                if isinstance(item, dict)
                and isinstance(item.get("data"), dict)
                and item["data"].get("artifact_type") == artifact_type
            ),
            None,
        )
        scenario_ids = source_input_scenario_ids(artifact)
        if scenario_ids:
            assert_equal(f"GTM {artifact_type} source_inputs.scenario_ids", scenario_ids, package_scenario_order, errors)

    seed_capabilities = capability_ids_from_service_definition(definition)
    assert_set_equal("GTM seed/package capabilities", seed_capabilities, package_capabilities, errors)

    seed_signature = normalize_signature((definition.get("compiled_contract_identity") or {}).get("signature"))
    package_signature = normalize_signature(service_definition.get("compiled_contract_identity"))
    if seed_signature and package_signature:
        assert_equal("GTM seed/package compiled contract signature", seed_signature, package_signature, errors)

    traceability = next(
        (
            item.get("data")
            for item in seed_artifacts
            if isinstance(item, dict)
            and isinstance(item.get("data"), dict)
            and item["data"].get("artifact_type") == "design_traceability"
        ),
        None,
    )
    readiness = (traceability or {}).get("agent_consumption_readiness") if isinstance(traceability, dict) else None
    summary = readiness.get("summary") if isinstance(readiness, dict) else None
    if not isinstance(summary, dict) or not all(isinstance(summary.get(key), int) for key in ["blockers", "warnings", "info", "probes", "required_app_glue"]):
        errors.append("GTM seed traceability has missing or malformed agent_consumption_readiness.summary")

    for language in ["python", "typescript", "go", "java", "csharp"]:
        definition_path = REPO_ROOT / "examples/showcase/gtm/generated/language-parity" / language / "anip-service-definition.json"
        if not definition_path.exists():
            errors.append(f"missing generated GTM {language} service definition: {definition_path.relative_to(REPO_ROOT)}")
            continue
        generated = load_json(definition_path)
        assert_set_equal(
            f"GTM generated {language} package capabilities",
            capability_ids_from_service_definition(generated),
            package_capabilities,
            errors,
        )


def seeded_fronting_systems(seed_projects: list[dict[str, Any]]) -> list[str]:
    systems = []
    for item in seed_projects:
        project_id = str(item.get("project", {}).get("id") or "")
        match = re.fullmatch(r"([a-z0-9-]+)-fronting-starter", project_id)
        if match:
            systems.append(match.group(1))
    return sorted(systems)


def main() -> int:
    errors: list[str] = []
    seed_projects = load_seed_projects()

    verify_gtm(seed_projects, errors)

    for system in seeded_fronting_systems(seed_projects):
        verify_fronting_showcase(system, errors)

    if errors:
        print("Showcase release parity check FAILED:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Showcase release parity check passed.")
    print(f"- GTM package: {GTm_PACKAGE_ID}@{GTM_PACKAGE_VERSION}")
    print(f"- Fronting systems: {', '.join(seeded_fronting_systems(seed_projects))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
