package crypto

import (
	"crypto/ecdsa"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"math/big"
	"strings"
)

// SignDetachedJWS creates a detached JWS signature for the given payload.
// The result is a compact JWS with an empty payload: "header..signature".
// Used for the X-ANIP-Signature header on manifest responses.
func SignDetachedJWS(km *KeyManager, payload []byte) (string, error) {
	return signDetachedJWSWithKey(km.delegationPrivate, km.delegationKID, payload)
}

// signDetachedJWSWithKey creates a detached JWS with the given key.
func signDetachedJWSWithKey(key *ecdsa.PrivateKey, kid string, payload []byte) (string, error) {
	header := map[string]string{
		"alg": "ES256",
		"kid": kid,
	}

	headerJSON, err := json.Marshal(header)
	if err != nil {
		return "", fmt.Errorf("marshal header: %w", err)
	}

	headerB64 := base64.RawURLEncoding.EncodeToString(headerJSON)
	payloadB64 := base64.RawURLEncoding.EncodeToString(payload)

	// The signing input includes the payload, but the output omits it.
	signingInput := headerB64 + "." + payloadB64
	hash := sha256.Sum256([]byte(signingInput))

	r, s, err := ecdsa.Sign(cryptoRandReader(), key, hash[:])
	if err != nil {
		return "", fmt.Errorf("sign: %w", err)
	}

	sigBytes := make([]byte, 64)
	rBytes := r.Bytes()
	sBytes := s.Bytes()
	copy(sigBytes[32-len(rBytes):32], rBytes)
	copy(sigBytes[64-len(sBytes):64], sBytes)

	sigB64 := base64.RawURLEncoding.EncodeToString(sigBytes)

	// Detached: omit the payload part.
	return headerB64 + ".." + sigB64, nil
}

// VerifyDetachedJWS verifies a detached JWS signature against the given payload.
func VerifyDetachedJWS(km *KeyManager, payload []byte, signature string) error {
	return VerifyDetachedJWSWithKey(km.delegationPublic, payload, signature)
}

// VerifyDetachedJWSWithKey verifies a detached JWS using a raw public key.
func VerifyDetachedJWSWithKey(pub *ecdsa.PublicKey, payload []byte, signature string) error {
	parts := strings.SplitN(signature, ".", 3)
	if len(parts) != 3 {
		return errors.New("invalid detached JWS format: expected 3 parts")
	}

	headerB64, middle, sigB64 := parts[0], parts[1], parts[2]

	if middle != "" {
		return errors.New("invalid detached JWS: payload part should be empty")
	}

	// Verify header.
	headerJSON, err := base64.RawURLEncoding.DecodeString(headerB64)
	if err != nil {
		return fmt.Errorf("decode header: %w", err)
	}

	var header map[string]string
	if err := json.Unmarshal(headerJSON, &header); err != nil {
		return fmt.Errorf("unmarshal header: %w", err)
	}

	if header["alg"] != "ES256" {
		return fmt.Errorf("unsupported algorithm: %s", header["alg"])
	}

	// Reconstruct signing input with the payload.
	payloadB64 := base64.RawURLEncoding.EncodeToString(payload)
	signingInput := headerB64 + "." + payloadB64
	hash := sha256.Sum256([]byte(signingInput))

	sigBytes, err := base64.RawURLEncoding.DecodeString(sigB64)
	if err != nil {
		return fmt.Errorf("decode signature: %w", err)
	}

	if len(sigBytes) != 64 {
		return fmt.Errorf("invalid signature length: %d", len(sigBytes))
	}

	r := new(big.Int).SetBytes(sigBytes[:32])
	s := new(big.Int).SetBytes(sigBytes[32:])

	if !ecdsa.Verify(pub, hash[:], r, s) {
		return errors.New("invalid signature")
	}

	return nil
}

// SignDetachedJWSAudit creates a detached JWS using the audit key pair.
func SignDetachedJWSAudit(km *KeyManager, payload []byte) (string, error) {
	return signDetachedJWSWithKey(km.auditPrivate, km.auditKID, payload)
}
