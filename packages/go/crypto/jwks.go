package crypto

import (
	"crypto/ecdsa"
	"encoding/base64"
)

// ToJWKS serializes both public keys as a JWKS (JSON Web Key Set).
// Returns a map suitable for JSON serialization as {"keys": [...]}.
func ToJWKS(km *KeyManager) map[string]any {
	return map[string]any{
		"keys": []map[string]any{
			ecPublicKeyToJWKMap(km.delegationPublic, km.delegationKID, "sig"),
			ecPublicKeyToJWKMap(km.auditPublic, km.auditKID, "audit"),
		},
	}
}

// ecPublicKeyToJWKMap converts an EC public key to a JWK map.
func ecPublicKeyToJWKMap(pub *ecdsa.PublicKey, kid string, use string) map[string]any {
	x := pub.X.Bytes()
	y := pub.Y.Bytes()

	// Pad to 32 bytes.
	if len(x) < 32 {
		padded := make([]byte, 32)
		copy(padded[32-len(x):], x)
		x = padded
	}
	if len(y) < 32 {
		padded := make([]byte, 32)
		copy(padded[32-len(y):], y)
		y = padded
	}

	return map[string]any{
		"kty": "EC",
		"crv": "P-256",
		"x":   base64.RawURLEncoding.EncodeToString(x),
		"y":   base64.RawURLEncoding.EncodeToString(y),
		"kid": kid,
		"alg": "ES256",
		"use": use,
	}
}
