from __future__ import annotations

import app


def test_capability_metadata_preserves_generated_kit_precedence(monkeypatch) -> None:
    monkeypatch.setattr(
        app,
        "_metadata_from_agent_consumability",
        lambda: {
            "demo.capability": {
                "app_boundaries": {
                    "unsupported_effects": ["raw_data_export"],
                    "unsupported_terms": {
                        "raw_data_export": [
                            "generated boundary",
                            "generated explicit denial phrase",
                        ],
                    },
                },
                "business_effects": {"does_not_produce": ["raw_data_export"]},
            },
        },
    )
    monkeypatch.setitem(
        app.APP_PROFILE,
        "capability_metadata",
        {
            "demo.capability": {
                "app_boundaries": {
                    "unsupported_terms": {
                        "raw_data_export": ["stale module boundary"],
                    },
                },
                "reference_catalogs": {
                    "target_ref": ["Acme Corporation"],
                },
            },
        },
    )

    metadata = app._capability_metadata()["demo.capability"]

    assert metadata["app_boundaries"]["unsupported_terms"]["raw_data_export"] == [
        "generated boundary",
        "generated explicit denial phrase",
    ]
    assert metadata["reference_catalogs"] == {"target_ref": ["Acme Corporation"]}
