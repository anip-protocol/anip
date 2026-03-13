"""Manifest and profile handshake."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone

from ..capabilities import search_flights, book_flight
from .models import (
    ANIPManifest,
    AnchoringPolicy,
    ManifestMetadata,
    ProfileVersions,
    ServiceIdentity,
    TrustPosture,
)


def build_manifest() -> ANIPManifest:
    capabilities = {
        "search_flights": search_flights.DECLARATION,
        "book_flight": book_flight.DECLARATION,
    }

    # Build trust posture from environment
    trust_level = os.environ.get("ANIP_TRUST_LEVEL", "signed")
    anchoring = None
    if trust_level in ("anchored", "attested"):
        # cadence: ISO 8601 duration for max time between checkpoints
        # Derived from ANIP_CHECKPOINT_INTERVAL (seconds) if set
        interval_env = os.environ.get("ANIP_CHECKPOINT_INTERVAL")
        cadence = f"PT{interval_env}S" if interval_env else None
        # max_lag: max uncheckpointed entry count from ANIP_CHECKPOINT_CADENCE
        cadence_env = os.environ.get("ANIP_CHECKPOINT_CADENCE")
        max_lag = int(cadence_env) if cadence_env else None
        # sink: qualifying URIs required for anchored (file:// is dev-only)
        sink_env = os.environ.get("ANIP_CHECKPOINT_SINK")
        sink = [s.strip() for s in sink_env.split(",")] if sink_env else None
        anchoring = AnchoringPolicy(
            cadence=cadence,
            max_lag=max_lag,
            sink=sink,
        )
    trust = TrustPosture(level=trust_level, anchoring=anchoring)

    manifest = ANIPManifest(
        protocol="anip/0.3",
        profile=ProfileVersions(
            core="1.0",
            cost="1.0",
            capability_graph="1.0",
            state_session="1.0",
            observability="1.0",
        ),
        capabilities=capabilities,
        service_identity=ServiceIdentity(),
        trust=trust,
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
