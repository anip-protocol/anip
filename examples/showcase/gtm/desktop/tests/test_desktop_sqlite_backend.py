"""The desktop app runs the generated Python service against the bundled SQLite marts.

The sidecar sets DATABASE_URL to sqlite:///<bundled gtm_desktop.sqlite>; the
generated backend adapter has to answer from that file, with no Postgres.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GENERATED_SRC = ROOT.parents[0] / "generated" / "language-parity" / "python" / "src"
FULL_ACCESS_ACTOR = {"pipeline_scope": "company", "financial_access": "full"}


@pytest.fixture(scope="module")
def sqlite_adapter(tmp_path_factory):
    spec = importlib.util.spec_from_file_location("build_desktop_data", ROOT / "scripts" / "build_desktop_data.py")
    assert spec and spec.loader
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    database = builder.build_database(tmp_path_factory.mktemp("desktop") / "gtm_desktop.sqlite")

    sys.path.insert(0, str(GENERATED_SRC))
    try:
        adapter = importlib.import_module("gtm_pipeline_q2_review.backend_adapter")
    finally:
        sys.path.remove(str(GENERATED_SRC))
    previous = adapter.DATABASE_URL
    adapter.DATABASE_URL = f"sqlite:///{database}"
    yield adapter
    adapter.DATABASE_URL = previous


@pytest.mark.parametrize(
    "capability",
    [
        "pipeline_summary",
        "forecast_summary",
        "stage_bottleneck_summary",
        "sales_team_performance_summary",
        "product_pipeline_summary",
        "stalled_opportunities",
        "account_risk_summary",
    ],
)
def test_pipeline_capabilities_answer_from_the_bundled_sqlite_marts(sqlite_adapter, capability):
    result = getattr(sqlite_adapter, capability)({"quarter": "2017-Q2"}, FULL_ACCESS_ACTOR)
    assert result["execution_status"] == "completed"
    assert result["quarter"] == "2017-Q2"


def test_pipeline_summary_counts_the_quarter_from_sqlite(sqlite_adapter):
    result = sqlite_adapter.pipeline_summary({"quarter": "2017-Q2"}, FULL_ACCESS_ACTOR)
    assert result["totals"]["opportunity_count"] > 0
    assert {row["deal_stage"] for row in result["by_stage"]}


def test_account_enrichment_reads_named_accounts_from_sqlite(sqlite_adapter):
    # account_name = any($1) is the one query whose parameters change shape for SQLite.
    result = sqlite_adapter.account_enrichment({"account_names": "Acme Corporation"}, FULL_ACCESS_ACTOR)
    assert result["execution_status"] == "completed"
    assert "Acme Corporation" in str(result)
