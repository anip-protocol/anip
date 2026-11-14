from slack_governed_fronting_showcase.backend_adapter import _channel_allowed, backend_adapter


def test_slack_bundle_declares_current_contract_capability_ids() -> None:
    constants = backend_adapter.__class__.execute.__code__.co_consts
    joined = "\n".join(str(item) for item in constants)
    assert "slack.channel.read_context" in joined
    assert "slack.thread.summarize" in joined
    assert "slack.message.prepare" in joined
    assert "slack.incident_update.prepare" in joined
    assert "slack.announcement.request" in joined


def test_slack_channel_allowlist_policy(monkeypatch) -> None:
    monkeypatch.setenv("ANIP_SLACK_ALLOWED_CHANNELS", "C_ALLOWED,C_OTHER")
    monkeypatch.setenv("ANIP_SLACK_BLOCKED_CHANNELS", "C_BLOCKED")
    assert _channel_allowed("C_ALLOWED") is True
    assert _channel_allowed("C_UNKNOWN") is False
    assert _channel_allowed("C_BLOCKED") is False
