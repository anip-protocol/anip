package crypto

import (
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math/big"
	"strings"
	"time"
)

// SignDelegationJWT signs a delegation token as an ES256 JWT.
// The claims map should include standard JWT claims (jti, iss, sub, aud, iat, exp)
// plus ANIP claims (scope, root_principal, capability, parent_token_id, purpose, constraints).
func SignDelegationJWT(km *KeyManager, claims map[string]any) (string, error) {
	return signJWTRaw(km.delegationPrivate, km.delegationKID, claims)
}

// signJWTRaw creates a compact JWS with ES256 using the given key.
func signJWTRaw(key *ecdsa.PrivateKey, kid string, claims map[string]any) (string, error) {
	// Build header.
	header := map[string]string{
		"alg": "ES256",
		"typ": "JWT",
		"kid": kid,
	}

	headerJSON, err := json.Marshal(header)
	if err != nil {
		return "", fmt.Errorf("marshal header: %w", err)
	}

	claimsJSON, err := json.Marshal(claims)
	if err != nil {
		return "", fmt.Errorf("marshal claims: %w", err)
	}

	headerB64 := base64.RawURLEncoding.EncodeToString(headerJSON)
	claimsB64 := base64.RawURLEncoding.EncodeToString(claimsJSON)
	signingInput := headerB64 + "." + claimsB64

	// Sign with ES256 (ECDSA P-256 + SHA-256).
	hash := sha256.Sum256([]byte(signingInput))
	r, s, err := ecdsa.Sign(cryptoRandReader(), key, hash[:])
	if err != nil {
		return "", fmt.Errorf("sign: %w", err)
	}

	// Encode r and s as fixed-size 32-byte big-endian values per RFC 7515.
	sigBytes := make([]byte, 64)
	rBytes := r.Bytes()
	sBytes := s.Bytes()
	copy(sigBytes[32-len(rBytes):32], rBytes)
	copy(sigBytes[64-len(sBytes):64], sBytes)

	sigB64 := base64.RawURLEncoding.EncodeToString(sigBytes)

	return signingInput + "." + sigB64, nil
}

// VerifyDelegationJWT verifies and decodes an ES256 JWT signed by the delegation key.
// It checks the signature, expiration, issuer (if provided), and audience.
func VerifyDelegationJWT(km *KeyManager, tokenStr string, issuer string, audience string) (map[string]any, error) {
	return verifyJWT(km.delegationPublic, tokenStr, issuer, audience)
}

// verifyJWT verifies an ES256 JWT against a public key.
func verifyJWT(pub *ecdsa.PublicKey, tokenStr string, issuer string, audience string) (map[string]any, error) {
	parts := strings.SplitN(tokenStr, ".", 3)
	if len(parts) != 3 {
		return nil, errors.New("invalid JWT format: expected 3 parts")
	}

	headerB64, claimsB64, sigB64 := parts[0], parts[1], parts[2]

	// Verify header.
	headerJSON, err := base64.RawURLEncoding.DecodeString(headerB64)
	if err != nil {
		return nil, fmt.Errorf("decode header: %w", err)
	}

	var header map[string]string
	if err := json.Unmarshal(headerJSON, &header); err != nil {
		return nil, fmt.Errorf("unmarshal header: %w", err)
	}

	if header["alg"] != "ES256" {
		return nil, fmt.Errorf("unsupported algorithm: %s", header["alg"])
	}

	// Verify signature.
	signingInput := headerB64 + "." + claimsB64
	hash := sha256.Sum256([]byte(signingInput))

	sigBytes, err := base64.RawURLEncoding.DecodeString(sigB64)
	if err != nil {
		return nil, fmt.Errorf("decode signature: %w", err)
	}

	if len(sigBytes) != 64 {
		return nil, fmt.Errorf("invalid signature length: %d", len(sigBytes))
	}

	r := new(big.Int).SetBytes(sigBytes[:32])
	s := new(big.Int).SetBytes(sigBytes[32:])

	if !ecdsa.Verify(pub, hash[:], r, s) {
		return nil, errors.New("invalid signature")
	}

	// Decode claims.
	claimsJSON, err := base64.RawURLEncoding.DecodeString(claimsB64)
	if err != nil {
		return nil, fmt.Errorf("decode claims: %w", err)
	}

	var claims map[string]any
	if err := json.Unmarshal(claimsJSON, &claims); err != nil {
		return nil, fmt.Errorf("unmarshal claims: %w", err)
	}

	// Check expiration.
	if exp, ok := claims["exp"]; ok {
		var expTime float64
		switch v := exp.(type) {
		case float64:
			expTime = v
		case json.Number:
			expTime, _ = v.Float64()
		}
		if expTime > 0 && time.Now().Unix() > int64(expTime) {
			return nil, errors.New("token expired")
		}
	}

	// Check issuer.
	if issuer != "" {
		if iss, ok := claims["iss"]; ok {
			if issStr, ok := iss.(string); ok && issStr != issuer {
				return nil, fmt.Errorf("issuer mismatch: expected %q, got %q", issuer, issStr)
			}
		}
	}

	// Check audience.
	if audience != "" {
		if aud, ok := claims["aud"]; ok {
			switch v := aud.(type) {
			case string:
				if v != audience {
					return nil, fmt.Errorf("audience mismatch: expected %q, got %q", audience, v)
				}
			case []any:
				found := false
				for _, a := range v {
					if aStr, ok := a.(string); ok && aStr == audience {
						found = true
						break
					}
				}
				if !found {
					return nil, fmt.Errorf("audience %q not in token audiences", audience)
				}
			}
		}
	}

	return claims, nil
}

// VerifyJWTWithKey verifies a JWT using a raw public key (for testing or external keys).
func VerifyJWTWithKey(pub *ecdsa.PublicKey, tokenStr string, issuer string, audience string) (map[string]any, error) {
	return verifyJWT(pub, tokenStr, issuer, audience)
}

// cryptoRandReader returns crypto/rand.Reader.
func cryptoRandReader() io.Reader {
	return rand.Reader
}

// ParseJWTUnverified decodes a JWT without verifying its signature.
// Returns the header and claims. Useful for extracting the kid before verification.
func ParseJWTUnverified(tokenStr string) (header map[string]string, claims map[string]any, err error) {
	parts := strings.SplitN(tokenStr, ".", 3)
	if len(parts) != 3 {
		return nil, nil, errors.New("invalid JWT format")
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

// ECPublicKeyFromJWKMap creates an ecdsa.PublicKey from a JWK map (for testing/JWKS consumption).
func ECPublicKeyFromJWKMap(jwk map[string]any) (*ecdsa.PublicKey, error) {
	kty, _ := jwk["kty"].(string)
	crv, _ := jwk["crv"].(string)
	xStr, _ := jwk["x"].(string)
	yStr, _ := jwk["y"].(string)

	if kty != "EC" || crv != "P-256" {
		return nil, fmt.Errorf("unsupported key type: kty=%s crv=%s", kty, crv)
	}

	xBytes, err := base64.RawURLEncoding.DecodeString(xStr)
	if err != nil {
		return nil, fmt.Errorf("decode x: %w", err)
	}
	yBytes, err := base64.RawURLEncoding.DecodeString(yStr)
	if err != nil {
		return nil, fmt.Errorf("decode y: %w", err)
	}

	return &ecdsa.PublicKey{
		Curve: elliptic.P256(),
		X:     new(big.Int).SetBytes(xBytes),
		Y:     new(big.Int).SetBytes(yBytes),
	}, nil
}
