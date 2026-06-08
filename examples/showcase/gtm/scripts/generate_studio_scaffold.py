"""Generate GTM showcase service scaffolds from Studio seed artifacts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from studio.server.business_developer_bridge import (
    generate_business_packet_from_context,
    seed_data_access_project_from_business_packet,
)
from studio.server.data_access_generation import generate_data_access_bundle
from studio.server.seed_catalog import SEED_PROJECTS


REPO_ROOT = Path(__file__).resolve().parents[4]
SERVICE_CONFIG = {
    "gtm-pipeline-q2-review": {
        "output_dir": REPO_ROOT / "examples" / "showcase" / "gtm" / "generated" / "studio_gtm_pipeline",
        "source_data_module": REPO_ROOT / "examples" / "showcase" / "gtm" / "services" / "gtm_pipeline" / "data.py",
        "docker_dir": "studio_gtm_pipeline",
    },
    "gtm-account-enrichment": {
        "output_dir": REPO_ROOT / "examples" / "showcase" / "gtm" / "generated" / "studio_gtm_enrichment",
        "source_data_module": REPO_ROOT / "examples" / "showcase" / "gtm" / "services" / "gtm_enrichment" / "data.py",
        "docker_dir": "studio_gtm_enrichment",
    },
}


def main() -> None:
    project_id = sys.argv[1] if len(sys.argv) > 1 else "gtm-pipeline-q2-review"
    config = SERVICE_CONFIG[project_id]
    seed = next(item for item in SEED_PROJECTS if item["project"]["id"] == project_id)
    packet = generate_business_packet_from_context(
        {
            "project": seed["project"],
            "requirements": seed["requirements"],
            "scenario": seed["scenario"],
            "shape": seed["shape"],
            "evaluation": seed["evaluation"],
        }
    )
    project, report = seed_data_access_project_from_business_packet(packet)
    bundle = generate_data_access_bundle(project)

    output_dir = config["output_dir"]
    source_data_module = config["source_data_module"]
    source_service_dir = source_data_module.parent
    docker_dir = config["docker_dir"]
    shared_dir = REPO_ROOT / "examples" / "showcase" / "gtm" / "shared"

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / bundle.designPacket.filename).write_text(bundle.designPacket.content)
    (output_dir / bundle.anipCapabilityScaffold.filename).write_text(bundle.anipCapabilityScaffold.content)
    (output_dir / bundle.backendAdapterScaffold.filename).write_text(bundle.backendAdapterScaffold.content)
    (output_dir / bundle.scenarioPackJson.filename).write_text(bundle.scenarioPackJson.content)
    (output_dir / bundle.scenarioManifestJson.filename).write_text(bundle.scenarioManifestJson.content)
    (output_dir / "service_contract.json").write_text(
        json.dumps(project.serviceContract.model_dump(mode="json") if project.serviceContract else {}, indent=2)
    )
    (output_dir / "derivation_report.json").write_text(json.dumps(report.model_dump(mode="json"), indent=2))
    (output_dir / "data.py").write_text(source_data_module.read_text())
    for extension_path in sorted(source_service_dir.glob("*extensions.py")):
        (output_dir / extension_path.name).write_text(extension_path.read_text())
    (output_dir / "README.md").write_text(
        "\n".join(
            [
                f"# Studio-Generated Scaffold: {seed['project']['name']}",
                "",
                "This directory is generated from the seeded GTM Studio design.",
                "It includes the generated ANIP service files plus the concrete showcase data module used by the runtime.",
                "Non-generated extension hooks live in source service files such as backend_extensions.py and are recopied on regeneration.",
                "",
                "Regenerate with:",
                "",
                "```bash",
                f"PYTHONPATH=/Users/samirski/Development/ANIP python3 examples/showcase/gtm/scripts/generate_studio_scaffold.py {project_id}",
                "```",
            ]
        )
    )
    (output_dir / "Dockerfile").write_text(
        "\n".join(
            [
                "from python:3.12-slim",
                "",
                "workdir /workspace",
                "",
                "env PYTHONPATH=/workspace/examples/showcase/gtm",
                "",
                "copy packages/python /workspace/packages/python",
                "copy examples/showcase/gtm/shared /workspace/examples/showcase/gtm/shared",
                f"copy examples/showcase/gtm/generated/{docker_dir} /workspace/examples/showcase/gtm/generated/{docker_dir}",
                "",
                "run pip install --no-cache-dir \\",
                "    -e /workspace/packages/python/anip-core \\",
                "    -e /workspace/packages/python/anip-crypto \\",
                "    -e /workspace/packages/python/anip-server \\",
                "    -e /workspace/packages/python/anip-service \\",
                "    -e /workspace/packages/python/anip-fastapi \\",
                "    uvicorn \\",
                "    psycopg[binary]",
                "",
                f"workdir /workspace/examples/showcase/gtm/generated/{docker_dir}",
                "",
                'cmd ["python", "data_access_service.py"]',
            ]
        )
    )
    shared_output_dir = output_dir / "shared"
    shared_output_dir.mkdir(exist_ok=True)
    for shared_path in shared_dir.iterdir():
        if shared_path.is_file():
            (shared_output_dir / shared_path.name).write_text(shared_path.read_text())


if __name__ == "__main__":
    main()
