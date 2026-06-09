package registryapi

import (
	"crypto/ed25519"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"strings"
)

const (
	SignatureAlgorithmEd25519 = "ed25519"
	defaultRegistryKeyID      = "anip-registry-dev-ed25519-v1"
)

type RegistrySigner struct {
	KeyID      string
	PrivateKey ed25519.PrivateKey
	PublicKey  ed25519.PublicKey
}

func NewRegistrySigner(keyID string, privateKey ed25519.PrivateKey) (*RegistrySigner, error) {
	if strings.TrimSpace(keyID) == "" {
		return nil, errors.New("registry signer key id is required")
	}
	if len(privateKey) != ed25519.PrivateKeySize {
		return nil, fmt.Errorf("registry signer private key must be %d bytes", ed25519.PrivateKeySize)
	}
	publicKey, ok := privateKey.Public().(ed25519.PublicKey)
	if !ok {
		return nil, errors.New("derive registry signer public key")
	}
	return &RegistrySigner{
		KeyID:      keyID,
		PrivateKey: privateKey,
		PublicKey:  publicKey,
	}, nil
}

func NewRegistrySignerFromBase64(keyID string, encoded string) (*RegistrySigner, error) {
	raw, err := base64.StdEncoding.DecodeString(strings.TrimSpace(encoded))
	if err != nil {
		return nil, fmt.Errorf("decode registry private key: %w", err)
	}
	switch len(raw) {
	case ed25519.SeedSize:
		return NewRegistrySigner(keyID, ed25519.NewKeyFromSeed(raw))
	case ed25519.PrivateKeySize:
		return NewRegistrySigner(keyID, ed25519.PrivateKey(raw))
	default:
		return nil, fmt.Errorf("registry private key must decode to %d-byte seed or %d-byte private key", ed25519.SeedSize, ed25519.PrivateKeySize)
	}
}

func NewRegistryPublicKeyFromBase64(keyID string, encoded string) (RegistryPublicKey, error) {
	if strings.TrimSpace(keyID) == "" {
		return RegistryPublicKey{}, errors.New("registry public key id is required")
	}
	raw, err := base64.StdEncoding.DecodeString(strings.TrimSpace(encoded))
	if err != nil {
		return RegistryPublicKey{}, fmt.Errorf("decode registry public key: %w", err)
	}
	if len(raw) != ed25519.PublicKeySize {
		return RegistryPublicKey{}, fmt.Errorf("registry public key must decode to %d bytes", ed25519.PublicKeySize)
	}
	return RegistryPublicKey{
		KeyID:     keyID,
		Algorithm: SignatureAlgorithmEd25519,
		PublicKey: base64.StdEncoding.EncodeToString(raw),
	}, nil
}

func ParseRegistryPublicKeyList(value string) ([]RegistryPublicKey, error) {
	value = strings.TrimSpace(value)
	if value == "" {
		return nil, nil
	}
	parts := strings.Split(value, ",")
	keys := make([]RegistryPublicKey, 0, len(parts))
	for _, part := range parts {
		keyID, encoded, ok := strings.Cut(strings.TrimSpace(part), "=")
		if !ok {
			return nil, fmt.Errorf("invalid registry public key entry %q: expected key_id=base64_public_key", part)
		}
		key, err := NewRegistryPublicKeyFromBase64(strings.TrimSpace(keyID), strings.TrimSpace(encoded))
		if err != nil {
			return nil, err
		}
		keys = append(keys, key)
	}
	return keys, nil
}

func NewDevRegistrySigner() *RegistrySigner {
	seed := sha256.Sum256([]byte("anip-registry-dev-local-ed25519-v1"))
	signer, err := NewRegistrySigner(defaultRegistryKeyID, ed25519.NewKeyFromSeed(seed[:]))
	if err != nil {
		panic(err)
	}
	return signer
}

func (s *RegistrySigner) PublicKeyRecord() RegistryPublicKey {
	return RegistryPublicKey{
		KeyID:     s.KeyID,
		Algorithm: SignatureAlgorithmEd25519,
		PublicKey: base64.StdEncoding.EncodeToString(s.PublicKey),
	}
}

func MergeRegistryPublicKeys(active RegistryPublicKey, extras []RegistryPublicKey) []RegistryPublicKey {
	seen := map[string]bool{}
	keys := make([]RegistryPublicKey, 0, 1+len(extras))
	if active.KeyID != "" {
		keys = append(keys, active)
		seen[active.KeyID] = true
	}
	for _, key := range extras {
		if key.KeyID == "" || seen[key.KeyID] {
			continue
		}
		keys = append(keys, key)
		seen[key.KeyID] = true
	}
	return keys
}

func (s *RegistrySigner) SignReceiptPayload(payload any) (string, error) {
	bytes, err := json.Marshal(payload)
	if err != nil {
		return "", err
	}
	signature := ed25519.Sign(s.PrivateKey, bytes)
	return fmt.Sprintf(
		"%s:%s:%s",
		SignatureAlgorithmEd25519,
		s.KeyID,
		base64.StdEncoding.EncodeToString(signature),
	), nil
}

func ParseRegistrySignature(signature string) (algorithm string, keyID string, raw []byte, ok bool) {
	parts := strings.Split(signature, ":")
	if len(parts) != 3 {
		return "", "", nil, false
	}
	decoded, err := base64.StdEncoding.DecodeString(parts[2])
	if err != nil {
		return "", "", nil, false
	}
	return parts[0], parts[1], decoded, true
}

func VerifyRegistrySignature(publicKey ed25519.PublicKey, payload any, signature string) bool {
	algorithm, _, raw, ok := ParseRegistrySignature(signature)
	if !ok || algorithm != SignatureAlgorithmEd25519 || len(publicKey) != ed25519.PublicKeySize {
		return false
	}
	bytes, err := json.Marshal(payload)
	if err != nil {
		return false
	}
	return ed25519.Verify(publicKey, bytes, raw)
}
