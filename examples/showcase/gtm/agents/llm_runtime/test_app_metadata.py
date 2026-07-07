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


def test_effect_mismatch_validation_failure_becomes_unsupported_plan() -> None:
    plan = {
        "selected_capability": "gtm.lookalike_accounts",
        "parameters": {"reference_account": "Globex"},
        "unsupported": False,
    }

    unsupported = app._unsupported_plan_from_validation_failure(
        plan,
        "selected capability does not produce requested primary effect: content.draft",
    )

    assert unsupported is not None
    assert unsupported["selected_capability"] == "gtm.lookalike_accounts"
    assert unsupported["parameters"] == {"reference_account": "Globex"}
    assert unsupported["unsupported"] is True
    assert "content.draft" in unsupported["unsupported_reason"]


def test_non_effect_validation_failure_stays_retryable_or_error() -> None:
    plan = {
        "selected_capability": "gtm.draft_outreach_message",
        "parameters": {},
        "unsupported": False,
    }

    assert app._unsupported_plan_from_validation_failure(
        plan,
        "missing required input(s) appear present but unbound: target_ref",
    ) is None
