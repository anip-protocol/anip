import importlib
from pathlib import Path


def _load_backend_adapter():
    generated_src = Path(__file__).resolve().parents[1] / "src"
    candidates = sorted(generated_src.glob("*/backend_adapter.py"))
    assert candidates, "expected generated package backend_adapter.py under src/"
    package_name = candidates[0].parent.name
    module = importlib.import_module(f"{package_name}.backend_adapter")
    return module.backend_adapter


def test_jira_bundle_declares_current_contract_capability_ids() -> None:
    backend_adapter = _load_backend_adapter()
    source = backend_adapter.__class__.execute.__code__.co_consts
    joined = "\n".join(str(item) for item in source)
    assert "jira.backlog.search_context" in joined
    assert "jira.issue.get_context" in joined
    assert "jira.incident_bug.prepare" in joined
    assert "jira.story.prepare" in joined
    assert "jira.workflow_transition.request" in joined


def test_backlog_query_stays_inside_its_jql_string_literal(monkeypatch) -> None:
    # A caller-supplied query cannot add its own JQL clauses (for example a
    # second project): quotes and backslashes are escaped inside the literal.
    import asyncio

    for name in ("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    backend_adapter = _load_backend_adapter()
    plan = {"selected_binding": None, "semantic_input": {}, "unresolved_required_backend_inputs": [], "backend_input_contract": {}}
    result = asyncio.run(backend_adapter.execute(
        {"capability_id": "jira.backlog.search_context"},
        plan,
        {"project_key": "ACME", "query": 'x" OR project = "SECRET" OR text ~ "\\'},
        None,
    ))
    assert result["execution_status"] == "backend_not_configured"
    assert result["jql_preview"] == 'project = "ACME" AND text ~ "x\\" OR project = \\"SECRET\\" OR text ~ \\"\\\\" ORDER BY updated DESC'
