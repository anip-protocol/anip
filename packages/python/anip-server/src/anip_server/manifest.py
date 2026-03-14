"""Manifest builder for ANIP services."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

from anip_core import (
    ANIPManifest,
    CapabilityDeclaration,
    ManifestMetadata,
    ProfileVersions,
    ServiceIdentity,
    TrustPosture,
    PROTOCOL_VERSION,
    DEFAULT_PROFILE,
)


def build_manifest(
    *,
    capabilities: dict[str, CapabilityDeclaration],
    trust: TrustPosture,
    service_identity: ServiceIdentity,
    expires_days: int = 30,
) -> ANIPManifest:
    """Build an ANIP manifest from parameters (no env-var parsing)."""
    manifest = ANIPManifest(
        protocol=PROTOCOL_VERSION,
        profile=ProfileVersions(**DEFAULT_PROFILE),
        capabilities=capabilities,
        service_identity=service_identity,
        trust=trust,
    )

    caps_json = json.dumps(
        {k: v.model_dump() for k, v in capabilities.items()},
        sort_keys=True,
    ).encode()
    now = datetime.now(timezone.utc)
    manifest.manifest_metadata = ManifestMetadata(
        sha256=hashlib.sha256(caps_json).hexdigest(),
        issued_at=now.isoformat(),
        expires_at=(now + timedelta(days=expires_days)).isoformat(),
    )

    return manifest
