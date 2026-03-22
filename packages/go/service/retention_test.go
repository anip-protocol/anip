package service

import (
	"strings"
	"testing"
	"time"
)

func TestRetentionPolicy_DefaultTiers(t *testing.T) {
	rp := NewRetentionPolicy(nil, nil)
	cases := []struct {
		eventClass string
		wantTier   string
	}{
		{"high_risk_success", "long"},
		{"high_risk_denial", "medium"},
		{"low_risk_success", "short"},
		{"repeated_low_value_denial", "aggregate_only"},
		{"malformed_or_spam", "short"},
		{"unknown_class", "short"},
	}
	for _, tc := range cases {
		got := rp.ResolveTier(tc.eventClass)
		if got != tc.wantTier {
			t.Errorf("ResolveTier(%q) = %q, want %q", tc.eventClass, got, tc.wantTier)
		}
	}
}

func TestRetentionPolicy_ComputeExpiresAt(t *testing.T) {
	rp := NewRetentionPolicy(nil, nil)
	now := time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)
	exp := rp.ComputeExpiresAt("long", now)
	if exp == "" {
		t.Fatal("expected non-empty expires_at for long tier")
	}
	parsed, err := time.Parse(time.RFC3339, exp)
	if err != nil {
		t.Fatalf("invalid timestamp: %v", err)
	}
	expectedDate := now.AddDate(0, 0, 365)
	if !strings.HasPrefix(parsed.Format(time.RFC3339), expectedDate.Format("2006-01-02")) {
		t.Errorf("long tier expires %v, want around %v", parsed, expectedDate)
	}
}

func TestRetentionPolicy_DefaultRetention(t *testing.T) {
	rp := NewRetentionPolicy(nil, nil)
	if rp.DefaultRetention() != "P90D" {
		t.Errorf("DefaultRetention() = %q, want P90D", rp.DefaultRetention())
	}
}

func TestRetentionPolicy_CustomOverrides(t *testing.T) {
	rp := NewRetentionPolicy(
		map[string]string{"low_risk_success": "long"},
		map[string]string{"short": "P14D"},
	)
	if rp.ResolveTier("low_risk_success") != "long" {
		t.Error("custom class-to-tier override not applied")
	}
	now := time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)
	exp := rp.ComputeExpiresAt("short", now)
	parsed, _ := time.Parse(time.RFC3339, exp)
	want := now.AddDate(0, 0, 14)
	if parsed.Day() != want.Day() || parsed.Month() != want.Month() {
		t.Errorf("custom tier duration: got %v, want ~%v", parsed, want)
	}
}
