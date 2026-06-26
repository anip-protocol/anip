package generator

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"sort"
	"strings"

	"github.com/anip-protocol/anip/packages/go/definitionvalidation"
	"github.com/anip-protocol/anip/packages/go/registryclient"
)

type ResolveServiceDefinitionOptions struct {
	DefinitionPath         string
	PackageBundle          string
	RegistryBase           string
	PackageID              string
	PackageVersion         string
	PackageRef             string
	AllowUntrustedRegistry bool
}

type ResolvedServiceDefinition struct {
	SourceKind                string
	Definition                map[string]any
	DefinitionBytes           []byte
	PackageID                 string
	PackageVersion            string
	DefinitionDigest          string
	ManifestDigest            string
	LockDigest                string
	PackageExecutionSignature string
	ContractSignature         string
	Lineage                   map[string]any
	SchemaVersion             string
	RegistryRecordPath        string
	ReceiptSignature          string
	ReceiptIssuedAt           string
	ReceiptAuthority          string
	ReceiptKeyID              string
	ReceiptAlgorithm          string
	RegistrySigningMode       string
	RegistryActiveKeyID       string
	RegistryPublicKeys        []registryclient.PublicKey
	PublisherID               string
	PublisherType             string
	Manifest                  map[string]any
	RecommendedLock           map[string]any
	ImplementationMaterials   []map[string]any
	AgentReadiness            map[string]any
	AgentConsumability        map[string]any
	RegistryTrustChecks       []registryclient.CheckResult
}

type registryPackageRecord struct {
	PackageID                 string           `json:"package_id"`
	PackageVersion            string           `json:"package_version"`
	ContractSignature         string           `json:"contract_signature"`
	PublisherID               string           `json:"publisher_id,omitempty"`
	PublisherType             string           `json:"publisher_type,omitempty"`
	Lineage                   map[string]any   `json:"lineage,omitempty"`
	SchemaVersion             string           `json:"schema_version"`
	ManifestDigest            string           `json:"manifest_digest"`
	DefinitionDigest          string           `json:"definition_digest"`
	LockDigest                string           `json:"lock_digest"`
	PackageExecutionSignature string           `json:"package_execution_signature,omitempty"`
	Manifest                  map[string]any   `json:"manifest"`
	ServiceDefinition         map[string]any   `json:"service_definition"`
	RecommendedLock           map[string]any   `json:"recommended_lock"`
	ImplementationMaterials   []map[string]any `json:"implementation_materials,omitempty"`
}

type PackageBundle struct {
	BundleSchemaVersion string                     `json:"bundle_schema_version"`
	Authority           string                     `json:"authority"`
	Publication         map[string]any             `json:"publication"`
	Package             registryPackageRecord      `json:"package"`
	Receipt             packageBundleReceipt       `json:"receipt"`
	Lineage             map[string]any             `json:"lineage,omitempty"`
	Manifest            map[string]any             `json:"manifest"`
	ServiceDefinition   map[string]any             `json:"service_definition"`
	Lock                map[string]any             `json:"lock"`
	Digests             map[string]string          `json:"digests"`
	RegistryKeys        []registryclient.PublicKey `json:"registry_keys,omitempty"`
}

type packageBundleReceipt struct {
	RegistrySignature string `json:"registry_signature"`
	IssuedAt          string `json:"issued_at"`
	Authority         string `json:"authority"`
}

func ResolveServiceDefinition(ctx context.Context, client *http.Client, options ResolveServiceDefinitionOptions) (*ResolvedServiceDefinition, error) {
	var resolved *ResolvedServiceDefinition
	var err error
	if strings.TrimSpace(options.DefinitionPath) != "" {
		resolved, err = resolveFromFile(options.DefinitionPath)
	} else if strings.TrimSpace(options.PackageBundle) != "" {
		resolved, err = resolveFromPackageBundle(options.PackageBundle)
	} else if strings.TrimSpace(options.RegistryBase) != "" {
		resolved, err = resolveFromRegistry(ctx, client, options)
	} else {
		return nil, fmt.Errorf("definition path, package bundle, or registry package identity must be provided")
	}
	if err != nil {
		return nil, err
	}
	if err := definitionvalidation.ValidateServiceDefinition(resolved.Definition); err != nil {
		return nil, fmt.Errorf("resolved service definition failed validation: %w", err)
	}
	if err := definitionvalidation.ValidateKnownBusinessEffectsInPayload("manifest", resolved.Manifest); err != nil {
		return nil, fmt.Errorf("resolved package manifest failed validation: %w", err)
	}
	if err := definitionvalidation.ValidateKnownBusinessEffectsInPayload("recommended_lock", resolved.RecommendedLock); err != nil {
		return nil, fmt.Errorf("resolved package lock failed validation: %w", err)
	}
	if resolved.SourceKind != "file" {
		if err := validateResolvedPackageExecutionMetadata(resolved); err != nil {
			return nil, err
		}
	}
	return resolved, nil
}

func resolveFromFile(path string) (*ResolvedServiceDefinition, error) {
	bytes, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("read definition file: %w", err)
	}
	var definition map[string]any
	if err := json.Unmarshal(bytes, &definition); err != nil {
		return nil, fmt.Errorf("decode definition file: %w", err)
	}
	normalized, err := json.MarshalIndent(definition, "", "  ")
	if err != nil {
		return nil, fmt.Errorf("encode normalized definition: %w", err)
	}
	return &ResolvedServiceDefinition{
		SourceKind:      "file",
		Definition:      definition,
		DefinitionBytes: append(normalized, '\n'),
		SchemaVersion:   stringValue(definition["contract_schema_version"]),
	}, nil
}

func resolveFromPackageBundle(path string) (*ResolvedServiceDefinition, error) {
	bytes, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("read package bundle: %w", err)
	}
	var bundle PackageBundle
	if err := json.Unmarshal(bytes, &bundle); err != nil {
		return nil, fmt.Errorf("decode package bundle: %w", err)
	}
	serviceDefinition := bundle.ServiceDefinition
	if len(serviceDefinition) == 0 {
		serviceDefinition = bundle.Package.ServiceDefinition
	}
	if len(serviceDefinition) == 0 {
		return nil, fmt.Errorf("package bundle does not contain a service definition")
	}
	manifest := bundle.Manifest
	if len(manifest) == 0 {
		manifest = bundle.Package.Manifest
	}
	implementationMaterials := bundle.Package.ImplementationMaterials
	manifest = manifestWithPackageImplementationMaterials(manifest, implementationMaterials)
	lock := bundle.Lock
	if len(lock) == 0 {
		lock = bundle.Package.RecommendedLock
	}
	authority := firstNonEmpty(bundle.Authority, bundle.Receipt.Authority, "local-studio")
	packageExecutionSignature := firstNonEmpty(
		bundle.Package.PackageExecutionSignature,
		stringValue(manifest["package_execution_signature"]),
		stringValue(lock["package_execution_signature"]),
		bundle.Digests["package_execution"],
	)
	normalized, err := json.MarshalIndent(serviceDefinition, "", "  ")
	if err != nil {
		return nil, fmt.Errorf("encode normalized package bundle definition: %w", err)
	}

	return &ResolvedServiceDefinition{
		SourceKind:                "package-bundle",
		Definition:                serviceDefinition,
		DefinitionBytes:           append(normalized, '\n'),
		PackageID:                 bundle.Package.PackageID,
		PackageVersion:            bundle.Package.PackageVersion,
		DefinitionDigest:          firstNonEmpty(bundle.Package.DefinitionDigest, bundle.Digests["service_definition"]),
		ManifestDigest:            firstNonEmpty(bundle.Package.ManifestDigest, bundle.Digests["manifest"]),
		LockDigest:                firstNonEmpty(bundle.Package.LockDigest, bundle.Digests["lock"]),
		PackageExecutionSignature: packageExecutionSignature,
		ContractSignature:         bundle.Package.ContractSignature,
		Lineage:                   firstLineage(bundle.Lineage, bundle.Package.Lineage, manifest, lock),
		SchemaVersion:             bundle.Package.SchemaVersion,
		RegistryRecordPath:        path,
		ReceiptSignature:          firstNonEmpty(bundle.Receipt.RegistrySignature, bundle.Digests["receipt"]),
		ReceiptIssuedAt:           bundle.Receipt.IssuedAt,
		ReceiptAuthority:          authority,
		RegistryPublicKeys:        bundle.RegistryKeys,
		PublisherID:               bundle.Package.PublisherID,
		PublisherType:             bundle.Package.PublisherType,
		Manifest:                  manifest,
		RecommendedLock:           lock,
		ImplementationMaterials:   implementationMaterials,
		AgentReadiness:            firstAgentReadiness(manifest, lock),
		AgentConsumability:        firstAgentConsumability(manifest, lock),
	}, nil
}

func resolveFromRegistry(ctx context.Context, client *http.Client, options ResolveServiceDefinitionOptions) (*ResolvedServiceDefinition, error) {
	packageID := strings.TrimSpace(options.PackageID)
	packageVersion := strings.TrimSpace(options.PackageVersion)
	if strings.TrimSpace(options.PackageRef) != "" {
		refPackageID, refPackageVersion, err := registryclient.ParsePackageRef(options.PackageRef)
		if err != nil {
			return nil, err
		}
		if packageID == "" {
			packageID = refPackageID
		}
		if packageVersion == "" {
			packageVersion = refPackageVersion
		}
	}
	if packageID == "" || packageVersion == "" {
		return nil, fmt.Errorf("package id and package version are required for registry resolution")
	}

	resolvedPackage, err := registryclient.ResolveAndVerify(ctx, client, options.RegistryBase, packageID, packageVersion)
	if err != nil {
		return nil, err
	}
	if !options.AllowUntrustedRegistry && !resolvedPackage.Trusted() {
		return nil, fmt.Errorf("registry package %s@%s failed trust verification: %s", packageID, packageVersion, resolvedPackage.FailureSummary())
	}
	record := resolvedPackage.Package
	implementationMaterials := implementationMaterialsToMap(record.ImplementationMaterials)
	manifest := manifestWithPackageImplementationMaterials(record.Manifest, implementationMaterials)
	packageExecutionSignature := firstNonEmpty(
		record.PackageExecutionSignature,
		stringValue(manifest["package_execution_signature"]),
		stringValue(record.RecommendedLock["package_execution_signature"]),
	)
	normalized, err := json.MarshalIndent(record.ServiceDefinition, "", "  ")
	if err != nil {
		return nil, fmt.Errorf("encode normalized registry definition: %w", err)
	}

	return &ResolvedServiceDefinition{
		SourceKind:                "registry",
		Definition:                record.ServiceDefinition,
		DefinitionBytes:           append(normalized, '\n'),
		PackageID:                 record.PackageID,
		PackageVersion:            record.PackageVersion,
		DefinitionDigest:          record.DefinitionDigest,
		ManifestDigest:            record.ManifestDigest,
		LockDigest:                record.LockDigest,
		PackageExecutionSignature: packageExecutionSignature,
		ContractSignature:         record.ContractSignature,
		Lineage:                   firstLineage(record.Lineage, record.Manifest, record.RecommendedLock),
		SchemaVersion:             record.SchemaVersion,
		RegistryRecordPath:        resolvedPackage.PackageURL,
		ReceiptSignature:          resolvedPackage.Receipt.RegistrySignature,
		ReceiptIssuedAt:           resolvedPackage.Receipt.IssuedAt,
		ReceiptAuthority:          "remote-registry",
		ReceiptKeyID:              resolvedPackage.Receipt.KeyID,
		ReceiptAlgorithm:          resolvedPackage.Receipt.SignatureAlgorithm,
		RegistrySigningMode:       resolvedPackage.SigningMode,
		RegistryActiveKeyID:       resolvedPackage.ActiveKeyID,
		RegistryPublicKeys:        resolvedPackage.PublicKeys,
		PublisherID:               record.PublisherID,
		PublisherType:             record.PublisherType,
		Manifest:                  manifest,
		RecommendedLock:           record.RecommendedLock,
		ImplementationMaterials:   implementationMaterials,
		AgentReadiness:            firstAgentReadiness(record.Manifest, record.RecommendedLock),
		AgentConsumability:        firstAgentConsumability(record.Manifest, record.RecommendedLock),
		RegistryTrustChecks:       resolvedPackage.Checks,
	}, nil
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if strings.TrimSpace(value) != "" {
			return value
		}
	}
	return ""
}

func stringValue(value any) string {
	text, _ := value.(string)
	return text
}

func firstLineage(candidates ...map[string]any) map[string]any {
	for _, candidate := range candidates {
		if len(candidate) == 0 {
			continue
		}
		if lineage, ok := candidate["lineage"].(map[string]any); ok && len(lineage) > 0 {
			return lineage
		}
		_, hasProject := candidate["project_ref"]
		_, hasProduct := candidate["product_revision"]
		_, hasDeveloper := candidate["developer_revision"]
		if hasProject && hasProduct && hasDeveloper {
			return candidate
		}
	}
	return nil
}

func firstAgentReadiness(candidates ...map[string]any) map[string]any {
	for _, candidate := range candidates {
		if len(candidate) == 0 {
			continue
		}
		if readiness, ok := candidate["agent_consumption_readiness"].(map[string]any); ok && len(readiness) > 0 {
			return readiness
		}
	}
	return nil
}

func firstAgentConsumability(candidates ...map[string]any) map[string]any {
	for _, candidate := range candidates {
		if len(candidate) == 0 {
			continue
		}
		if consumability, ok := candidate["agent_consumability"].(map[string]any); ok && len(consumability) > 0 {
			return consumability
		}
	}
	return nil
}

func validateResolvedPackageExecutionMetadata(resolved *ResolvedServiceDefinition) error {
	if resolved == nil {
		return fmt.Errorf("resolved package is nil")
	}
	if len(resolved.AgentConsumability) == 0 {
		return fmt.Errorf("resolved package is missing agent_consumability metadata")
	}
	if strings.TrimSpace(stringValue(resolved.AgentConsumability["schema_version"])) == "" {
		return fmt.Errorf("resolved package agent_consumability is missing schema_version")
	}
	definitionIDs := definitionCapabilityIDs(resolved.Definition)
	consumabilityIDs := agentConsumabilityCapabilityIDs(resolved.AgentConsumability)
	if len(definitionIDs) == 0 || !stringSetEqual(definitionIDs, consumabilityIDs) {
		return fmt.Errorf("resolved package agent_consumability capabilities do not match service definition: definition=%v consumability=%v", sortedSet(definitionIDs), sortedSet(consumabilityIDs))
	}
	if len(resolved.AgentReadiness) == 0 {
		return fmt.Errorf("resolved package is missing agent_consumption_readiness metadata")
	}
	if strings.TrimSpace(strings.ToLower(stringValue(resolved.AgentReadiness["status"]))) != "ready" {
		return fmt.Errorf("resolved package agent_consumption_readiness is not ready: status=%s", stringValue(resolved.AgentReadiness["status"]))
	}
	summary, _ := resolved.AgentReadiness["summary"].(map[string]any)
	if numericValue(summary["blockers"]) != 0 {
		return fmt.Errorf("resolved package agent_consumption_readiness has blockers: %v", summary["blockers"])
	}
	if numericValue(summary["warnings"]) != 0 {
		return fmt.Errorf("resolved package agent_consumption_readiness has warnings: %v", summary["warnings"])
	}
	if strings.TrimSpace(resolved.PackageExecutionSignature) == "" {
		return fmt.Errorf("resolved package is missing package_execution_signature")
	}
	computed, err := computePackageExecutionSignature(
		resolved.Manifest,
		resolved.Definition,
		resolved.RecommendedLock,
		resolved.ImplementationMaterials,
		resolved.Lineage,
	)
	if err != nil {
		return fmt.Errorf("compute package execution signature: %w", err)
	}
	if resolved.PackageExecutionSignature != computed {
		return fmt.Errorf("resolved package execution signature mismatch: stored=%s computed=%s", resolved.PackageExecutionSignature, computed)
	}
	return nil
}

func computePackageExecutionSignature(
	manifest map[string]any,
	serviceDefinition map[string]any,
	lock map[string]any,
	implementationMaterials []map[string]any,
	lineage map[string]any,
) (string, error) {
	if implementationMaterials == nil {
		implementationMaterials = []map[string]any{}
	}
	if lineage == nil {
		lineage = map[string]any{}
	}
	payload := map[string]any{
		"schema_version":                     "anip-package-execution-signature/v1",
		"service_definition":                 serviceDefinition,
		"agent_consumability":                stripPackageExecutionSignature(manifest)["agent_consumability"],
		"agent_consumption_readiness":        stripPackageExecutionSignature(manifest)["agent_consumption_readiness"],
		"agent_consumption_publication_gate": stripPackageExecutionSignature(manifest)["agent_consumption_publication_gate"],
		"implementation_materials":           implementationMaterials,
		"recommended_lock":                   stripPackageExecutionSignature(lock),
		"lineage":                            lineage,
	}
	return computeCanonicalDigest(payload)
}

// ComputePackageExecutionSignature returns the canonical execution signature for
// package fixtures and external package assembly paths that need to match
// resolver validation exactly.
func ComputePackageExecutionSignature(
	manifest map[string]any,
	serviceDefinition map[string]any,
	lock map[string]any,
	implementationMaterials []map[string]any,
	lineage map[string]any,
) (string, error) {
	return computePackageExecutionSignature(manifest, serviceDefinition, lock, implementationMaterials, lineage)
}

func computeCanonicalDigest(payload any) (string, error) {
	var buffer bytes.Buffer
	encoder := json.NewEncoder(&buffer)
	encoder.SetEscapeHTML(false)
	if err := encoder.Encode(payload); err != nil {
		return "", err
	}
	bytes := bytes.TrimSuffix(buffer.Bytes(), []byte("\n"))
	sum := sha256.Sum256(bytes)
	return "sha256:" + hex.EncodeToString(sum[:]), nil
}

func stripPackageExecutionSignature(value map[string]any) map[string]any {
	stripped, _ := stripPackageExecutionSignatureValue(value).(map[string]any)
	if stripped == nil {
		return map[string]any{}
	}
	return stripped
}

func stripPackageExecutionSignatureValue(value any) any {
	switch typed := value.(type) {
	case map[string]any:
		result := make(map[string]any, len(typed))
		for key, item := range typed {
			if key == "package_execution_signature" {
				continue
			}
			result[key] = stripPackageExecutionSignatureValue(item)
		}
		return result
	case []any:
		result := make([]any, 0, len(typed))
		for _, item := range typed {
			result = append(result, stripPackageExecutionSignatureValue(item))
		}
		return result
	default:
		return value
	}
}

func definitionCapabilityIDs(definition map[string]any) map[string]struct{} {
	result := map[string]struct{}{}
	capabilities, _ := definition["capability_formalizations"].([]any)
	for _, capability := range capabilities {
		item, _ := capability.(map[string]any)
		capabilityID := strings.TrimSpace(stringValue(item["capability_id"]))
		if capabilityID != "" {
			result[capabilityID] = struct{}{}
		}
	}
	return result
}

func agentConsumabilityCapabilityIDs(consumability map[string]any) map[string]struct{} {
	result := map[string]struct{}{}
	capabilities, _ := consumability["capabilities"].(map[string]any)
	for capabilityID := range capabilities {
		trimmed := strings.TrimSpace(capabilityID)
		if trimmed != "" {
			result[trimmed] = struct{}{}
		}
	}
	return result
}

func stringSetEqual(left map[string]struct{}, right map[string]struct{}) bool {
	if len(left) != len(right) {
		return false
	}
	for value := range left {
		if _, ok := right[value]; !ok {
			return false
		}
	}
	return true
}

func sortedSet(values map[string]struct{}) []string {
	result := make([]string, 0, len(values))
	for value := range values {
		result = append(result, value)
	}
	sort.Strings(result)
	return result
}

func numericValue(value any) float64 {
	switch typed := value.(type) {
	case float64:
		return typed
	case float32:
		return float64(typed)
	case int:
		return float64(typed)
	case int64:
		return float64(typed)
	case json.Number:
		number, _ := typed.Float64()
		return number
	default:
		return 0
	}
}

func manifestWithPackageImplementationMaterials(manifest map[string]any, materials []map[string]any) map[string]any {
	if len(materials) == 0 {
		return manifest
	}
	if manifest == nil {
		manifest = map[string]any{}
	}
	if _, ok := manifest["implementation_material"]; ok {
		return manifest
	}
	copied := make(map[string]any, len(manifest)+1)
	for key, value := range manifest {
		copied[key] = value
	}
	items := make([]any, 0, len(materials))
	for _, material := range materials {
		if len(material) > 0 {
			items = append(items, material)
		}
	}
	if len(items) > 0 {
		copied["implementation_material"] = map[string]any{"custom_code_bundles": items}
	}
	return copied
}

func implementationMaterialsToMap(materials []registryclient.ImplementationMaterial) []map[string]any {
	result := make([]map[string]any, 0, len(materials))
	for _, material := range materials {
		item := map[string]any{"ref": material.Ref}
		if material.Title != "" {
			item["title"] = material.Title
		}
		if material.BundleTreeSHA256 != "" {
			item["bundle_tree_sha256"] = material.BundleTreeSHA256
		}
		result = append(result, item)
	}
	return result
}
