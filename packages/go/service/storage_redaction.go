package service

import "maps"

// StorageRedactEntry strips parameters from low-value audit entries
// before persistence. Implements SPEC §6.10.
// Returns a shallow copy — does not mutate the input.
func StorageRedactEntry(entry map[string]any) map[string]any {
	result := make(map[string]any, len(entry))
	maps.Copy(result, entry)

	ec, _ := result["event_class"].(string)
	if isLowValueClass(ec) {
		result["parameters"] = nil
		result["storage_redacted"] = true
	} else {
		result["storage_redacted"] = false
	}
	return result
}

func isLowValueClass(ec string) bool {
	return ec == "low_risk_success" || ec == "malformed_or_spam" || ec == "repeated_low_value_denial"
}
