package crypto

import (
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"math/big"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

// KeyManager manages two ES256 key pairs: one for delegation tokens, one for audit entries.
type KeyManager struct {
	delegationPrivate *ecdsa.PrivateKey
	delegationPublic  *ecdsa.PublicKey
	delegationKID     string

	auditPrivate *ecdsa.PrivateKey
	auditPublic  *ecdsa.PublicKey
	auditKID     string
}

// persistedKeys is the on-disk JSON format for key storage.
type persistedKeys struct {
	DelegationJWK map[string]string `json:"delegationJwk"`
	DelegationKID string            `json:"delegationKid"`
	AuditJWK      map[string]string `json:"auditJwk"`
	AuditKID      string            `json:"auditKid"`
}

// NewKeyManager creates a KeyManager by loading keys from keyPath or generating new ones.
// If keyPath is empty, keys are generated in memory only.
func NewKeyManager(keyPath string) (*KeyManager, error) {
	km := &KeyManager{}

	if keyPath != "" {
		keysFile := keyPath
		// If keyPath is a directory, use a default filename inside it.
		info, err := os.Stat(keyPath)
		if err == nil && info.IsDir() {
			keysFile = filepath.Join(keyPath, "anip-keys.json")
		} else if os.IsNotExist(err) {
			// Determine if it looks like a directory (ends with / or no extension).
			if strings.HasSuffix(keyPath, "/") || filepath.Ext(keyPath) == "" {
				if err := os.MkdirAll(keyPath, 0700); err != nil {
					return nil, fmt.Errorf("create key directory: %w", err)
				}
				keysFile = filepath.Join(keyPath, "anip-keys.json")
			}
		}

		if data, err := os.ReadFile(keysFile); err == nil {
			if err := km.loadFromJSON(data); err != nil {
				return nil, fmt.Errorf("load keys from %s: %w", keysFile, err)
			}
			return km, nil
		}

		// Generate and save.
		if err := km.generate(); err != nil {
			return nil, err
		}
		if err := km.saveToFile(keysFile); err != nil {
			return nil, fmt.Errorf("save keys to %s: %w", keysFile, err)
		}
		return km, nil
	}

	// In-memory only.
	if err := km.generate(); err != nil {
		return nil, err
	}
	return km, nil
}

// generate creates fresh ES256 key pairs.
func (km *KeyManager) generate() error {
	delegationKey, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		return fmt.Errorf("generate delegation key: %w", err)
	}
	km.delegationPrivate = delegationKey
	km.delegationPublic = &delegationKey.PublicKey
	km.delegationKID = computeKID(km.delegationPublic)

	auditKey, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		return fmt.Errorf("generate audit key: %w", err)
	}
	km.auditPrivate = auditKey
	km.auditPublic = &auditKey.PublicKey
	km.auditKID = computeKID(km.auditPublic)

	return nil
}

// computeKID computes a JWK thumbprint (RFC 7638) for an EC P-256 public key,
// then returns the first 16 characters of the base64url-encoded SHA-256 hash.
func computeKID(pub *ecdsa.PublicKey) string {
	// RFC 7638: for EC keys, the thumbprint input is {"crv":"P-256","kty":"EC","x":"...","y":"..."}
	// with members in lexicographic order.
	x := base64url(pub.X.Bytes(), 32)
	y := base64url(pub.Y.Bytes(), 32)

	thumbprintInput := fmt.Sprintf(`{"crv":"P-256","kty":"EC","x":"%s","y":"%s"}`, x, y)
	hash := sha256.Sum256([]byte(thumbprintInput))
	thumbprint := base64.RawURLEncoding.EncodeToString(hash[:])

	if len(thumbprint) > 16 {
		return thumbprint[:16]
	}
	return thumbprint
}

// base64url encodes bytes as base64url without padding, zero-padded to the given field size.
func base64url(b []byte, fieldSize int) string {
	// Pad to field size.
	if len(b) < fieldSize {
		padded := make([]byte, fieldSize)
		copy(padded[fieldSize-len(b):], b)
		b = padded
	}
	return base64.RawURLEncoding.EncodeToString(b)
}

// ecPrivateKeyToJWK serializes an EC private key to a JWK map.
func ecPrivateKeyToJWK(key *ecdsa.PrivateKey) map[string]string {
	return map[string]string{
		"kty": "EC",
		"crv": "P-256",
		"x":   base64url(key.PublicKey.X.Bytes(), 32),
		"y":   base64url(key.PublicKey.Y.Bytes(), 32),
		"d":   base64url(key.D.Bytes(), 32),
	}
}

// ecPublicKeyFromJWK deserializes an EC public key from a JWK map.
func ecPublicKeyFromJWK(jwk map[string]string) (*ecdsa.PublicKey, error) {
	xBytes, err := base64.RawURLEncoding.DecodeString(jwk["x"])
	if err != nil {
		return nil, fmt.Errorf("decode x: %w", err)
	}
	yBytes, err := base64.RawURLEncoding.DecodeString(jwk["y"])
	if err != nil {
		return nil, fmt.Errorf("decode y: %w", err)
	}

	return &ecdsa.PublicKey{
		Curve: elliptic.P256(),
		X:     new(big.Int).SetBytes(xBytes),
		Y:     new(big.Int).SetBytes(yBytes),
	}, nil
}

// ecPrivateKeyFromJWK deserializes an EC private key from a JWK map.
func ecPrivateKeyFromJWK(jwk map[string]string) (*ecdsa.PrivateKey, error) {
	pub, err := ecPublicKeyFromJWK(jwk)
	if err != nil {
		return nil, err
	}
	dBytes, err := base64.RawURLEncoding.DecodeString(jwk["d"])
	if err != nil {
		return nil, fmt.Errorf("decode d: %w", err)
	}
	return &ecdsa.PrivateKey{
		PublicKey: *pub,
		D:        new(big.Int).SetBytes(dBytes),
	}, nil
}

// loadFromJSON loads keys from persisted JSON.
func (km *KeyManager) loadFromJSON(data []byte) error {
	var p persistedKeys
	if err := json.Unmarshal(data, &p); err != nil {
		return err
	}

	delPriv, err := ecPrivateKeyFromJWK(p.DelegationJWK)
	if err != nil {
		return fmt.Errorf("load delegation key: %w", err)
	}
	km.delegationPrivate = delPriv
	km.delegationPublic = &delPriv.PublicKey
	km.delegationKID = p.DelegationKID

	auditPriv, err := ecPrivateKeyFromJWK(p.AuditJWK)
	if err != nil {
		return fmt.Errorf("load audit key: %w", err)
	}
	km.auditPrivate = auditPriv
	km.auditPublic = &auditPriv.PublicKey
	km.auditKID = p.AuditKID

	return nil
}

// saveToFile persists keys to a JSON file.
func (km *KeyManager) saveToFile(path string) error {
	// Ensure parent directory exists.
	dir := filepath.Dir(path)
	if err := os.MkdirAll(dir, 0700); err != nil {
		return err
	}

	p := persistedKeys{
		DelegationJWK: ecPrivateKeyToJWK(km.delegationPrivate),
		DelegationKID: km.delegationKID,
		AuditJWK:      ecPrivateKeyToJWK(km.auditPrivate),
		AuditKID:      km.auditKID,
	}

	data, err := json.MarshalIndent(p, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, data, 0600)
}

// DelegationPrivateKey returns the delegation signing key.
func (km *KeyManager) DelegationPrivateKey() *ecdsa.PrivateKey {
	return km.delegationPrivate
}

// DelegationPublicKey returns the delegation verification key.
func (km *KeyManager) DelegationPublicKey() *ecdsa.PublicKey {
	return km.delegationPublic
}

// DelegationKID returns the key ID for the delegation key.
func (km *KeyManager) DelegationKID() string {
	return km.delegationKID
}

// AuditPrivateKey returns the audit signing key.
func (km *KeyManager) AuditPrivateKey() *ecdsa.PrivateKey {
	return km.auditPrivate
}

// AuditPublicKey returns the audit verification key.
func (km *KeyManager) AuditPublicKey() *ecdsa.PublicKey {
	return km.auditPublic
}

// AuditKID returns the key ID for the audit key.
func (km *KeyManager) AuditKID() string {
	return km.auditKID
}

// SignAuditEntry signs an audit entry's canonical JSON (excluding "signature" and "id" fields).
// Returns a compact JWS containing the SHA-256 hash of the canonical entry.
func (km *KeyManager) SignAuditEntry(entryData map[string]any) (string, error) {
	// Filter out "signature" and "id", sort keys.
	filtered := make(map[string]any)
	keys := make([]string, 0)
	for k, v := range entryData {
		if k == "signature" || k == "id" {
			continue
		}
		filtered[k] = v
		keys = append(keys, k)
	}
	sort.Strings(keys)

	// Build ordered JSON.
	ordered := make(map[string]any)
	for _, k := range keys {
		ordered[k] = filtered[k]
	}
	canonical, err := json.Marshal(ordered)
	if err != nil {
		return "", fmt.Errorf("marshal canonical entry: %w", err)
	}

	hash := sha256.Sum256(canonical)
	hashHex := fmt.Sprintf("%x", hash)

	claims := map[string]any{
		"audit_hash": hashHex,
	}

	return signJWTRaw(km.auditPrivate, km.auditKID, claims)
}
