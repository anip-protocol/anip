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
