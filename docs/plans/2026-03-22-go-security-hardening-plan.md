# Go v0.8-v0.9 Security Hardening Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the v0.8-v0.9 security-hardening features (event classification, retention policy, failure redaction, disclosure control, audit aggregation, storage-side redaction) in the Go ANIP runtime, achieving parity with Python and TypeScript.

**Architecture:** Six focused files in `packages/go/service/` — each a pure-function or small-struct module with no external dependencies beyond `core`. Integration through `appendAuditEntry()` and `Invoke()` in `invoke.go`, plus config fields in `service.go`. Go already has the model fields in `core/models.go` (event_class, retention_tier, expires_at, storage_redacted, entry_type).

**Tech Stack:** Go standard library only. No new dependencies.

---

## File Structure

| File | Responsibility | Status |
|------|---------------|--------|
| `packages/go/service/classification.go` | Event classification pure function | Create |
| `packages/go/service/classification_test.go` | Tests for classification | Create |
| `packages/go/service/retention.go` | Two-layer retention policy (EventClass→Tier→Duration) | Create |
| `packages/go/service/retention_test.go` | Tests for retention | Create |
| `packages/go/service/redaction.go` | Response-boundary failure redaction | Create |
| `packages/go/service/redaction_test.go` | Tests for redaction | Create |
| `packages/go/service/disclosure.go` | Policy-mode caller-class resolution | Create |
| `packages/go/service/disclosure_test.go` | Tests for disclosure | Create |
| `packages/go/service/aggregation.go` | Time-window bucketed audit aggregation | Create |
| `packages/go/service/aggregation_test.go` | Tests for aggregation | Create |
| `packages/go/service/storage_redaction.go` | Write-path parameter stripping | Create |
| `packages/go/service/storage_redaction_test.go` | Tests for storage redaction | Create |
| `packages/go/service/invoke.go` | Wire classification, redaction, storage redaction into invoke flow | Modify |
| `packages/go/service/service.go` | Add config fields, aggregator lifecycle, discovery posture | Modify |

---

## Chunk 1: Classification, Retention, Storage Redaction

### Task 1: Event Classification

**Files:**
- Create: `packages/go/service/classification.go`
- Create: `packages/go/service/classification_test.go`

- [ ] **Step 1: Write the failing tests**

```go
// classification_test.go
package service

import "testing"

func TestClassifyEvent_HighRiskSuccess(t *testing.T) {
	for _, se := range []string{"write", "irreversible", "transactional"} {
		got := ClassifyEvent(se, true, "")
		if got != "high_risk_success" {
			t.Errorf("ClassifyEvent(%q, true, \"\") = %q, want high_risk_success", se, got)
		}
	}
}

func TestClassifyEvent_LowRiskSuccess(t *testing.T) {
	got := ClassifyEvent("read", true, "")
	if got != "low_risk_success" {
		t.Errorf("ClassifyEvent(read, true, \"\") = %q, want low_risk_success", got)
	}
}

func TestClassifyEvent_MalformedOrSpam(t *testing.T) {
	// No side-effect type (pre-resolution failure)
	got := ClassifyEvent("", false, "unknown_capability")
	if got != "malformed_or_spam" {
		t.Errorf("ClassifyEvent(\"\", false, unknown_capability) = %q, want malformed_or_spam", got)
	}
	// Known malformed failure types
	for _, ft := range []string{"unknown_capability", "streaming_not_supported", "internal_error"} {
		got := ClassifyEvent("read", false, ft)
		if got != "malformed_or_spam" {
			t.Errorf("ClassifyEvent(read, false, %q) = %q, want malformed_or_spam", ft, got)
		}
	}
}

func TestClassifyEvent_HighRiskDenial(t *testing.T) {
	for _, ft := range []string{"scope_insufficient", "invalid_token", "token_expired", "purpose_mismatch"} {
		got := ClassifyEvent("write", false, ft)
		if got != "high_risk_denial" {
			t.Errorf("ClassifyEvent(write, false, %q) = %q, want high_risk_denial", ft, got)
		}
	}
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd packages/go && go test ./service/ -run TestClassifyEvent -v`
Expected: FAIL — `ClassifyEvent` undefined

- [ ] **Step 3: Write minimal implementation**

```go
// classification.go
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd packages/go && go test ./service/ -run TestClassifyEvent -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/go/service/classification.go packages/go/service/classification_test.go
git commit -m "feat(go): add event classification (§6.8)"
```

---

### Task 2: Retention Policy

**Files:**
- Create: `packages/go/service/retention.go`
- Create: `packages/go/service/retention_test.go`

- [ ] **Step 1: Write the failing tests**

```go
// retention_test.go
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
		{"unknown_class", "short"}, // fallback
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
	// P365D = 365 days
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd packages/go && go test ./service/ -run TestRetentionPolicy -v`
Expected: FAIL — `NewRetentionPolicy` undefined

- [ ] **Step 3: Write minimal implementation**

```go
// retention.go
package service

import (
	"fmt"
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
// Layer 1: EventClass → RetentionTier
// Layer 2: RetentionTier → ISO 8601 duration
type RetentionPolicy struct {
	classToTier    map[string]string
	tierToDuration map[string]string
}

// NewRetentionPolicy creates a retention policy with optional overrides.
// Nil maps use defaults.
func NewRetentionPolicy(classOverrides, tierOverrides map[string]string) *RetentionPolicy {
	ct := make(map[string]string, len(defaultClassToTier))
	for k, v := range defaultClassToTier {
		ct[k] = v
	}
	for k, v := range classOverrides {
		ct[k] = v
	}

	td := make(map[string]string, len(defaultTierToDuration))
	for k, v := range defaultTierToDuration {
		td[k] = v
	}
	for k, v := range tierOverrides {
		td[k] = v
	}

	return &RetentionPolicy{classToTier: ct, tierToDuration: td}
}

// ResolveTier maps an event class to its retention tier.
func (rp *RetentionPolicy) ResolveTier(eventClass string) string {
	if tier, ok := rp.classToTier[eventClass]; ok {
		return tier
	}
	return "short" // fallback
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd packages/go && go test ./service/ -run TestRetentionPolicy -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/go/service/retention.go packages/go/service/retention_test.go
git commit -m "feat(go): add two-layer retention policy (§6.8)"
```

---

### Task 3: Storage-Side Redaction

**Files:**
- Create: `packages/go/service/storage_redaction.go`
- Create: `packages/go/service/storage_redaction_test.go`

- [ ] **Step 1: Write the failing tests**

```go
// storage_redaction_test.go
package service

import "testing"

func TestStorageRedact_LowValueStripsParameters(t *testing.T) {
	for _, ec := range []string{"low_risk_success", "malformed_or_spam", "repeated_low_value_denial"} {
		entry := map[string]any{
			"event_class": ec,
			"parameters":  map[string]any{"origin": "SEA"},
		}
		result := StorageRedactEntry(entry)
		if result["parameters"] != nil {
			t.Errorf("event_class=%q: parameters should be nil, got %v", ec, result["parameters"])
		}
		if result["storage_redacted"] != true {
			t.Errorf("event_class=%q: storage_redacted should be true", ec)
		}
	}
}

func TestStorageRedact_HighValuePreservesParameters(t *testing.T) {
	for _, ec := range []string{"high_risk_success", "high_risk_denial"} {
		entry := map[string]any{
			"event_class": ec,
			"parameters":  map[string]any{"origin": "SEA"},
		}
		result := StorageRedactEntry(entry)
		if result["parameters"] == nil {
			t.Errorf("event_class=%q: parameters should be preserved", ec)
		}
		if result["storage_redacted"] != false {
			t.Errorf("event_class=%q: storage_redacted should be false", ec)
		}
	}
}

func TestStorageRedact_DoesNotMutateOriginal(t *testing.T) {
	entry := map[string]any{
		"event_class": "low_risk_success",
		"parameters":  map[string]any{"origin": "SEA"},
	}
	_ = StorageRedactEntry(entry)
	if entry["parameters"] == nil {
		t.Error("original entry was mutated")
	}
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd packages/go && go test ./service/ -run TestStorageRedact -v`
Expected: FAIL — `StorageRedactEntry` undefined

- [ ] **Step 3: Write minimal implementation**

```go
// storage_redaction.go
package service

// StorageRedactEntry strips parameters from low-value audit entries
// before persistence. Implements SPEC §6.10.
// Returns a shallow copy — does not mutate the input.
func StorageRedactEntry(entry map[string]any) map[string]any {
	result := make(map[string]any, len(entry))
	for k, v := range entry {
		result[k] = v
	}

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd packages/go && go test ./service/ -run TestStorageRedact -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/go/service/storage_redaction.go packages/go/service/storage_redaction_test.go
git commit -m "feat(go): add storage-side parameter redaction (§6.10)"
```

---

## Chunk 2: Response Redaction, Disclosure, Aggregation

### Task 4: Response-Boundary Failure Redaction

**Files:**
- Create: `packages/go/service/redaction.go`
- Create: `packages/go/service/redaction_test.go`

- [ ] **Step 1: Write the failing tests**

```go
// redaction_test.go
package service

import "testing"

func TestRedactFailure_Full(t *testing.T) {
	failure := map[string]any{
		"type":   "scope_insufficient",
		"detail": "Need travel.book scope",
		"retry":  false,
		"resolution": map[string]any{
			"action":       "request_scope",
			"requires":     []string{"travel.book"},
			"grantable_by": "human:samir@example.com",
		},
	}
	result := RedactFailure(failure, "full")
	if result["detail"] != "Need travel.book scope" {
		t.Error("full mode should preserve detail")
	}
	res := result["resolution"].(map[string]any)
	if res["grantable_by"] != "human:samir@example.com" {
		t.Error("full mode should preserve grantable_by")
	}
}

func TestRedactFailure_Reduced(t *testing.T) {
	failure := map[string]any{
		"type":   "scope_insufficient",
		"detail": "Need travel.book scope",
		"retry":  false,
		"resolution": map[string]any{
			"action":       "request_scope",
			"requires":     []string{"travel.book"},
			"grantable_by": "human:samir@example.com",
		},
	}
	result := RedactFailure(failure, "reduced")
	if result["detail"] != "Need travel.book scope" {
		t.Error("reduced should preserve detail (under 200 chars)")
	}
	res := result["resolution"].(map[string]any)
	if res["grantable_by"] != nil {
		t.Error("reduced should null grantable_by")
	}
	if res["action"] != "request_scope" {
		t.Error("reduced should preserve action")
	}
}

func TestRedactFailure_Redacted(t *testing.T) {
	failure := map[string]any{
		"type":   "scope_insufficient",
		"detail": "Need travel.book scope with specific user context",
		"retry":  false,
		"resolution": map[string]any{
			"action":       "request_scope",
			"requires":     []string{"travel.book"},
			"grantable_by": "human:samir@example.com",
		},
	}
	result := RedactFailure(failure, "redacted")
	if result["detail"] != "Insufficient scope for this capability" {
		t.Errorf("redacted detail = %q, want generic message", result["detail"])
	}
	if result["type"] != "scope_insufficient" {
		t.Error("type should never be redacted")
	}
	if result["retry"] != false {
		t.Error("retry should never be redacted")
	}
	res := result["resolution"].(map[string]any)
	if res["action"] != "request_scope" {
		t.Error("action should never be redacted")
	}
	if res["requires"] != nil {
		t.Error("redacted should null requires")
	}
	if res["grantable_by"] != nil {
		t.Error("redacted should null grantable_by")
	}
}

func TestRedactFailure_ReducedTruncatesLongDetail(t *testing.T) {
	longDetail := ""
	for i := 0; i < 300; i++ {
		longDetail += "x"
	}
	failure := map[string]any{
		"type":   "internal_error",
		"detail": longDetail,
		"retry":  false,
	}
	result := RedactFailure(failure, "reduced")
	detail := result["detail"].(string)
	if len(detail) > 200 {
		t.Errorf("reduced should truncate detail to 200 chars, got %d", len(detail))
	}
}

func TestRedactFailure_TypeAndRetryNeverRedacted(t *testing.T) {
	failure := map[string]any{
		"type":  "token_expired",
		"detail": "Token XYZ expired at ...",
		"retry": true,
	}
	for _, level := range []string{"full", "reduced", "redacted"} {
		result := RedactFailure(failure, level)
		if result["type"] != "token_expired" {
			t.Errorf("level=%q: type was redacted", level)
		}
		if result["retry"] != true {
			t.Errorf("level=%q: retry was redacted", level)
		}
	}
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd packages/go && go test ./service/ -run TestRedactFailure -v`
Expected: FAIL — `RedactFailure` undefined

- [ ] **Step 3: Write minimal implementation**

```go
// redaction.go
package service

// genericMessages maps failure types to generic disclosure messages
// used at the "redacted" level. Per SPEC §6.8.
var genericMessages = map[string]string{
	"scope_insufficient":        "Insufficient scope for this capability",
	"invalid_token":             "Authentication failed",
	"token_expired":             "Token has expired",
	"purpose_mismatch":          "Token purpose does not match this capability",
	"insufficient_authority":    "Insufficient authority for this action",
	"unknown_capability":        "Capability not found",
	"not_found":                 "Resource not found",
	"unavailable":               "Service temporarily unavailable",
	"concurrent_lock":           "Operation conflict",
	"internal_error":            "Internal error",
	"streaming_not_supported":   "Streaming not supported for this capability",
	"scope_escalation":          "Scope escalation not permitted",
}

// RedactFailure applies disclosure-level redaction to a failure response.
// The input is NOT mutated; a new map is returned.
//
// Rules (never redacted): type, retry, resolution.action
// "full": everything as-is
// "reduced": detail truncated to 200 chars, resolution.grantable_by nulled
// "redacted": detail replaced with generic message, resolution fields nulled except action
func RedactFailure(failure map[string]any, level string) map[string]any {
	if level == "full" {
		return copyMap(failure)
	}

	result := copyMap(failure)

	if level == "reduced" {
		// Truncate detail to 200 chars.
		if detail, ok := result["detail"].(string); ok && len(detail) > 200 {
			result["detail"] = detail[:200]
		}
		// Null grantable_by in resolution.
		if res, ok := result["resolution"].(map[string]any); ok {
			resCopy := copyMap(res)
			resCopy["grantable_by"] = nil
			result["resolution"] = resCopy
		}
		return result
	}

	// "redacted" mode
	failType, _ := result["type"].(string)
	if msg, ok := genericMessages[failType]; ok {
		result["detail"] = msg
	} else {
		result["detail"] = "Request failed"
	}

	if res, ok := result["resolution"].(map[string]any); ok {
		resCopy := make(map[string]any)
		resCopy["action"] = res["action"] // preserve action
		resCopy["requires"] = nil
		resCopy["grantable_by"] = nil
		resCopy["estimated_availability"] = nil
		result["resolution"] = resCopy
	}

	return result
}

func copyMap(m map[string]any) map[string]any {
	c := make(map[string]any, len(m))
	for k, v := range m {
		c[k] = v
	}
	return c
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd packages/go && go test ./service/ -run TestRedactFailure -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/go/service/redaction.go packages/go/service/redaction_test.go
git commit -m "feat(go): add response-boundary failure redaction (§6.8)"
```

---

### Task 5: Disclosure Control

**Files:**
- Create: `packages/go/service/disclosure.go`
- Create: `packages/go/service/disclosure_test.go`

- [ ] **Step 1: Write the failing tests**

```go
// disclosure_test.go
package service

import "testing"

func TestResolveDisclosureLevel_FixedModes(t *testing.T) {
	for _, level := range []string{"full", "reduced", "redacted"} {
		got := ResolveDisclosureLevel(level, nil, nil)
		if got != level {
			t.Errorf("ResolveDisclosureLevel(%q) = %q, want %q", level, got, level)
		}
	}
}

func TestResolveDisclosureLevel_PolicyNoPolicy(t *testing.T) {
	got := ResolveDisclosureLevel("policy", nil, nil)
	if got != "redacted" {
		t.Errorf("policy mode with nil policy should default to redacted, got %q", got)
	}
}

func TestResolveDisclosureLevel_PolicyWithCallerClass(t *testing.T) {
	claims := map[string]any{"anip:caller_class": "internal"}
	policy := map[string]string{
		"internal": "full",
		"default":  "redacted",
	}
	got := ResolveDisclosureLevel("policy", claims, policy)
	if got != "full" {
		t.Errorf("internal caller should get full, got %q", got)
	}
}

func TestResolveDisclosureLevel_PolicyFallsBackToDefault(t *testing.T) {
	claims := map[string]any{"anip:caller_class": "unknown_class"}
	policy := map[string]string{
		"internal": "full",
		"default":  "reduced",
	}
	got := ResolveDisclosureLevel("policy", claims, policy)
	if got != "reduced" {
		t.Errorf("unknown caller should fall back to default, got %q", got)
	}
}

func TestResolveDisclosureLevel_PolicyFromScope(t *testing.T) {
	// No explicit caller_class, but scope contains audit:full
	claims := map[string]any{
		"scope": []any{"travel.search", "audit:full"},
	}
	policy := map[string]string{
		"audit_full": "full",
		"default":    "redacted",
	}
	got := ResolveDisclosureLevel("policy", claims, policy)
	if got != "full" {
		t.Errorf("audit:full scope should resolve to audit_full class, got %q", got)
	}
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd packages/go && go test ./service/ -run TestResolveDisclosureLevel -v`
Expected: FAIL — `ResolveDisclosureLevel` undefined

- [ ] **Step 3: Write minimal implementation**

```go
// disclosure.go
package service

// ResolveDisclosureLevel resolves the effective disclosure level.
// Fixed modes ("full", "reduced", "redacted") pass through.
// "policy" mode resolves caller class from token claims and applies the policy map.
// Implements SPEC §6.9 caller-class-aware disclosure.
func ResolveDisclosureLevel(level string, tokenClaims map[string]any, policy map[string]string) string {
	if level != "policy" {
		return level
	}

	callerClass := resolveCallerClass(tokenClaims)

	if policy == nil {
		return "redacted"
	}

	if mapped, ok := policy[callerClass]; ok {
		return mapped
	}
	if def, ok := policy["default"]; ok {
		return def
	}
	return "redacted"
}

// resolveCallerClass determines the caller class from token claims.
// Priority: 1) explicit anip:caller_class claim, 2) scope-derived, 3) "default".
func resolveCallerClass(claims map[string]any) string {
	if claims == nil {
		return "default"
	}

	// 1. Explicit claim.
	if cc, ok := claims["anip:caller_class"].(string); ok && cc != "" {
		return cc
	}

	// 2. Scope-derived: "audit:full" → "audit_full".
	if scopes, ok := claims["scope"].([]any); ok {
		for _, s := range scopes {
			if str, ok := s.(string); ok && str == "audit:full" {
				return "audit_full"
			}
		}
	}

	return "default"
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd packages/go && go test ./service/ -run TestResolveDisclosureLevel -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/go/service/disclosure.go packages/go/service/disclosure_test.go
git commit -m "feat(go): add caller-class disclosure control (§6.9)"
```

---

### Task 6: Audit Aggregation

**Files:**
- Create: `packages/go/service/aggregation.go`
- Create: `packages/go/service/aggregation_test.go`

- [ ] **Step 1: Write the failing tests**

```go
// aggregation_test.go
package service

import (
	"testing"
	"time"
)

func TestAggregator_SingleEventPassesThrough(t *testing.T) {
	agg := NewAuditAggregator(60)
	now := time.Date(2026, 1, 1, 0, 0, 30, 0, time.UTC)

	agg.Submit(map[string]any{
		"actor_key":    "agent:test",
		"capability":   "search",
		"failure_type": "scope_insufficient",
		"timestamp":    now.Format(time.RFC3339),
	})

	// Flush after window closes
	flushTime := time.Date(2026, 1, 1, 0, 1, 1, 0, time.UTC)
	results := agg.Flush(flushTime)
	if len(results) != 1 {
		t.Fatalf("expected 1 result, got %d", len(results))
	}
	// Single event should be a normal entry (map), not aggregated
	entry, ok := results[0].(map[string]any)
	if !ok {
		t.Fatal("single event should pass through as map[string]any")
	}
	if entry["actor_key"] != "agent:test" {
		t.Error("entry should preserve original fields")
	}
}

func TestAggregator_MultipleEventsAggregate(t *testing.T) {
	agg := NewAuditAggregator(60)
	base := time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)

	for i := 0; i < 5; i++ {
		agg.Submit(map[string]any{
			"actor_key":    "agent:spam",
			"capability":   "search",
			"failure_type": "scope_insufficient",
			"timestamp":    base.Add(time.Duration(i) * time.Second).Format(time.RFC3339),
			"detail":       "first detail",
		})
	}

	flushTime := base.Add(61 * time.Second)
	results := agg.Flush(flushTime)
	if len(results) != 1 {
		t.Fatalf("expected 1 aggregated result, got %d", len(results))
	}

	agg_entry, ok := results[0].(*AggregatedEntry)
	if !ok {
		t.Fatal("multiple events should produce *AggregatedEntry")
	}
	if agg_entry.Count != 5 {
		t.Errorf("count = %d, want 5", agg_entry.Count)
	}
	if agg_entry.EventClass != "repeated_low_value_denial" {
		t.Errorf("event_class = %q, want repeated_low_value_denial", agg_entry.EventClass)
	}
	if agg_entry.RetentionTier != "aggregate_only" {
		t.Errorf("retention_tier = %q, want aggregate_only", agg_entry.RetentionTier)
	}
}

func TestAggregator_DifferentKeysNotMerged(t *testing.T) {
	agg := NewAuditAggregator(60)
	base := time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)

	agg.Submit(map[string]any{
		"actor_key": "agent:a", "capability": "search",
		"failure_type": "scope_insufficient", "timestamp": base.Format(time.RFC3339),
	})
	agg.Submit(map[string]any{
		"actor_key": "agent:b", "capability": "search",
		"failure_type": "scope_insufficient", "timestamp": base.Format(time.RFC3339),
	})

	results := agg.Flush(base.Add(61 * time.Second))
	if len(results) != 2 {
		t.Fatalf("different actor_keys should produce 2 results, got %d", len(results))
	}
}

func TestAggregator_FlushDoesNotEmitOpenWindows(t *testing.T) {
	agg := NewAuditAggregator(60)
	now := time.Date(2026, 1, 1, 0, 0, 30, 0, time.UTC)

	agg.Submit(map[string]any{
		"actor_key": "agent:test", "capability": "search",
		"failure_type": "scope_insufficient", "timestamp": now.Format(time.RFC3339),
	})

	// Flush BEFORE window closes
	results := agg.Flush(now.Add(10 * time.Second))
	if len(results) != 0 {
		t.Fatalf("should not flush open windows, got %d results", len(results))
	}
}

func TestAggregatedEntry_ToAuditDict(t *testing.T) {
	ae := &AggregatedEntry{
		EventClass:    "repeated_low_value_denial",
		RetentionTier: "aggregate_only",
		GroupingKey: map[string]string{
			"actor_key": "agent:test", "capability": "search", "failure_type": "scope_insufficient",
		},
		WindowStart:           "2026-01-01T00:00:00Z",
		WindowEnd:             "2026-01-01T00:01:00Z",
		Count:                 10,
		FirstSeen:             "2026-01-01T00:00:05Z",
		LastSeen:              "2026-01-01T00:00:55Z",
		RepresentativeDetail:  "Insufficient scope",
	}
	d := ae.ToAuditDict()
	if d["entry_type"] != "aggregated" {
		t.Errorf("entry_type = %q, want aggregated", d["entry_type"])
	}
	if d["count"] != 10 {
		t.Errorf("count = %v, want 10", d["count"])
	}
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd packages/go && go test ./service/ -run "TestAggregat" -v`
Expected: FAIL — `NewAuditAggregator` undefined

- [ ] **Step 3: Write minimal implementation**

```go
// aggregation.go
package service

import (
	"sync"
	"time"
)

// groupingKey is the tuple used to group events in an aggregation window.
type groupingKey struct {
	ActorKey    string
	Capability  string
	FailureType string
}

// bucket tracks events within a single aggregation window for one grouping key.
type bucket struct {
	events              []map[string]any
	firstSeen           time.Time
	lastSeen            time.Time
	representativeDetail string
}

// AggregatedEntry is emitted when a window closes with >1 event for a grouping key.
type AggregatedEntry struct {
	EventClass           string
	RetentionTier        string
	GroupingKey           map[string]string
	WindowStart          string
	WindowEnd            string
	Count                int
	FirstSeen            string
	LastSeen             string
	RepresentativeDetail string
}

// ToAuditDict converts an AggregatedEntry to a map suitable for audit persistence.
func (ae *AggregatedEntry) ToAuditDict() map[string]any {
	return map[string]any{
		"entry_type":            "aggregated",
		"event_class":           ae.EventClass,
		"retention_tier":        ae.RetentionTier,
		"grouping_key":          ae.GroupingKey,
		"aggregation_window":    map[string]string{"start": ae.WindowStart, "end": ae.WindowEnd},
		"aggregation_count":     ae.Count,
		"count":                 ae.Count,
		"first_seen":            ae.FirstSeen,
		"last_seen":             ae.LastSeen,
		"representative_detail": ae.RepresentativeDetail,
		"capability":            ae.GroupingKey["capability"],
		"failure_type":          ae.GroupingKey["failure_type"],
		"success":               false,
	}
}

// windowKey combines a grouping key with a window epoch for map indexing.
type windowKey struct {
	gk    groupingKey
	epoch int64
}

// AuditAggregator buckets low-value denial events by time window.
// Implements SPEC §6.9.
type AuditAggregator struct {
	windowSeconds int64
	mu            sync.Mutex
	windows       map[windowKey]*bucket
}

// NewAuditAggregator creates an aggregator with the given window size in seconds.
func NewAuditAggregator(windowSeconds int) *AuditAggregator {
	return &AuditAggregator{
		windowSeconds: int64(windowSeconds),
		windows:       make(map[windowKey]*bucket),
	}
}

// Submit adds an event to the aggregator. The event must have
// actor_key, capability, failure_type, and timestamp fields.
func (a *AuditAggregator) Submit(event map[string]any) {
	a.mu.Lock()
	defer a.mu.Unlock()

	actorKey, _ := event["actor_key"].(string)
	if actorKey == "" {
		actorKey = "anonymous"
	}
	capability, _ := event["capability"].(string)
	if capability == "" {
		capability = "_pre_auth"
	}
	failureType, _ := event["failure_type"].(string)
	if failureType == "" {
		failureType = "unknown"
	}

	ts := parseTimestamp(event)
	epoch := ts.Unix() - (ts.Unix() % a.windowSeconds)

	gk := groupingKey{ActorKey: actorKey, Capability: capability, FailureType: failureType}
	wk := windowKey{gk: gk, epoch: epoch}

	b, ok := a.windows[wk]
	if !ok {
		detail, _ := event["detail"].(string)
		if len(detail) > 200 {
			detail = detail[:200]
		}
		b = &bucket{
			firstSeen:            ts,
			lastSeen:             ts,
			representativeDetail: detail,
		}
		a.windows[wk] = b
	}
	b.events = append(b.events, event)
	if ts.After(b.lastSeen) {
		b.lastSeen = ts
	}
}

// Flush closes all windows whose end time <= now and returns the results.
// Single-event buckets pass through as map[string]any.
// Multi-event buckets produce *AggregatedEntry.
func (a *AuditAggregator) Flush(now time.Time) []any {
	a.mu.Lock()
	defer a.mu.Unlock()

	var results []any
	nowUnix := now.Unix()

	for wk, b := range a.windows {
		windowEnd := wk.epoch + a.windowSeconds
		if windowEnd > nowUnix {
			continue // window still open
		}

		windowStartStr := time.Unix(wk.epoch, 0).UTC().Format(time.RFC3339)
		windowEndStr := time.Unix(windowEnd, 0).UTC().Format(time.RFC3339)

		if len(b.events) == 1 {
			results = append(results, b.events[0])
		} else {
			results = append(results, &AggregatedEntry{
				EventClass:    "repeated_low_value_denial",
				RetentionTier: "aggregate_only",
				GroupingKey: map[string]string{
					"actor_key":    wk.gk.ActorKey,
					"capability":   wk.gk.Capability,
					"failure_type": wk.gk.FailureType,
				},
				WindowStart:          windowStartStr,
				WindowEnd:            windowEndStr,
				Count:                len(b.events),
				FirstSeen:            b.firstSeen.UTC().Format(time.RFC3339),
				LastSeen:             b.lastSeen.UTC().Format(time.RFC3339),
				RepresentativeDetail: b.representativeDetail,
			})
		}
		delete(a.windows, wk)
	}

	return results
}

func parseTimestamp(event map[string]any) time.Time {
	if ts, ok := event["timestamp"].(string); ok {
		if t, err := time.Parse(time.RFC3339, ts); err == nil {
			return t
		}
	}
	return time.Now().UTC()
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd packages/go && go test ./service/ -run "TestAggregat" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/go/service/aggregation.go packages/go/service/aggregation_test.go
git commit -m "feat(go): add time-window audit aggregation (§6.9)"
```

---

## Chunk 3: Service Integration

### Task 7: Wire Config + Discovery + Aggregator Lifecycle into service.go

**Files:**
- Modify: `packages/go/core/models.go`
- Modify: `packages/go/service/service.go`

- [ ] **Step 0: Extend AuditEntry model with aggregation fields**

Add these fields to `AuditEntry` in `packages/go/core/models.go` (after `EntryType`):

```go
	GroupingKey          map[string]string `json:"grouping_key,omitempty"`
	AggregationWindow   map[string]string `json:"aggregation_window,omitempty"`
	AggregationCount    int               `json:"aggregation_count,omitempty"`
	FirstSeen           string            `json:"first_seen,omitempty"`
	LastSeen            string            `json:"last_seen,omitempty"`
	RepresentativeDetail string           `json:"representative_detail,omitempty"`
```

These fields are required for aggregated audit entries to carry meaningful data (matching Python and TypeScript).

- [ ] **Step 1: Add config fields to Config struct**

Add these fields to `Config` (after `Hooks`):

```go
	// RetentionPolicy configures event class → tier → duration mapping.
	// If nil, default retention policy is used.
	RetentionPolicy *RetentionPolicy

	// DisclosureLevel controls failure detail disclosure.
	// One of "full", "reduced", "redacted", "policy". Default: "full".
	DisclosureLevel string

	// DisclosurePolicy maps caller classes to disclosure levels.
	// Only used when DisclosureLevel is "policy".
	DisclosurePolicy map[string]string

	// AggregationWindowSeconds sets the aggregation window size.
	// 0 or negative disables aggregation. Default: 0 (disabled).
	AggregationWindowSeconds int
```

- [ ] **Step 2: Add fields to Service struct**

Add these fields to `Service` (after `hooks`):

```go
	retentionPolicy  *RetentionPolicy
	disclosureLevel  string
	disclosurePolicy map[string]string
	aggregator       *AuditAggregator
```

- [ ] **Step 3: Wire in New()**

In `New()`, after `retentionInterval` setup, add:

```go
	rp := cfg.RetentionPolicy
	if rp == nil {
		rp = NewRetentionPolicy(nil, nil)
	}

	disclosureLevel := cfg.DisclosureLevel
	if disclosureLevel == "" {
		disclosureLevel = "full"
	}

	var aggregator *AuditAggregator
	if cfg.AggregationWindowSeconds > 0 {
		aggregator = NewAuditAggregator(cfg.AggregationWindowSeconds)
	}
```

And add to the returned `&Service{}`:

```go
		retentionPolicy:  rp,
		disclosureLevel:  disclosureLevel,
		disclosurePolicy: cfg.DisclosurePolicy,
		aggregator:       aggregator,
```

- [ ] **Step 4: Add aggregator flush goroutine in Start()**

After the checkpoint goroutine start block, add:

```go
	// Start aggregator flush goroutine.
	if s.aggregator != nil {
		s.wg.Add(1)
		go s.runAggregatorFlush()
	}
```

Add the method:

```go
// runAggregatorFlush periodically flushes closed aggregation windows.
func (s *Service) runAggregatorFlush() {
	defer s.wg.Done()
	ticker := time.NewTicker(10 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-s.stopCh:
			// Final flush on shutdown.
			s.flushAggregator()
			return
		case <-ticker.C:
			s.flushAggregator()
		}
	}
}

func (s *Service) flushAggregator() {
	results := s.aggregator.Flush(time.Now().UTC())
	for _, item := range results {
		var entryData map[string]any
		switch v := item.(type) {
		case *AggregatedEntry:
			entryData = StorageRedactEntry(v.ToAuditDict())
		case map[string]any:
			entryData = StorageRedactEntry(v)
		default:
			continue
		}
		s.persistAuditMap(entryData)
	}
}
```

- [ ] **Step 5: Update discovery posture**

In `GetDiscovery()`, replace the hardcoded `failure_disclosure` and `audit.retention` with:

```go
		failureDisc := map[string]any{
			"detail_level": s.disclosureLevel,
		}
		if s.disclosureLevel == "policy" && s.disclosurePolicy != nil {
			classes := make([]string, 0, len(s.disclosurePolicy))
			for k := range s.disclosurePolicy {
				classes = append(classes, k)
			}
			failureDisc["caller_classes"] = classes
		}

		// Then in the posture block:
		"posture": map[string]any{
			"audit": map[string]any{
				"retention":          s.retentionPolicy.DefaultRetention(),
				"retention_enforced": s.retentionRunning,
			},
			"failure_disclosure": failureDisc,
			// ... rest unchanged
		},
```

- [ ] **Step 6: Run all existing tests to verify nothing broke**

Run: `cd packages/go && go test ./service/ -v`
Expected: all existing tests PASS

- [ ] **Step 7: Commit**

```bash
git add packages/go/service/service.go
git commit -m "feat(go): wire retention, disclosure, aggregation config into service"
```

---

### Task 8: Wire Classification + Redaction into invoke.go

**Files:**
- Modify: `packages/go/service/invoke.go`

- [ ] **Step 1: Update appendAuditEntry signature and body**

Change `appendAuditEntry` to accept `sideEffectType` and populate classification fields:

```go
func (s *Service) appendAuditEntry(
	capability string,
	token *core.DelegationToken,
	success bool,
	failureType string,
	resultSummary map[string]any,
	costActual *core.CostActual,
	invocationID string,
	clientReferenceID string,
	sideEffectType string,
) {
```

Inside the function, before creating the entry, add:

```go
	eventClass := ClassifyEvent(sideEffectType, success, failureType)
	tier := s.retentionPolicy.ResolveTier(eventClass)
	expiresAt := s.retentionPolicy.ComputeExpiresAt(tier, time.Now().UTC())
```

Set the fields on the entry:

```go
	entry := &core.AuditEntry{
		// ... existing fields ...
		EventClass:        eventClass,
		RetentionTier:     tier,
		ExpiresAt:         expiresAt,
	}
```

After building the entry, apply storage redaction before persistence:

```go
	// Convert entry to map for storage redaction.
	entryMap := map[string]any{
		"event_class":    entry.EventClass,
		"parameters":     entry.Parameters,
	}
	redacted := StorageRedactEntry(entryMap)
	if redacted["storage_redacted"] == true {
		entry.Parameters = nil
		entry.StorageRedacted = true
	}

	// Route through aggregator if applicable.
	if s.aggregator != nil && eventClass == "malformed_or_spam" {
		eventMap := s.entryToMap(entry)
		s.aggregator.Submit(eventMap)
		return
	}
```

- [ ] **Step 2: Update all appendAuditEntry call sites**

Every call to `appendAuditEntry` in `invoke.go` needs the new `sideEffectType` parameter.

In `Invoke()`:
- Unknown capability (line ~195): pass `""` (no side effect resolved yet)
- Scope failure (line ~195): pass `capDef.Declaration.SideEffect.Type`
- Handler error (line ~238, ~253): pass `capDef.Declaration.SideEffect.Type`
- Success (line ~271): pass `capDef.Declaration.SideEffect.Type`

In `InvokeStream()`:
- Handler error (line ~395): pass `capDef.Declaration.SideEffect.Type`
- Success (line ~412): pass `capDef.Declaration.SideEffect.Type`

- [ ] **Step 3: Add failure redaction to Invoke response paths**

For each failure response in `Invoke()`, apply redaction:

```go
	// After building the failure map:
	effectiveLevel := ResolveDisclosureLevel(s.disclosureLevel, nil, s.disclosurePolicy)
	// For JWT-authenticated requests, pass token claims:
	// effectiveLevel := ResolveDisclosureLevel(s.disclosureLevel, tokenClaims, s.disclosurePolicy)
	failure = RedactFailure(failure, effectiveLevel)
```

Apply to:
1. Unknown capability failure response
2. Scope validation failure response
3. Handler ANIP error response
4. Handler generic error response

For unknown capability (pre-auth, no token claims): use `nil` for claims.
For other failures (token available): build claims map from `token`.

- [ ] **Step 4: Add helper methods**

Add `entryToMap` to convert an AuditEntry to a map for aggregation:

```go
func (s *Service) entryToMap(entry *core.AuditEntry) map[string]any {
	m := map[string]any{
		"timestamp":       entry.Timestamp,
		"capability":      entry.Capability,
		"actor_key":       entry.RootPrincipal,
		"failure_type":    entry.FailureType,
		"event_class":     entry.EventClass,
		"retention_tier":  entry.RetentionTier,
		"expires_at":      entry.ExpiresAt,
		"invocation_id":   entry.InvocationID,
	}
	if entry.ResultSummary != nil {
		if detail, ok := entry.ResultSummary["detail"]; ok {
			m["detail"] = detail
		}
	}
	return m
}
```

Add `persistAuditMap` for the aggregator flush path:

```go
func (s *Service) persistAuditMap(entryData map[string]any) {
	entry := &core.AuditEntry{
		Capability:    strVal(entryData, "capability"),
		Success:       false,
		FailureType:   strVal(entryData, "failure_type"),
		EventClass:    strVal(entryData, "event_class"),
		RetentionTier: strVal(entryData, "retention_tier"),
		ExpiresAt:     strVal(entryData, "expires_at"),
		EntryType:     strVal(entryData, "entry_type"),
		RootPrincipal: strVal(entryData, "actor_key"),
	}
	if entry.EntryType == "" {
		entry.EntryType = "normal"
	}
	// Carry aggregation-specific fields for aggregated entries.
	if gk, ok := entryData["grouping_key"].(map[string]string); ok {
		entry.GroupingKey = gk
	}
	if aw, ok := entryData["aggregation_window"].(map[string]string); ok {
		entry.AggregationWindow = aw
	}
	if count, ok := entryData["aggregation_count"].(int); ok {
		entry.AggregationCount = count
	}
	entry.FirstSeen = strVal(entryData, "first_seen")
	entry.LastSeen = strVal(entryData, "last_seen")
	entry.RepresentativeDetail = strVal(entryData, "representative_detail")

	_ = server.AppendAudit(s.keys, s.storage, entry)
}

func strVal(m map[string]any, key string) string {
	v, _ := m[key].(string)
	return v
}
```

- [ ] **Step 5: Run all tests**

Run: `cd packages/go && go test ./... -v`
Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add packages/go/service/invoke.go
git commit -m "feat(go): integrate classification, redaction, aggregation into invoke flow"
```

---

### Task 9: Run Conformance Suite

**Files:** No new files — verification only.

- [ ] **Step 1: Build and start Go example service**

```bash
cd packages/go
go build -o flight-service ./examples/flights/
./flight-service &
sleep 3
```

- [ ] **Step 2: Run conformance suite**

```bash
cd /path/to/repo
pip install -e ./conformance
pytest conformance/ \
  --base-url=http://localhost:8080 \
  --bootstrap-bearer=demo-human-key \
  --sample-inputs=conformance/samples/flight-service.json \
  -v
```

Expected: 43 passed, 1 skipped (same as before — no regressions)

- [ ] **Step 3: Kill the server**

```bash
kill %1
```

- [ ] **Step 4: Final commit if any fixups needed**

```bash
git add -A
git commit -m "fix(go): conformance fixups for security hardening"
```

---

### Task 10: Create PR

- [ ] **Step 1: Create branch and push**

```bash
git checkout -b feat/go-security-hardening
git push -u origin feat/go-security-hardening
```

- [ ] **Step 2: Create PR**

```bash
gh pr create --title "feat(go): add v0.8-v0.9 security hardening" --body "$(cat <<'EOF'
## Summary
- Add event classification (§6.8) — pure function mapping side-effect/success/failure to 5 event classes
- Add two-layer retention policy (§6.8) — EventClass → Tier → Duration with configurable overrides
- Add response-boundary failure redaction (§6.8) — full/reduced/redacted disclosure modes
- Add caller-class disclosure control (§6.9) — policy mode with scope-derived caller class resolution
- Add time-window audit aggregation (§6.9) — bucketed aggregation of low-value denials
- Add storage-side parameter redaction (§6.10) — strip parameters from low-value events before persistence
- Wire all features into invoke flow and service lifecycle
- Achieves parity with Python and TypeScript on v0.8-v0.9 security hardening

## Test plan
- [ ] All new unit tests pass (`go test ./service/ -v`)
- [ ] All existing tests pass (no regressions)
- [ ] Conformance suite passes (43 passed, 1 skipped)
EOF
)"
```
