// OIDC token validation for the ANIP Go example app.
//
// Validates external OIDC/OAuth2 JWTs against a provider's JWKS endpoint.
// Maps OIDC claims to ANIP principal identifiers.
//
// This is example-app code, not an SDK package. Real deployments should
// define their own claim-to-principal mapping policy.
package main

import (
	"crypto"
	"crypto/rsa"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"math/big"
	"net/http"
	"strings"
	"sync"
	"time"
)

// OIDCValidator validates OIDC bearer tokens and maps claims to ANIP principals.
//
// Fully synchronous — the Go service authenticate callback is sync.
// JWKS discovery and fetching use net/http. JWKS keys are cached with
// retry-on-miss for key rotation.
type OIDCValidator struct {
	issuerURL string
	audience  string
	jwksURL   string

	mu   sync.RWMutex
	keys map[string]*rsa.PublicKey // kid -> public key
}

// NewOIDCValidator creates a new OIDC validator.
// jwksURL may be empty, in which case it will be discovered from the issuer.
func NewOIDCValidator(issuerURL, audience, jwksURL string) *OIDCValidator {
	return &OIDCValidator{
		issuerURL: strings.TrimRight(issuerURL, "/"),
		audience:  audience,
		jwksURL:   jwksURL,
	}
}

// Validate validates an OIDC bearer token and returns an ANIP principal.
// Returns ("", false) if validation fails for any reason.
func (v *OIDCValidator) Validate(bearer string) (string, bool) {
	// Parse JWT header to get kid and alg (without verifying signature).
	header, claims, err := parseJWTUnverified(bearer)
	if err != nil {
		return "", false
	}

	alg, _ := header["alg"].(string)
	if alg != "RS256" {
		return "", false
	}

	kid, _ := header["kid"].(string)
	if kid == "" {
		return "", false
	}

	// Get the public key for this kid.
	key := v.getKey(kid)
	if key == nil {
		// Key not in cache — refresh JWKS and retry (key rotation).
		v.refreshJWKS()
		key = v.getKey(kid)
	}
	if key == nil {
		return "", false
	}

	// Verify signature.
	if err := verifyRS256(bearer, key); err != nil {
		return "", false
	}

	// Verify standard claims.
	if !v.verifyClaims(claims) {
		return "", false
	}

	// Map claims to ANIP principal.
	principal := mapClaimsToPrincipal(claims)
	if principal == "" {
		return "", false
	}

	return principal, true
}

// getKey returns the cached public key for the given kid, or nil.
func (v *OIDCValidator) getKey(kid string) *rsa.PublicKey {
	v.mu.RLock()
	defer v.mu.RUnlock()
	if v.keys == nil {
		return nil
	}
	return v.keys[kid]
}

// refreshJWKS fetches the JWKS from the provider and updates the cache.
func (v *OIDCValidator) refreshJWKS() {
	jwksURL := v.jwksURL

	// Discover JWKS URL from OIDC discovery if not explicitly set.
	if jwksURL == "" {
		discoveryURL := v.issuerURL + "/.well-known/openid-configuration"
		client := &http.Client{Timeout: 10 * time.Second}
		resp, err := client.Get(discoveryURL)
		if err != nil {
			return
		}
		defer resp.Body.Close()
		if resp.StatusCode != http.StatusOK {
			return
		}
		var doc struct {
			JWKSURI string `json:"jwks_uri"`
		}
		if err := json.NewDecoder(resp.Body).Decode(&doc); err != nil || doc.JWKSURI == "" {
			return
		}
		jwksURL = doc.JWKSURI
		v.jwksURL = jwksURL
	}

	// Fetch JWKS.
	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Get(jwksURL)
	if err != nil {
		return
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return
	}

	var jwks struct {
		Keys []json.RawMessage `json:"keys"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&jwks); err != nil {
		return
	}

	keys := make(map[string]*rsa.PublicKey)
	for _, raw := range jwks.Keys {
		var jwk map[string]any
		if err := json.Unmarshal(raw, &jwk); err != nil {
			continue
		}
		kty, _ := jwk["kty"].(string)
		kid, _ := jwk["kid"].(string)
		if kty != "RSA" || kid == "" {
			continue
		}
		pub, err := rsaPublicKeyFromJWK(jwk)
		if err != nil {
			continue
		}
		keys[kid] = pub
	}

	v.mu.Lock()
	v.keys = keys
	v.mu.Unlock()
}

// verifyClaims checks issuer, audience, and expiry.
func (v *OIDCValidator) verifyClaims(claims map[string]any) bool {
	// Check issuer.
	iss, _ := claims["iss"].(string)
	if iss != v.issuerURL {
		return false
	}

	// Check audience.
	switch aud := claims["aud"].(type) {
	case string:
		if aud != v.audience {
			return false
		}
	case []any:
		found := false
		for _, a := range aud {
			if aStr, ok := a.(string); ok && aStr == v.audience {
				found = true
				break
			}
		}
		if !found {
			return false
		}
	default:
		return false
	}

	// Check expiry.
	exp, ok := claims["exp"].(float64)
	if !ok {
		return false
	}
	if time.Now().Unix() > int64(exp) {
		return false
	}

	return true
}

// mapClaimsToPrincipal maps OIDC JWT claims to an ANIP principal identifier.
//
// Deployment policy, not protocol meaning:
//   - email -> "human:{email}"
//   - preferred_username -> "human:{username}"
//   - sub -> "oidc:{sub}"
func mapClaimsToPrincipal(claims map[string]any) string {
	if email, ok := claims["email"].(string); ok && email != "" {
		return "human:" + email
	}
	if username, ok := claims["preferred_username"].(string); ok && username != "" {
		return "human:" + username
	}
	if sub, ok := claims["sub"].(string); ok && sub != "" {
		return "oidc:" + sub
	}
	return ""
}

// --- JWT parsing and RS256 verification using crypto/rsa ---

// parseJWTUnverified decodes a JWT without verifying the signature.
// Returns the header and claims as maps.
func parseJWTUnverified(tokenStr string) (header map[string]any, claims map[string]any, err error) {
	parts := strings.SplitN(tokenStr, ".", 3)
	if len(parts) != 3 {
		return nil, nil, fmt.Errorf("invalid JWT format")
	}

	headerJSON, err := base64.RawURLEncoding.DecodeString(parts[0])
	if err != nil {
		return nil, nil, fmt.Errorf("decode header: %w", err)
	}
	if err := json.Unmarshal(headerJSON, &header); err != nil {
		return nil, nil, fmt.Errorf("unmarshal header: %w", err)
	}

	claimsJSON, err := base64.RawURLEncoding.DecodeString(parts[1])
	if err != nil {
		return nil, nil, fmt.Errorf("decode claims: %w", err)
	}
	if err := json.Unmarshal(claimsJSON, &claims); err != nil {
		return nil, nil, fmt.Errorf("unmarshal claims: %w", err)
	}

	return header, claims, nil
}

// verifyRS256 verifies an RS256 JWT signature using the given public key.
func verifyRS256(tokenStr string, pub *rsa.PublicKey) error {
	parts := strings.SplitN(tokenStr, ".", 3)
	if len(parts) != 3 {
		return fmt.Errorf("invalid JWT format")
	}

	signingInput := []byte(parts[0] + "." + parts[1])

	sigBytes, err := base64.RawURLEncoding.DecodeString(parts[2])
	if err != nil {
		return fmt.Errorf("decode signature: %w", err)
	}

	// RS256 = RSASSA-PKCS1-v1_5 with SHA-256
	hash := sha256.Sum256(signingInput)
	return rsa.VerifyPKCS1v15(pub, crypto.SHA256, hash[:], sigBytes)
}

// rsaPublicKeyFromJWK creates an *rsa.PublicKey from a JWK map with kty=RSA.
func rsaPublicKeyFromJWK(jwk map[string]any) (*rsa.PublicKey, error) {
	nStr, _ := jwk["n"].(string)
	eStr, _ := jwk["e"].(string)
	if nStr == "" || eStr == "" {
		return nil, fmt.Errorf("missing n or e in RSA JWK")
	}

	nBytes, err := base64.RawURLEncoding.DecodeString(nStr)
	if err != nil {
		return nil, fmt.Errorf("decode n: %w", err)
	}
	eBytes, err := base64.RawURLEncoding.DecodeString(eStr)
	if err != nil {
		return nil, fmt.Errorf("decode e: %w", err)
	}

	n := new(big.Int).SetBytes(nBytes)
	e := new(big.Int).SetBytes(eBytes)
	if !e.IsInt64() {
		return nil, fmt.Errorf("exponent too large")
	}

	return &rsa.PublicKey{
		N: n,
		E: int(e.Int64()),
	}, nil
}
