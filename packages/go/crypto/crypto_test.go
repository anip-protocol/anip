package crypto

import (
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestKeyGeneration(t *testing.T) {
	km, err := NewKeyManager("")
	if err != nil {
		t.Fatal(err)
	}

	if km.DelegationPrivateKey() == nil {
		t.Error("delegation private key should not be nil")
	}
	if km.DelegationPublicKey() == nil {
		t.Error("delegation public key should not be nil")
	}
	if km.DelegationKID() == "" {
		t.Error("delegation KID should not be empty")
	}

	if km.AuditPrivateKey() == nil {
		t.Error("audit private key should not be nil")
	}
	if km.AuditPublicKey() == nil {
		t.Error("audit public key should not be nil")
	}
	if km.AuditKID() == "" {
		t.Error("audit KID should not be empty")
	}

	// Delegation and audit keys should be different.
	if km.DelegationKID() == km.AuditKID() {
		t.Error("delegation and audit KIDs should be different")
	}
}

func TestKeyRoundTrip(t *testing.T) {
	dir := t.TempDir()
	keyPath := filepath.Join(dir, "test-keys")

	// Generate and save.
	km1, err := NewKeyManager(keyPath)
	if err != nil {
		t.Fatal(err)
	}

	// Load from disk.
	km2, err := NewKeyManager(keyPath)
	if err != nil {
		t.Fatal(err)
	}

	// KIDs should match.
	if km1.DelegationKID() != km2.DelegationKID() {
		t.Errorf("delegation KID mismatch: %q vs %q", km1.DelegationKID(), km2.DelegationKID())
	}
	if km1.AuditKID() != km2.AuditKID() {
		t.Errorf("audit KID mismatch: %q vs %q", km1.AuditKID(), km2.AuditKID())
	}

	// Sign with km1, verify with km2.
	claims := map[string]any{
		"jti": "test-123",
		"iss": "test-service",
		"sub": "agent:test",
		"aud": "test-service",
		"iat": float64(time.Now().Unix()),
		"exp": float64(time.Now().Add(time.Hour).Unix()),
	}

	token, err := SignDelegationJWT(km1, claims)
	if err != nil {
		t.Fatal(err)
	}

	decoded, err := VerifyDelegationJWT(km2, token, "test-service", "test-service")
	if err != nil {
		t.Fatal(err)
	}

	if decoded["jti"] != "test-123" {
		t.Errorf("expected jti %q, got %v", "test-123", decoded["jti"])
	}
}

func TestKeyLoadFromFile(t *testing.T) {
	dir := t.TempDir()
	keyFile := filepath.Join(dir, "keys.json")

	// Generate and save to a specific file path.
	km1, err := NewKeyManager(keyFile)
	if err != nil {
		t.Fatal(err)
	}

	// Verify file exists.
	if _, err := os.Stat(keyFile); os.IsNotExist(err) {
		t.Fatal("key file should exist")
	}

	// Load from file.
	km2, err := NewKeyManager(keyFile)
	if err != nil {
		t.Fatal(err)
	}

	if km1.DelegationKID() != km2.DelegationKID() {
		t.Error("KIDs should match after round-trip")
	}
}

func TestJWTSignVerify(t *testing.T) {
	km, err := NewKeyManager("")
	if err != nil {
		t.Fatal(err)
	}

	claims := map[string]any{
		"jti":            "token-001",
		"iss":            "anip-test-service",
		"sub":            "agent:demo",
		"aud":            "anip-test-service",
		"iat":            float64(time.Now().Unix()),
		"exp":            float64(time.Now().Add(2 * time.Hour).Unix()),
		"scope":          []string{"travel.search"},
		"root_principal": "human:test@example.com",
		"capability":     "search_flights",
	}

	token, err := SignDelegationJWT(km, claims)
	if err != nil {
		t.Fatal(err)
	}

	decoded, err := VerifyDelegationJWT(km, token, "anip-test-service", "anip-test-service")
	if err != nil {
		t.Fatal(err)
	}

	if decoded["jti"] != "token-001" {
		t.Errorf("expected jti %q, got %v", "token-001", decoded["jti"])
	}
	if decoded["root_principal"] != "human:test@example.com" {
		t.Errorf("expected root_principal %q, got %v", "human:test@example.com", decoded["root_principal"])
	}
	if decoded["capability"] != "search_flights" {
		t.Errorf("expected capability %q, got %v", "search_flights", decoded["capability"])
	}

	// Verify scope is preserved.
	scopeRaw, ok := decoded["scope"].([]any)
	if !ok {
		t.Fatalf("expected scope to be []any, got %T", decoded["scope"])
	}
	if len(scopeRaw) != 1 || scopeRaw[0] != "travel.search" {
		t.Errorf("expected scope [travel.search], got %v", scopeRaw)
	}
}

func TestJWTVerifyWrongKey(t *testing.T) {
	km1, err := NewKeyManager("")
	if err != nil {
		t.Fatal(err)
	}

	km2, err := NewKeyManager("")
	if err != nil {
		t.Fatal(err)
	}

	claims := map[string]any{
		"jti": "token-wrong",
		"iss": "service",
		"sub": "agent:test",
		"aud": "service",
		"iat": float64(time.Now().Unix()),
		"exp": float64(time.Now().Add(time.Hour).Unix()),
	}

	token, err := SignDelegationJWT(km1, claims)
	if err != nil {
		t.Fatal(err)
	}

	// Verify with a different key should fail.
	_, err = VerifyDelegationJWT(km2, token, "", "service")
	if err == nil {
		t.Error("expected verification to fail with wrong key")
	}
}

func TestJWTExpired(t *testing.T) {
	km, err := NewKeyManager("")
	if err != nil {
		t.Fatal(err)
	}

	claims := map[string]any{
		"jti": "expired-token",
		"iss": "service",
		"sub": "agent:test",
		"aud": "service",
		"iat": float64(time.Now().Add(-2 * time.Hour).Unix()),
		"exp": float64(time.Now().Add(-1 * time.Hour).Unix()), // expired 1 hour ago
	}

	token, err := SignDelegationJWT(km, claims)
	if err != nil {
		t.Fatal(err)
	}

	_, err = VerifyDelegationJWT(km, token, "", "service")
	if err == nil {
		t.Error("expected verification to fail for expired token")
	}
}

func TestJWSSignVerify(t *testing.T) {
	km, err := NewKeyManager("")
	if err != nil {
		t.Fatal(err)
	}

	payload := []byte(`{"protocol":"anip/0.11","capabilities":{}}`)

	sig, err := SignDetachedJWS(km, payload)
	if err != nil {
		t.Fatal(err)
	}

	// Signature should be in detached format: "header..signature".
	if err := VerifyDetachedJWS(km, payload, sig); err != nil {
		t.Fatalf("verification failed: %v", err)
	}

	// Verify with wrong payload should fail.
	wrongPayload := []byte(`{"protocol":"anip/0.12","capabilities":{}}`)
	if err := VerifyDetachedJWS(km, wrongPayload, sig); err == nil {
		t.Error("expected verification to fail with wrong payload")
	}
}

func TestJWSVerifyWrongKey(t *testing.T) {
	km1, err := NewKeyManager("")
	if err != nil {
		t.Fatal(err)
	}

	km2, err := NewKeyManager("")
	if err != nil {
		t.Fatal(err)
	}

	payload := []byte(`test payload`)

	sig, err := SignDetachedJWS(km1, payload)
	if err != nil {
		t.Fatal(err)
	}

	if err := VerifyDetachedJWS(km2, payload, sig); err == nil {
		t.Error("expected verification to fail with wrong key")
	}
}

func TestJWSDetachedFormat(t *testing.T) {
	km, err := NewKeyManager("")
	if err != nil {
		t.Fatal(err)
	}

	payload := []byte(`test`)

	sig, err := SignDetachedJWS(km, payload)
	if err != nil {
		t.Fatal(err)
	}

	// Detached JWS should have format: header..signature (empty middle part).
	parts := splitJWS(sig)
	if len(parts) != 3 {
		t.Fatalf("expected 3 parts, got %d", len(parts))
	}
	if parts[1] != "" {
		t.Errorf("middle part should be empty for detached JWS, got %q", parts[1])
	}
	if parts[0] == "" {
		t.Error("header part should not be empty")
	}
	if parts[2] == "" {
		t.Error("signature part should not be empty")
	}
}

func splitJWS(s string) []string {
	result := []string{}
	start := 0
	for i := 0; i < len(s); i++ {
		if s[i] == '.' {
			result = append(result, s[start:i])
			start = i + 1
		}
	}
	result = append(result, s[start:])
	return result
}

func TestJWKSFormat(t *testing.T) {
	km, err := NewKeyManager("")
	if err != nil {
		t.Fatal(err)
	}

	jwks := ToJWKS(km)

	keys, ok := jwks["keys"].([]map[string]any)
	if !ok {
		t.Fatal("expected keys to be []map[string]any")
	}
	if len(keys) != 2 {
		t.Fatalf("expected 2 keys, got %d", len(keys))
	}

	// Check delegation key.
	delKey := keys[0]
	if delKey["kty"] != "EC" {
		t.Errorf("expected kty EC, got %v", delKey["kty"])
	}
	if delKey["crv"] != "P-256" {
		t.Errorf("expected crv P-256, got %v", delKey["crv"])
	}
	if delKey["alg"] != "ES256" {
		t.Errorf("expected alg ES256, got %v", delKey["alg"])
	}
	if delKey["use"] != "sig" {
		t.Errorf("expected use sig, got %v", delKey["use"])
	}
	if delKey["kid"] != km.DelegationKID() {
		t.Errorf("expected kid %q, got %v", km.DelegationKID(), delKey["kid"])
	}
	if _, ok := delKey["x"]; !ok {
		t.Error("expected x field")
	}
	if _, ok := delKey["y"]; !ok {
		t.Error("expected y field")
	}

	// Check audit key.
	auditKey := keys[1]
	if auditKey["use"] != "audit" {
		t.Errorf("expected use audit, got %v", auditKey["use"])
	}
	if auditKey["kid"] != km.AuditKID() {
		t.Errorf("expected kid %q, got %v", km.AuditKID(), auditKey["kid"])
	}
}

func TestJWKSPublicKeysCanVerify(t *testing.T) {
	km, err := NewKeyManager("")
	if err != nil {
		t.Fatal(err)
	}

	jwks := ToJWKS(km)
	keys := jwks["keys"].([]map[string]any)

	// Extract the delegation public key from JWKS and verify a JWT.
	delKeyMap := keys[0]
	pub, err := ECPublicKeyFromJWKMap(delKeyMap)
	if err != nil {
		t.Fatal(err)
	}

	claims := map[string]any{
		"jti": "jwks-test",
		"aud": "test",
		"exp": float64(time.Now().Add(time.Hour).Unix()),
	}

	token, err := SignDelegationJWT(km, claims)
	if err != nil {
		t.Fatal(err)
	}

	decoded, err := VerifyJWTWithKey(pub, token, "", "test")
	if err != nil {
		t.Fatalf("verification with JWKS-derived key failed: %v", err)
	}

	if decoded["jti"] != "jwks-test" {
		t.Errorf("expected jti %q, got %v", "jwks-test", decoded["jti"])
	}
}

func TestParseJWTUnverified(t *testing.T) {
	km, err := NewKeyManager("")
	if err != nil {
		t.Fatal(err)
	}

	claims := map[string]any{
		"jti": "parse-test",
		"iss": "service",
		"sub": "agent:test",
		"aud": "service",
		"exp": float64(time.Now().Add(time.Hour).Unix()),
	}

	token, err := SignDelegationJWT(km, claims)
	if err != nil {
		t.Fatal(err)
	}

	header, decoded, err := ParseJWTUnverified(token)
	if err != nil {
		t.Fatal(err)
	}

	if header["alg"] != "ES256" {
		t.Errorf("expected alg ES256, got %v", header["alg"])
	}
	if header["kid"] != km.DelegationKID() {
		t.Errorf("expected kid %q, got %v", km.DelegationKID(), header["kid"])
	}
	if decoded["jti"] != "parse-test" {
		t.Errorf("expected jti %q, got %v", "parse-test", decoded["jti"])
	}
}

func TestSignAuditEntry(t *testing.T) {
	km, err := NewKeyManager("")
	if err != nil {
		t.Fatal(err)
	}

	entry := map[string]any{
		"sequence_number": 1,
		"timestamp":       "2026-03-20T12:00:00Z",
		"capability":      "search_flights",
		"success":         true,
		"signature":       "", // should be excluded
		"id":              5,  // should be excluded
	}

	sig, err := km.SignAuditEntry(entry)
	if err != nil {
		t.Fatal(err)
	}

	if sig == "" {
		t.Error("expected non-empty signature")
	}

	// The signature should be a valid JWT.
	_, claims, err := ParseJWTUnverified(sig)
	if err != nil {
		t.Fatal(err)
	}

	if _, ok := claims["audit_hash"]; !ok {
		t.Error("expected audit_hash claim in signature JWT")
	}
}

func TestKIDDeterministic(t *testing.T) {
	// The same public key should always produce the same KID.
	key, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		t.Fatal(err)
	}

	kid1 := computeKID(&key.PublicKey)
	kid2 := computeKID(&key.PublicKey)

	if kid1 != kid2 {
		t.Errorf("KID should be deterministic: %q vs %q", kid1, kid2)
	}

	if len(kid1) != 16 {
		t.Errorf("KID should be 16 chars, got %d", len(kid1))
	}
}
