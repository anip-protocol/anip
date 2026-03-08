"""ANIP service discovery and manifest fetching."""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx


@dataclass
class ANIPCapability:
    """A discovered ANIP capability with full metadata."""

    name: str
    description: str
    side_effect: str
    rollback_window: str | None
    minimum_scope: list[str]
    financial: bool
    contract_version: str
    inputs: list[dict]
    output: dict
    cost: dict | None
    requires: list[dict]


@dataclass
class ANIPService:
    """A discovered ANIP service."""

    base_url: str
    protocol: str
    compliance: str
    endpoints: dict[str, str]
    capabilities: dict[str, ANIPCapability]
    profiles: dict[str, str] = field(default_factory=dict)


async def discover_service(anip_url: str) -> ANIPService:
    """Discover an ANIP service from its base URL.

    Follows the standard ANIP flow:
    1. Fetch /.well-known/anip
    2. Fetch full manifest from the declared endpoint
    3. Return structured service description
    """
    async with httpx.AsyncClient(timeout=30) as client:
        # Step 1: Discovery document
        discovery_url = f"{anip_url.rstrip('/')}/.well-known/anip"
        resp = await client.get(discovery_url)
        resp.raise_for_status()
        discovery = resp.json()["anip_discovery"]

        base_url = discovery["base_url"]
        endpoints = discovery["endpoints"]

        # Step 2: Full manifest
        manifest_url = _resolve_url(base_url, endpoints["manifest"])
        resp = await client.get(manifest_url)
        resp.raise_for_status()
        manifest = resp.json()

        # Step 3: Build capability objects from manifest
        capabilities = {}
        for name, cap in manifest["capabilities"].items():
            capabilities[name] = ANIPCapability(
                name=name,
                description=cap["description"],
                side_effect=cap["side_effect"]["type"],
                rollback_window=cap["side_effect"].get("rollback_window"),
                minimum_scope=cap.get("minimum_scope", cap.get("required_scope", [])),
                financial=cap.get("cost", {}).get("financial") is not None,
                contract_version=cap.get("contract_version", "1.0"),
                inputs=cap.get("inputs", []),
                output=cap.get("output", {}),
                cost=cap.get("cost"),
                requires=cap.get("requires", []),
            )

        # Resolve all endpoint URLs
        resolved_endpoints = {
            k: _resolve_url(base_url, v) for k, v in endpoints.items()
        }

        return ANIPService(
            base_url=base_url,
            protocol=discovery["protocol"],
            compliance=discovery.get("compliance", "anip-compliant"),
            endpoints=resolved_endpoints,
            capabilities=capabilities,
            profiles=discovery.get("profile", {}),
        )


def _resolve_url(base_url: str, path: str) -> str:
    """Resolve a relative endpoint path against the base URL."""
    if path.startswith("http"):
        return path
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"
