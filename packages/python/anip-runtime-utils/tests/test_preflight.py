from anip_runtime_utils.preflight import build_denied_preflight_result, contains_any_phrase


def test_contains_any_phrase_matches_case_insensitively() -> None:
    assert contains_any_phrase("Draft and send it NOW", ["send it now"]) is True


def test_build_denied_preflight_result_has_denied_shape() -> None:
    payload = build_denied_preflight_result(
        question="Send it now.",
        model="gpt-5.4-mini",
        base_url="https://api.openai.com/v1",
        rationale="Direct send is out of scope.",
        user_message="Direct send is not allowed.",
        detail="Direct send is out of scope.",
        resolution_action="request_preview_or_approval",
        resolution_requires="a bounded preview",
    )
    assert payload["anip_result"]["failure"]["type"] == "denied"
    assert payload["loop_counts"]["total_loops"] == 0
