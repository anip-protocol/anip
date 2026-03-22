package service

import (
	"fmt"
	"maps"
	"regexp"
	"strconv"
	"time"
)

var defaultClassToTier = map[string]string{
	"high_risk_success":          "long",
	"high_risk_denial":           "medium",
	"low_risk_success":           "short",
	"repeated_low_value_denial":  "aggregate_only",
	"malformed_or_spam":          "short",
}

var defaultTierToDuration = map[string]string{
	"long":           "P365D",
	"medium":         "P90D",
	"short":          "P7D",
	"aggregate_only": "P1D",
}

var durationRE = regexp.MustCompile(`^P(\d+)D$`)

// RetentionPolicy implements the two-layer retention model from SPEC §6.8.
type RetentionPolicy struct {
	classToTier    map[string]string
	tierToDuration map[string]string
}

// NewRetentionPolicy creates a retention policy with optional overrides. Nil maps use defaults.
func NewRetentionPolicy(classOverrides, tierOverrides map[string]string) *RetentionPolicy {
	ct := make(map[string]string, len(defaultClassToTier))
	maps.Copy(ct, defaultClassToTier)
	maps.Copy(ct, classOverrides)
	td := make(map[string]string, len(defaultTierToDuration))
	maps.Copy(td, defaultTierToDuration)
	maps.Copy(td, tierOverrides)
	return &RetentionPolicy{classToTier: ct, tierToDuration: td}
}

// ResolveTier maps an event class to its retention tier.
func (rp *RetentionPolicy) ResolveTier(eventClass string) string {
	if tier, ok := rp.classToTier[eventClass]; ok {
		return tier
	}
	return "short"
}

// ComputeExpiresAt returns an RFC3339 timestamp for when the entry expires.
func (rp *RetentionPolicy) ComputeExpiresAt(tier string, now time.Time) string {
	duration, ok := rp.tierToDuration[tier]
	if !ok || duration == "" {
		return ""
	}
	days, err := parseISODurationDays(duration)
	if err != nil {
		return ""
	}
	return now.AddDate(0, 0, days).Format(time.RFC3339)
}

// DefaultRetention returns the medium-tier duration string for discovery.
func (rp *RetentionPolicy) DefaultRetention() string {
	return rp.tierToDuration["medium"]
}

func parseISODurationDays(d string) (int, error) {
	m := durationRE.FindStringSubmatch(d)
	if m == nil {
		return 0, fmt.Errorf("unsupported ISO 8601 duration: %q", d)
	}
	return strconv.Atoi(m[1])
}
