from anip_service.classification import classify_event


def test_write_success_is_high_risk_success():
    assert classify_event("write", True, None) == "high_risk_success"


def test_irreversible_success_is_high_risk_success():
    assert classify_event("irreversible", True, None) == "high_risk_success"


def test_transactional_success_is_high_risk_success():
    assert classify_event("transactional", True, None) == "high_risk_success"


def test_read_success_is_low_risk_success():
    assert classify_event("read", True, None) == "low_risk_success"


def test_write_scope_insufficient_is_high_risk_denial():
    assert classify_event("write", False, "scope_insufficient") == "high_risk_denial"


def test_read_invalid_token_is_high_risk_denial():
    assert classify_event("read", False, "invalid_token") == "high_risk_denial"


def test_read_scope_insufficient_is_high_risk_denial():
    assert classify_event("read", False, "scope_insufficient") == "high_risk_denial"


def test_read_insufficient_authority_is_high_risk_denial():
    assert classify_event("read", False, "insufficient_authority") == "high_risk_denial"


def test_null_side_effect_unknown_capability_is_malformed():
    assert classify_event(None, False, "unknown_capability") == "malformed_or_spam"


def test_read_streaming_not_supported_is_malformed():
    assert classify_event("read", False, "streaming_not_supported") == "malformed_or_spam"


def test_write_internal_error_is_malformed():
    assert classify_event("write", False, "internal_error") == "malformed_or_spam"


def test_null_side_effect_invalid_token_is_malformed_pre_resolution():
    assert classify_event(None, False, "invalid_token") == "malformed_or_spam"


def test_null_side_effect_unknown_capability_is_malformed_pre_resolution():
    assert classify_event(None, False, "unknown_capability") == "malformed_or_spam"


def test_write_not_found_is_high_risk_denial():
    assert classify_event("write", False, "not_found") == "high_risk_denial"


def test_read_not_found_is_high_risk_denial():
    assert classify_event("read", False, "not_found") == "high_risk_denial"
