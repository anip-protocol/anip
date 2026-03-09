"""Adapter configuration — load from YAML or environment."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class DelegationConfig:
    """Delegation token configuration for the adapter."""

    issuer: str = "human:user@example.com"
    scope: list[str] = field(default_factory=lambda: ["*"])
    token_ttl_minutes: int = 60


@dataclass
class RouteOverride:
    """Override for a capability's REST route."""

    path: str
    method: str


@dataclass
class AdapterConfig:
    """Full adapter configuration."""

    anip_service_url: str = "http://localhost:8000"
    port: int = 3001
    delegation: DelegationConfig = field(default_factory=DelegationConfig)
    routes: dict[str, RouteOverride] = field(default_factory=dict)


def load_config(config_path: str | None = None) -> AdapterConfig:
    """Load adapter configuration from YAML file or environment variables.

    Priority: explicit path > ANIP_ADAPTER_CONFIG env var > ./adapter.yaml > defaults
    """
    # Find config file
    if config_path is None:
        config_path = os.environ.get("ANIP_ADAPTER_CONFIG")
    if config_path is None:
        default_path = Path("adapter.yaml")
        if default_path.exists():
            config_path = str(default_path)

    if config_path is None:
        # Use environment variables or defaults
        return AdapterConfig(
            anip_service_url=os.environ.get(
                "ANIP_SERVICE_URL", "http://localhost:8000"
            ),
            port=int(os.environ.get("ANIP_ADAPTER_PORT", "3001")),
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

    routes: dict[str, RouteOverride] = {}
    for cap_name, route_data in data.get("routes", {}).items():
        routes[cap_name] = RouteOverride(
            path=route_data["path"],
            method=route_data.get("method", "POST").upper(),
        )

    return AdapterConfig(
        anip_service_url=data.get(
            "anip_service_url", "http://localhost:8000"
        ),
        port=data.get("port", 3001),
        delegation=delegation,
        routes=routes,
    )
