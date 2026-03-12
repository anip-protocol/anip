"""Adapter configuration — load from YAML or environment."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class GraphQLConfig:
    """GraphQL-specific configuration."""

    path: str = "/graphql"
    playground: bool = True
    introspection: bool = True


@dataclass
class AdapterConfig:
    """Full adapter configuration."""

    anip_service_url: str = "http://localhost:8000"
    port: int = 3002
    graphql: GraphQLConfig = field(default_factory=GraphQLConfig)


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
            port=int(os.environ.get("ANIP_ADAPTER_PORT", "3002")),
        )

    # Load from YAML
    with open(config_path) as f:
        data = yaml.safe_load(f)

    graphql_data = data.get("graphql", {})
    graphql = GraphQLConfig(
        path=graphql_data.get("path", "/graphql"),
        playground=graphql_data.get("playground", True),
        introspection=graphql_data.get("introspection", True),
    )

    return AdapterConfig(
        anip_service_url=data.get(
            "anip_service_url", "http://localhost:8000"
        ),
        port=data.get("port", 3002),
        graphql=graphql,
    )
