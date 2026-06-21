package generator

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"strings"
)

const PackageLockSchemaVersion = "anip-package-lock/v1"

type PackageLock struct {
	LockSchemaVersion         string `json:"lock_schema_version"`
	ArtifactType              string `json:"artifact_type"`
	SourceKind                string `json:"source_kind"`
	RegistryURL               string `json:"registry_url,omitempty"`
	PackageID                 string `json:"package_id"`
	PackageVersion            string `json:"package_version"`
	ContractSignature         string `json:"contract_signature,omitempty"`
	SchemaVersion             string `json:"schema_version,omitempty"`
	DefinitionDigest          string `json:"definition_digest"`
	ManifestDigest            string `json:"manifest_digest,omitempty"`
	LockDigest                string `json:"lock_digest"`
	PackageExecutionSignature string `json:"package_execution_signature,omitempty"`
	ReceiptSignature          string `json:"receipt_signature,omitempty"`
	ReceiptAuthority          string `json:"receipt_authority,omitempty"`
	ReceiptKeyID              string `json:"receipt_key_id,omitempty"`
	ReceiptAlgorithm          string `json:"receipt_algorithm,omitempty"`
	ReceiptIssuedAt           string `json:"receipt_issued_at,omitempty"`
	RegistrySigningMode       string `json:"registry_signing_mode,omitempty"`
	RegistryActiveKeyID       string `json:"registry_active_key_id,omitempty"`
	PublisherID               string `json:"publisher_id,omitempty"`
	PublisherType             string `json:"publisher_type,omitempty"`
}

func LoadPackageLock(path string) (*PackageLock, error) {
	path = strings.TrimSpace(path)
	if path == "" {
		return nil, nil
	}
	bytes, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("read lock file: %w", err)
	}
	var lock PackageLock
	if err := json.Unmarshal(bytes, &lock); err != nil {
		return nil, fmt.Errorf("decode lock file: %w", err)
	}
	if err := lock.ValidateShape(); err != nil {
		return nil, err
	}
	return &lock, nil
}

func WritePackageLock(path string, resolved *ResolvedServiceDefinition) (*PackageLock, error) {
	path = strings.TrimSpace(path)
	if path == "" {
		return nil, nil
	}
	lock, err := BuildPackageLock(resolved)
	if err != nil {
		return nil, err
	}
	bytes, err := json.MarshalIndent(lock, "", "  ")
	if err != nil {
		return nil, fmt.Errorf("encode lock file: %w", err)
	}
	if err := os.WriteFile(path, append(bytes, '\n'), 0o600); err != nil {
		return nil, fmt.Errorf("write lock file: %w", err)
	}
	return lock, nil
}

func BuildPackageLock(resolved *ResolvedServiceDefinition) (*PackageLock, error) {
	if resolved == nil {
		return nil, fmt.Errorf("resolved package is required to build a lock")
	}
	if strings.TrimSpace(resolved.PackageID) == "" || strings.TrimSpace(resolved.PackageVersion) == "" {
		return nil, fmt.Errorf("lock files can only be written for registry packages or package bundles")
	}
	definitionDigest := strings.TrimSpace(resolved.DefinitionDigest)
	if definitionDigest == "" && len(resolved.Definition) > 0 {
		definitionDigest = canonicalJSONDigest(resolved.Definition)
	}
	lockDigest := strings.TrimSpace(resolved.LockDigest)
	if lockDigest == "" && len(resolved.RecommendedLock) > 0 {
		lockDigest = canonicalJSONDigest(resolved.RecommendedLock)
	}
	lock := &PackageLock{
		LockSchemaVersion:         PackageLockSchemaVersion,
		ArtifactType:              "anip_package_lock",
		SourceKind:                resolved.SourceKind,
		PackageID:                 resolved.PackageID,
		PackageVersion:            resolved.PackageVersion,
		ContractSignature:         resolved.ContractSignature,
		SchemaVersion:             resolved.SchemaVersion,
		DefinitionDigest:          definitionDigest,
		ManifestDigest:            resolved.ManifestDigest,
		LockDigest:                lockDigest,
		PackageExecutionSignature: resolved.PackageExecutionSignature,
		ReceiptSignature:          resolved.ReceiptSignature,
		ReceiptAuthority:          resolved.ReceiptAuthority,
		ReceiptKeyID:              resolved.ReceiptKeyID,
		ReceiptAlgorithm:          resolved.ReceiptAlgorithm,
		ReceiptIssuedAt:           resolved.ReceiptIssuedAt,
		RegistrySigningMode:       resolved.RegistrySigningMode,
		RegistryActiveKeyID:       resolved.RegistryActiveKeyID,
		PublisherID:               resolved.PublisherID,
		PublisherType:             resolved.PublisherType,
	}
	if resolved.SourceKind == "registry" {
		lock.RegistryURL = resolvedRegistryBaseURL(resolved)
	}
	if err := lock.ValidateShape(); err != nil {
		return nil, err
	}
	return lock, nil
}

func ApplyPackageLockToResolveOptions(options *ResolveServiceDefinitionOptions, lock *PackageLock) {
	if options == nil || lock == nil {
		return
	}
	if strings.TrimSpace(options.RegistryBase) == "" {
		options.RegistryBase = strings.TrimSpace(lock.RegistryURL)
	}
	if strings.TrimSpace(options.PackageID) == "" && strings.TrimSpace(options.PackageRef) == "" {
		options.PackageID = strings.TrimSpace(lock.PackageID)
	}
	if strings.TrimSpace(options.PackageVersion) == "" && strings.TrimSpace(options.PackageRef) == "" {
		options.PackageVersion = strings.TrimSpace(lock.PackageVersion)
	}
}

func ValidateResolvedPackageLock(resolved *ResolvedServiceDefinition, lock *PackageLock) error {
	if lock == nil {
		return nil
	}
	if resolved == nil {
		return fmt.Errorf("resolved package is required for lock validation")
	}
	if resolved.SourceKind == "file" {
		return fmt.Errorf("--lock-file requires a registry package or package bundle, not a raw definition file")
	}
	checks := []struct {
		name     string
		expected string
		observed string
	}{
		{name: "package_id", expected: lock.PackageID, observed: resolved.PackageID},
		{name: "package_version", expected: lock.PackageVersion, observed: resolved.PackageVersion},
		{name: "contract_signature", expected: lock.ContractSignature, observed: resolved.ContractSignature},
		{name: "schema_version", expected: lock.SchemaVersion, observed: resolved.SchemaVersion},
		{name: "manifest_digest", expected: lock.ManifestDigest, observed: resolved.ManifestDigest},
		{name: "lock_digest", expected: lock.LockDigest, observed: resolved.LockDigest},
		{name: "package_execution_signature", expected: lock.PackageExecutionSignature, observed: resolved.PackageExecutionSignature},
		{name: "receipt_key_id", expected: lock.ReceiptKeyID, observed: resolved.ReceiptKeyID},
		{name: "receipt_algorithm", expected: lock.ReceiptAlgorithm, observed: resolved.ReceiptAlgorithm},
	}
	for _, check := range checks {
		if err := requireLockMatch(check.name, check.expected, check.observed); err != nil {
			return err
		}
	}
	definitionDigest := strings.TrimSpace(resolved.DefinitionDigest)
	if definitionDigest == "" && len(resolved.Definition) > 0 {
		definitionDigest = canonicalJSONDigest(resolved.Definition)
	}
	if err := requireLockMatch("definition_digest", lock.DefinitionDigest, definitionDigest); err != nil {
		return err
	}
	if lock.RegistrySigningMode != "" && resolved.RegistrySigningMode != "" {
		if err := requireLockMatch("registry_signing_mode", lock.RegistrySigningMode, resolved.RegistrySigningMode); err != nil {
			return err
		}
	}
	if lock.RegistryActiveKeyID != "" && resolved.RegistryActiveKeyID != "" {
		if err := requireLockMatch("registry_active_key_id", lock.RegistryActiveKeyID, resolved.RegistryActiveKeyID); err != nil {
			return err
		}
	}
	return nil
}

func (lock PackageLock) ValidateShape() error {
	if strings.TrimSpace(lock.LockSchemaVersion) != "" && lock.LockSchemaVersion != PackageLockSchemaVersion {
		return fmt.Errorf("unsupported lock_schema_version %q", lock.LockSchemaVersion)
	}
	if strings.TrimSpace(lock.PackageID) == "" || strings.TrimSpace(lock.PackageVersion) == "" {
		return fmt.Errorf("lock file must include package_id and package_version")
	}
	if strings.TrimSpace(lock.DefinitionDigest) == "" || strings.TrimSpace(lock.LockDigest) == "" {
		return fmt.Errorf("lock file must include definition_digest and lock_digest")
	}
	return nil
}

func requireLockMatch(name string, expected string, observed string) error {
	expected = strings.TrimSpace(expected)
	observed = strings.TrimSpace(observed)
	if expected == "" {
		return nil
	}
	if observed == "" {
		return fmt.Errorf("lock mismatch for %s: expected %s but resolved value is empty", name, expected)
	}
	if expected != observed {
		return fmt.Errorf("lock mismatch for %s: expected %s got %s", name, expected, observed)
	}
	return nil
}

func canonicalJSONDigest(payload any) string {
	var buffer bytes.Buffer
	encoder := json.NewEncoder(&buffer)
	encoder.SetEscapeHTML(false)
	if err := encoder.Encode(payload); err != nil {
		return ""
	}
	bytes := bytes.TrimSuffix(buffer.Bytes(), []byte("\n"))
	sum := sha256.Sum256(bytes)
	return "sha256:" + hex.EncodeToString(sum[:])
}

func resolvedRegistryBaseURL(resolved *ResolvedServiceDefinition) string {
	path := strings.TrimSpace(resolved.RegistryRecordPath)
	if path == "" {
		return ""
	}
	index := strings.Index(path, "/packages/")
	if index < 0 {
		return path
	}
	return path[:index]
}
