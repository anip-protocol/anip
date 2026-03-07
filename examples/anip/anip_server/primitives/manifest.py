"""Manifest and profile handshake."""

from __future__ import annotations

from ..capabilities import search_flights, book_flight
from .models import ANIPManifest, ProfileVersions


def build_manifest() -> ANIPManifest:
    capabilities = {
        "search_flights": search_flights.DECLARATION,
        "book_flight": book_flight.DECLARATION,
    }

    return ANIPManifest(
        protocol="anip/1.0",
        profile=ProfileVersions(
            core="1.0",
            cost="1.0",
            capability_graph="1.0",
            state_session="1.0",
            observability="1.0",
        ),
        capabilities=capabilities,
    )
