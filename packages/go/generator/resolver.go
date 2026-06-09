package generator

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
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
	SourceKind          string
	Definition          map[string]any
	DefinitionBytes     []byte
	PackageID           string
	PackageVersion      string
	DefinitionDigest    string
	ManifestDigest      string
	LockDigest          string
	ContractSignature   string
	Lineage             map[string]any
	SchemaVersion       string
	RegistryRecordPath  string
	ReceiptSignature    string
	ReceiptIssuedAt     string
	ReceiptAuthority    string
	ReceiptKeyID        string
	ReceiptAlgorithm    string
	RegistrySigningMode string
	RegistryActiveKeyID string
	RegistryPublicKeys  []registryclient.PublicKey
	PublisherID         string
	PublisherType       string
	Manifest            map[string]any
	RecommendedLock     map[string]any
	AgentReadiness      map[string]any
	AgentConsumability  map[string]any
	RegistryTrustChecks []registryclient.CheckResult
}

type registryPackageRecord struct {
	PackageID               string           `json:"package_id"`
	PackageVersion          string           `json:"package_version"`
	ContractSignature       string           `json:"contract_signature"`
	PublisherID             string           `json:"publisher_id,omitempty"`
	PublisherType           string           `json:"publisher_type,omitempty"`
	Lineage                 map[string]any   `json:"lineage,omitempty"`
	SchemaVersion           string           `json:"schema_version"`
	ManifestDigest          string           `json:"manifest_digest"`
	DefinitionDigest        string           `json:"definition_digest"`
	LockDigest              string           `json:"lock_digest"`
	Manifest                map[string]any   `json:"manifest"`
	ServiceDefinition       map[string]any   `json:"service_definition"`
	RecommendedLock         map[string]any   `json:"recommended_lock"`
	ImplementationMaterials []map[string]any `json:"implementation_materials,omitempty"`
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
	manifest = manifestWithPackageImplementationMaterials(manifest, bundle.Package.ImplementationMaterials)
	lock := bundle.Lock
	if len(lock) == 0 {
		lock = bundle.Package.RecommendedLock
	}
	authority := firstNonEmpty(bundle.Authority, bundle.Receipt.Authority, "local-studio")
	normalized, err := json.MarshalIndent(serviceDefinition, "", "  ")
	if err != nil {
		return nil, fmt.Errorf("encode normalized package bundle definition: %w", err)
	}

	return &ResolvedServiceDefinition{
		SourceKind:         "package-bundle",
		Definition:         serviceDefinition,
		DefinitionBytes:    append(normalized, '\n'),
		PackageID:          bundle.Package.PackageID,
		PackageVersion:     bundle.Package.PackageVersion,
		DefinitionDigest:   firstNonEmpty(bundle.Package.DefinitionDigest, bundle.Digests["service_definition"]),
		ManifestDigest:     firstNonEmpty(bundle.Package.ManifestDigest, bundle.Digests["manifest"]),
		LockDigest:         firstNonEmpty(bundle.Package.LockDigest, bundle.Digests["lock"]),
		ContractSignature:  bundle.Package.ContractSignature,
		Lineage:            firstLineage(bundle.Lineage, bundle.Package.Lineage, manifest, lock),
		SchemaVersion:      bundle.Package.SchemaVersion,
		RegistryRecordPath: path,
		ReceiptSignature:   firstNonEmpty(bundle.Receipt.RegistrySignature, bundle.Digests["receipt"]),
		ReceiptIssuedAt:    bundle.Receipt.IssuedAt,
		ReceiptAuthority:   authority,
		RegistryPublicKeys: bundle.RegistryKeys,
		PublisherID:        bundle.Package.PublisherID,
		PublisherType:      bundle.Package.PublisherType,
		Manifest:           manifest,
		RecommendedLock:    lock,
		AgentReadiness:     firstAgentReadiness(manifest, lock),
		AgentConsumability: firstAgentConsumability(manifest, lock),
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
	manifest := manifestWithPackageImplementationMaterials(record.Manifest, implementationMaterialsToMap(record.ImplementationMaterials))
	normalized, err := json.MarshalIndent(record.ServiceDefinition, "", "  ")
	if err != nil {
		return nil, fmt.Errorf("encode normalized registry definition: %w", err)
	}

	return &ResolvedServiceDefinition{
		SourceKind:          "registry",
		Definition:          record.ServiceDefinition,
		DefinitionBytes:     append(normalized, '\n'),
		PackageID:           record.PackageID,
		PackageVersion:      record.PackageVersion,
		DefinitionDigest:    record.DefinitionDigest,
		ManifestDigest:      record.ManifestDigest,
		LockDigest:          record.LockDigest,
		ContractSignature:   record.ContractSignature,
		Lineage:             firstLineage(record.Lineage, record.Manifest, record.RecommendedLock),
		SchemaVersion:       record.SchemaVersion,
		RegistryRecordPath:  resolvedPackage.PackageURL,
		ReceiptSignature:    resolvedPackage.Receipt.RegistrySignature,
		ReceiptIssuedAt:     resolvedPackage.Receipt.IssuedAt,
		ReceiptAuthority:    "remote-registry",
		ReceiptKeyID:        resolvedPackage.Receipt.KeyID,
		ReceiptAlgorithm:    resolvedPackage.Receipt.SignatureAlgorithm,
		RegistrySigningMode: resolvedPackage.SigningMode,
		RegistryActiveKeyID: resolvedPackage.ActiveKeyID,
		RegistryPublicKeys:  resolvedPackage.PublicKeys,
		PublisherID:         record.PublisherID,
		PublisherType:       record.PublisherType,
		Manifest:            manifest,
		RecommendedLock:     record.RecommendedLock,
		AgentReadiness:      firstAgentReadiness(record.Manifest, record.RecommendedLock),
		AgentConsumability:  firstAgentConsumability(record.Manifest, record.RecommendedLock),
		RegistryTrustChecks: resolvedPackage.Checks,
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
