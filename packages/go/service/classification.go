package service

// ClassifyEvent assigns an event class to an audit entry based on
// side-effect type, success/failure, and failure type.
// Implements SPEC §6.8 event classification.
func ClassifyEvent(sideEffectType string, success bool, failureType string) string {
	if sideEffectType == "" {
		return "malformed_or_spam"
	}
	if success {
		if isHighRiskSideEffect(sideEffectType) {
			return "high_risk_success"
		}
		return "low_risk_success"
	}
	if isMalformedFailureType(failureType) {
		return "malformed_or_spam"
	}
	return "high_risk_denial"
}

func isHighRiskSideEffect(se string) bool {
	return se == "write" || se == "irreversible" || se == "transactional"
}

func isMalformedFailureType(ft string) bool {
	return ft == "unknown_capability" || ft == "streaming_not_supported" || ft == "internal_error"
}
