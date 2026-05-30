from anip_core import RECOVERY_CLASS_MAP, recovery_class_for_action


def test_request_approval_recovery_class():
    assert RECOVERY_CLASS_MAP["request_approval"] == "wait_then_retry"
    assert recovery_class_for_action("request_approval") == "wait_then_retry"
