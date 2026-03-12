"""Manifest and profile handshake."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

from ..capabilities import search_flights, book_flight
from .models import ANIPManifest, ManifestMetadata, ProfileVersions, ServiceIdentity


def build_manifest() -> ANIPManifest:
    capabilities = {
        "search_flights": search_flights.DECLARATION,
        "book_flight": book_flight.DECLARATION,
    }

    manifest = ANIPManifest(
        protocol="anip/0.2",
        profile=ProfileVersions(
            core="1.0",
            cost="1.0",
            capability_graph="1.0",
            state_session="1.0",
            observability="1.0",
        ),
        capabilities=capabilities,
        service_identity=ServiceIdentity(),
    )

    # Compute sha256 over capabilities (excluding metadata itself)
    caps_json = json.dumps(
        {k: v.model_dump() for k, v in capabilities.items()},
        sort_keys=True,
    ).encode()
    now = datetime.now(timezone.utc)
    manifest.manifest_metadata = ManifestMetadata(
        sha256=hashlib.sha256(caps_json).hexdigest(),
        issued_at=now.isoformat(),
        expires_at=(now + timedelta(days=30)).isoformat(),
    )

    return manifest
