package main

import (
	"crypto"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"math/big"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

// Test RSA key pair for signing OIDC tokens.
var testPrivateKey *rsa.PrivateKey
var testPublicJWK map[string]any

func init() {
	var err error
	testPrivateKey, err = rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		panic(err)
	}

	// Build JWK from public key.
	pub := testPrivateKey.PublicKey
	testPublicJWK = map[string]any{
		"kty": "RSA",
		"alg": "RS256",
		"use": "sig",
		"kid": "test-key-1",
		"n":   base64.RawURLEncoding.EncodeToString(pub.N.Bytes()),
		"e":   base64.RawURLEncoding.EncodeToString(big.NewInt(int64(pub.E)).Bytes()),
	}
}

// startJWKSServer starts a local HTTP server serving OIDC discovery + JWKS.
func startJWKSServer(t *testing.T) string {
	t.Helper()
	mux := http.NewServeMux()
	var serverURL string

	mux.HandleFunc("/.well-known/openid-configuration", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]any{
			"issuer":   serverURL,
			"jwks_uri": serverURL + "/jwks",
		})
	})
	mux.HandleFunc("/jwks", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]any{
			"keys": []any{testPublicJWK},
		})
	})

	ts := httptest.NewServer(mux)
	serverURL = ts.URL
	t.Cleanup(ts.Close)
	return ts.URL
}

// signTestToken creates a signed RS256 JWT.
func signTestToken(t *testing.T, issuer, audience string, claims map[string]any, expOffset time.Duration) string {
	t.Helper()

	header := map[string]any{"alg": "RS256", "typ": "JWT", "kid": "test-key-1"}
	headerJSON, _ := json.Marshal(header)
	headerB64 := base64.RawURLEncoding.EncodeToString(headerJSON)

	now := time.Now()
	payload := map[string]any{
		"iss": issuer,
		"aud": audience,
		"iat": now.Unix(),
		"exp": now.Add(expOffset).Unix(),
	}
	for k, v := range claims {
		payload[k] = v
	}
	payloadJSON, _ := json.Marshal(payload)
	payloadB64 := base64.RawURLEncoding.EncodeToString(payloadJSON)

	signingInput := headerB64 + "." + payloadB64
	hash := sha256.Sum256([]byte(signingInput))
	sig, err := rsa.SignPKCS1v15(rand.Reader, testPrivateKey, crypto.SHA256, hash[:])
	if err != nil {
		t.Fatal(err)
	}
	sigB64 := base64.RawURLEncoding.EncodeToString(sig)

	return headerB64 + "." + payloadB64 + "." + sigB64
}

func TestOIDC_ValidTokenWithEmail(t *testing.T) {
	issuer := startJWKSServer(t)
	v := NewOIDCValidator(issuer, "test-audience", "")
	token := signTestToken(t, issuer, "test-audience", map[string]any{"email": "samir@example.com"}, time.Hour)
	principal, ok := v.Validate(token)
	if !ok {
		t.Fatal("expected validation to succeed")
	}
	if principal != "human:samir@example.com" {
		t.Fatalf("expected human:samir@example.com, got %s", principal)
	}
}

func TestOIDC_ValidTokenWithUsername(t *testing.T) {
	issuer := startJWKSServer(t)
	v := NewOIDCValidator(issuer, "test-audience", "")
	token := signTestToken(t, issuer, "test-audience", map[string]any{"preferred_username": "samir", "sub": "u1"}, time.Hour)
	principal, ok := v.Validate(token)
	if !ok {
		t.Fatal("expected validation to succeed")
	}
	if principal != "human:samir" {
		t.Fatalf("expected human:samir, got %s", principal)
	}
}

func TestOIDC_ValidTokenSubOnly(t *testing.T) {
	issuer := startJWKSServer(t)
	v := NewOIDCValidator(issuer, "test-audience", "")
	token := signTestToken(t, issuer, "test-audience", map[string]any{"sub": "service-xyz"}, time.Hour)
	principal, ok := v.Validate(token)
	if !ok {
		t.Fatal("expected validation to succeed")
	}
	if principal != "oidc:service-xyz" {
		t.Fatalf("expected oidc:service-xyz, got %s", principal)
	}
}

func TestOIDC_ExpiredToken(t *testing.T) {
	issuer := startJWKSServer(t)
	v := NewOIDCValidator(issuer, "test-audience", "")
	token := signTestToken(t, issuer, "test-audience", map[string]any{"email": "x@x.com"}, -time.Hour)
	_, ok := v.Validate(token)
	if ok {
		t.Fatal("expected validation to fail for expired token")
	}
}

func TestOIDC_WrongIssuer(t *testing.T) {
	issuer := startJWKSServer(t)
	v := NewOIDCValidator("https://wrong-issuer.example.com", "test-audience", fmt.Sprintf("%s/jwks", issuer))
	token := signTestToken(t, issuer, "test-audience", map[string]any{"email": "x@x.com"}, time.Hour)
	_, ok := v.Validate(token)
	if ok {
		t.Fatal("expected validation to fail for wrong issuer")
	}
}

func TestOIDC_WrongAudience(t *testing.T) {
	issuer := startJWKSServer(t)
	v := NewOIDCValidator(issuer, "wrong-audience", "")
	token := signTestToken(t, issuer, "test-audience", map[string]any{"email": "x@x.com"}, time.Hour)
	_, ok := v.Validate(token)
	if ok {
		t.Fatal("expected validation to fail for wrong audience")
	}
}

func TestOIDC_InvalidSignature(t *testing.T) {
	issuer := startJWKSServer(t)
	v := NewOIDCValidator(issuer, "test-audience", "")

	// Sign with a different key.
	otherKey, _ := rsa.GenerateKey(rand.Reader, 2048)
	header := map[string]any{"alg": "RS256", "typ": "JWT", "kid": "test-key-1"}
	headerJSON, _ := json.Marshal(header)
	headerB64 := base64.RawURLEncoding.EncodeToString(headerJSON)
	payload := map[string]any{
		"iss": issuer, "aud": "test-audience", "email": "x@x.com",
		"iat": time.Now().Unix(), "exp": time.Now().Add(time.Hour).Unix(),
	}
	payloadJSON, _ := json.Marshal(payload)
	payloadB64 := base64.RawURLEncoding.EncodeToString(payloadJSON)
	hash := sha256.Sum256([]byte(headerB64 + "." + payloadB64))
	sig, _ := rsa.SignPKCS1v15(rand.Reader, otherKey, crypto.SHA256, hash[:])
	token := headerB64 + "." + payloadB64 + "." + base64.RawURLEncoding.EncodeToString(sig)

	_, ok := v.Validate(token)
	if ok {
		t.Fatal("expected validation to fail for invalid signature")
	}
}

func TestOIDC_JWKSFetchFailure(t *testing.T) {
	v := NewOIDCValidator("http://localhost:1", "test-audience", "http://localhost:1/jwks")
	_, ok := v.Validate("not-a-jwt")
	if ok {
		t.Fatal("expected validation to fail")
	}
}

func TestOIDC_NonJWTString(t *testing.T) {
	issuer := startJWKSServer(t)
	v := NewOIDCValidator(issuer, "test-audience", "")
	_, ok := v.Validate("not-a-jwt")
	if ok {
		t.Fatal("expected validation to fail for non-JWT")
	}
}

func TestOIDC_ExplicitJWKSURL(t *testing.T) {
	issuer := startJWKSServer(t)
	v := NewOIDCValidator(issuer, "test-audience", issuer+"/jwks")
	token := signTestToken(t, issuer, "test-audience", map[string]any{"email": "direct@example.com"}, time.Hour)
	principal, ok := v.Validate(token)
	if !ok {
		t.Fatal("expected validation to succeed with explicit JWKS URL")
	}
	if principal != "human:direct@example.com" {
		t.Fatalf("expected human:direct@example.com, got %s", principal)
	}
}

func TestOIDC_KeyRotationRefresh(t *testing.T) {
	// Generate a second key pair.
	rotatedKey, _ := rsa.GenerateKey(rand.Reader, 2048)
	rotatedPub := rotatedKey.PublicKey
	rotatedJWK := map[string]any{
		"kty": "RSA", "alg": "RS256", "use": "sig", "kid": "rotated-key-2",
		"n": base64.RawURLEncoding.EncodeToString(rotatedPub.N.Bytes()),
		"e": base64.RawURLEncoding.EncodeToString(big.NewInt(int64(rotatedPub.E)).Bytes()),
	}

	// Server that serves both keys.
	mux := http.NewServeMux()
	var serverURL string
	mux.HandleFunc("/.well-known/openid-configuration", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]any{"issuer": serverURL, "jwks_uri": serverURL + "/jwks"})
	})
	mux.HandleFunc("/jwks", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]any{"keys": []any{testPublicJWK, rotatedJWK}})
	})
	ts := httptest.NewServer(mux)
	serverURL = ts.URL
	t.Cleanup(ts.Close)

	v := NewOIDCValidator(serverURL, "test-audience", "")

	// First call with original key — caches JWKS.
	token1 := signTestToken(t, serverURL, "test-audience", map[string]any{"email": "first@example.com"}, time.Hour)
	p1, ok := v.Validate(token1)
	if !ok || p1 != "human:first@example.com" {
		t.Fatalf("first validation failed: %s %v", p1, ok)
	}

	// Second call with rotated kid — triggers JWKS refresh.
	header := map[string]any{"alg": "RS256", "typ": "JWT", "kid": "rotated-key-2"}
	headerJSON, _ := json.Marshal(header)
	headerB64 := base64.RawURLEncoding.EncodeToString(headerJSON)
	payload := map[string]any{
		"iss": serverURL, "aud": "test-audience", "email": "rotated@example.com",
		"iat": time.Now().Unix(), "exp": time.Now().Add(time.Hour).Unix(),
	}
	payloadJSON, _ := json.Marshal(payload)
	payloadB64 := base64.RawURLEncoding.EncodeToString(payloadJSON)
	sigInput := headerB64 + "." + payloadB64
	hash := sha256.Sum256([]byte(sigInput))
	sig, _ := rsa.SignPKCS1v15(rand.Reader, rotatedKey, crypto.SHA256, hash[:])
	token2 := headerB64 + "." + payloadB64 + "." + base64.RawURLEncoding.EncodeToString(sig)

	p2, ok := v.Validate(token2)
	if !ok {
		t.Fatal("rotated key validation failed — JWKS refresh did not work")
	}
	if !strings.Contains(p2, "rotated@example.com") {
		t.Fatalf("expected rotated@example.com principal, got %s", p2)
	}
}
