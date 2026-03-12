"""Bridge configuration — load from YAML or environment."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class DelegationConfig:
    """Delegation token configuration for the bridge."""

    scope: list[str] = field(default_factory=lambda: ["*"])
    api_key: str = "demo-human-key"


@dataclass
class BridgeConfig:
    """Full bridge configuration."""

    anip_service_url: str = "http://localhost:8000"
    delegation: DelegationConfig = field(default_factory=DelegationConfig)
    enrich_descriptions: bool = True
    transport: str = "stdio"  # "stdio" or "sse"
    port: int = 3000  # only used for SSE transport


def load_config(config_path: str | None = None) -> BridgeConfig:
    """Load bridge configuration from YAML file or environment variables.

    Priority: explicit path > ANIP_BRIDGE_CONFIG env var > ./bridge.yaml > defaults
    """
    # Find config file
    if config_path is None:
        config_path = os.environ.get("ANIP_BRIDGE_CONFIG")
    if config_path is None:
        default_path = Path("bridge.yaml")
        if default_path.exists():
            config_path = str(default_path)

    if config_path is None:
        # Use environment variables or defaults
        return BridgeConfig(
            anip_service_url=os.environ.get(
                "ANIP_SERVICE_URL", "http://localhost:8000"
            ),
            delegation=DelegationConfig(
                scope=os.environ.get("ANIP_SCOPE", "*").split(","),
                api_key=os.environ.get("ANIP_API_KEY", "demo-human-key"),
            ),
        )

    # Load from YAML
    with open(config_path) as f:
        data = yaml.safe_load(f)

    delegation_data = data.get("delegation", {})
    delegation = DelegationConfig(
        scope=delegation_data.get("scope", ["*"]),
        api_key=delegation_data.get("api_key", "demo-human-key"),
    )

    return BridgeConfig(
        anip_service_url=data.get(
            "anip_service_url", "http://localhost:8000"
        ),
        delegation=delegation,
        enrich_descriptions=data.get("enrich_descriptions", True),
        transport=data.get("transport", "stdio"),
        port=data.get("port", 3000),
    )
