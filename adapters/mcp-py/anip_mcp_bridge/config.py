"""Bridge configuration — load from YAML or environment."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class DelegationConfig:
    """Delegation token configuration for the bridge."""

    issuer: str = "human:user@example.com"
    scope: list[str] = field(default_factory=lambda: ["*"])
    token_ttl_minutes: int = 60


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
                issuer=os.environ.get(
                    "ANIP_ISSUER", "human:user@example.com"
                ),
                scope=os.environ.get("ANIP_SCOPE", "*").split(","),
            ),
        )

    # Load from YAML
    with open(config_path) as f:
        data = yaml.safe_load(f)

    delegation_data = data.get("delegation", {})
    delegation = DelegationConfig(
        issuer=delegation_data.get("issuer", "human:user@example.com"),
        scope=delegation_data.get("scope", ["*"]),
        token_ttl_minutes=delegation_data.get("token_ttl_minutes", 60),
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
