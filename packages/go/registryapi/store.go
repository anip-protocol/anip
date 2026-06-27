package registryapi

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"net/url"
	"sort"
	"strings"
	"time"

	"github.com/anip-protocol/anip/packages/go/bundlerefs"
	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/definitionvalidation"
)

var ErrPackageVersionExists = errors.New("package version already exists")
var ErrInvalidPackage = errors.New("invalid package")
var ErrUnauthorizedPublish = errors.New("unauthorized registry publish")
var ErrNamespaceExists = errors.New("registry namespace already exists")

const (
	MaxPublishRequestBytes            = 5 * 1024 * 1024
	MaxPackageManifestBytes           = 1 * 1024 * 1024
	MaxPackageServiceDefinitionBytes  = 2 * 1024 * 1024
	MaxPackageLockBytes               = 512 * 1024
	MaxPackageReadmeBytes             = 64 * 1024
	MaxPackageSourceLinks             = 8
	MaxPackageImplementationMaterials = 8
	MaxPackageJSONDepth               = 48
	MaxPackageCapabilities            = 256
	MaxPackageExampleBytes            = 256 * 1024
	MaxPackageAttachmentBytes         = 512 * 1024
	MaxTemplatePublishRequestBytes    = 2 * 1024 * 1024
	MaxTemplateManifestBytes          = 128 * 1024
	MaxTemplatePayloadBytes           = 1024 * 1024
	MaxTemplateDocuments              = 20
	MaxTemplateDocumentBytes          = 20 * 1024
	MaxTemplateConnections            = 20
	MaxTemplateDiscoveryRecords       = 200
	MaxTemplateCapabilityMappings     = 100
	MaxCreatePublishTokenRequestBytes = 32 * 1024
)

type Store interface {
	ListPublications() []PublicationSummary
	GetPackage(packageID, version string) (RegistryPackageRecord, bool)
	RecordPackageDownload(packageID, version string) (RegistryPackageRecord, bool)
	GetReceipt(packageID, version string) (RegistryReceipt, bool)
	ListPublicKeys() []RegistryPublicKey
	PublishPackage(request PublishPackageRequest) (PublishPackageResult, error)
	ListTemplates() []TemplateSummary
	GetTemplate(templateID, version string) (RegistryTemplateRecord, bool)
	RecordTemplateDownload(templateID, version string) (RegistryTemplateRecord, bool)
	PublishTemplate(request PublishTemplateRequest) (PublishTemplateResult, error)
}

type MemoryStore struct {
	publications []PublicationSummary
	packages     map[string]RegistryPackageRecord
	receipts     map[string]RegistryReceipt
	templates    map[string]RegistryTemplateRecord
	signer       *RegistrySigner
	publicKeys   []RegistryPublicKey
}

func NewMemoryStore() *MemoryStore {
	store := &MemoryStore{
		signer:    NewDevRegistrySigner(),
		packages:  map[string]RegistryPackageRecord{},
		receipts:  map[string]RegistryReceipt{},
		templates: map[string]RegistryTemplateRecord{},
	}
	publication, pkg, receipt := DemoPublicationFixtureWithSigner(store.signer)
	store.publications = []PublicationSummary{publication}
	store.packages = map[string]RegistryPackageRecord{
		storeKey(pkg.PackageID, pkg.PackageVersion): pkg,
	}
	store.receipts = map[string]RegistryReceipt{
		storeKey(receipt.PackageID, receipt.PackageVersion): receipt,
	}
	return store
}

func NewMemoryStoreWithSigner(signer *RegistrySigner) *MemoryStore {
	return NewMemoryStoreWithSignerAndPublicKeys(signer, nil)
}

func NewMemoryStoreWithSignerAndPublicKeys(signer *RegistrySigner, extraPublicKeys []RegistryPublicKey) *MemoryStore {
	if signer == nil {
		signer = NewDevRegistrySigner()
	}
	publication, pkg, receipt := DemoPublicationFixtureWithSigner(signer)
	return &MemoryStore{
		publications: []PublicationSummary{publication},
		packages: map[string]RegistryPackageRecord{
			storeKey(pkg.PackageID, pkg.PackageVersion): pkg,
		},
		receipts: map[string]RegistryReceipt{
			storeKey(receipt.PackageID, receipt.PackageVersion): receipt,
		},
		templates:  map[string]RegistryTemplateRecord{},
		signer:     signer,
		publicKeys: MergeRegistryPublicKeys(signer.PublicKeyRecord(), extraPublicKeys),
	}
}

func DemoPublicationFixture() (PublicationSummary, RegistryPackageRecord, RegistryReceipt) {
	return DemoPublicationFixtureWithSigner(NewDevRegistrySigner())
}

func DemoPublicationFixtureWithSigner(signer *RegistrySigner) (PublicationSummary, RegistryPackageRecord, RegistryReceipt) {
	if signer == nil {
		signer = NewDevRegistrySigner()
	}
	pkg := RegistryPackageRecord{
		PackageID:            "issue-tracker-native-and-mcp-fronting",
		PackageVersion:       "0.1.0",
		ProjectRef:           "issue-tracker-native-and-mcp-fronting",
		ProductRevisionRef:   "product-r12",
		DeveloperRevisionRef: "developer-r7",
		ContractSignature:    "sha256:4a85a5d4b3b8f51f85d90e92b4c8d17b7f4680c7fd4fbc3130655ad0e7f8f1d9",
		PublisherID:          "local-dev",
		PublisherType:        "demo",
		Lineage: map[string]any{
			"project_ref": "issue-tracker-native-and-mcp-fronting",
			"product_revision": map[string]any{
				"ref":             "product-r12",
				"artifact_id":     "product-r12",
				"revision_number": float64(12),
			},
			"developer_revision": map[string]any{
				"ref":                "developer-r7",
				"artifact_id":        "developer-r7",
				"revision_number":    float64(7),
				"contract_signature": "sha256:4a85a5d4b3b8f51f85d90e92b4c8d17b7f4680c7fd4fbc3130655ad0e7f8f1d9",
			},
		},
		SchemaVersion:    "anip-service-definition/v1",
		ManifestDigest:   "sha256:59b9ef00ce2c5b9496b95a1f8cb9e734ad9db8d8e3dc57d1e584dca0d4f1d0f1",
		DefinitionDigest: "sha256:4a85a5d4b3b8f51f85d90e92b4c8d17b7f4680c7fd4fbc3130655ad0e7f8f1d9",
		LockDigest:       "sha256:05258f555953797b5912fba7a5970bd3d426deb475a94e07ef35b63a28ff3ef0",
		PublishedAt:      "2026-04-24T18:20:00Z",
		Manifest: map[string]any{
			"name":              "Issue Tracker Native and MCP Fronting",
			"publisher":         "local-dev",
			"package_id":        "issue-tracker-native-and-mcp-fronting",
			"version":           "0.1.0",
			"schema":            "anip-service-definition/v1",
			"anip_spec_version": core.ProtocolVersion,
			"readme":            "Demo Registry package for the issue-tracker native and MCP fronting fixture.",
			"source_links": []any{
				map[string]any{"title": "Example Project", "url": "https://github.com/anip-protocol/anip"},
			},
			"build_pack":  map[string]any{"name": "anip-build-pack", "version": "0.1.0"},
			"verifier":    map[string]any{"name": "anip-verifier", "version": "0.1.0"},
			"publishedAt": "2026-04-24T18:20:00Z",
		},
		ServiceDefinition: map[string]any{
			"artifact_type":           "anip_service_definition",
			"contract_schema_version": "anip-service-definition/v1",
			"identity": map[string]any{
				"system_name":        "Issue Tracker Native and MCP Fronting",
				"domain_name":        "software_delivery",
				"delivery_model":     "standalone_service",
				"architecture_shape": "single_service",
			},
			"compiled_contract_identity": map[string]any{
				"signature":           "sha256:4a85a5d4b3b8f51f85d90e92b4c8d17b7f4680c7fd4fbc3130655ad0e7f8f1d9",
				"signature_algorithm": "sha256",
			},
			"service_topology_bindings": []any{
				map[string]any{
					"id":                        "svc-issue-tracker",
					"service_id":                "issue-tracker",
					"service_name":              "Issue Tracker",
					"source_role":               "data_access",
					"source_capabilities":       []any{"work_item.search"},
					"formalized_capability_ids": []any{"work_item.search"},
					"owned_concept_ids":         []any{"work_item"},
				},
			},
			"capability_formalizations": []any{
				map[string]any{
					"id":                "cap-work-item-search",
					"kind":              "atomic",
					"source_kind":       "data_access",
					"service_id":        "issue-tracker",
					"capability_id":     "work_item.search",
					"title":             "Search Work Items",
					"summary":           "Search work items with governed query inputs.",
					"intent_type":       "read_only",
					"operation_type":    "query",
					"side_effect_level": "none",
					"backend_operation": "searchWorkItems",
					"path_template":     "/work-items/search",
					"output_shape":      "work_item_search_result",
					"inputs": []any{
						map[string]any{
							"input_name": "query",
							"input_type": "string",
							"required":   true,
							"summary":    "Search query.",
						},
					},
				},
			},
		},
		RecommendedLock: map[string]any{
			"service_definition_digest": "sha256:4a85a5d4b3b8f51f85d90e92b4c8d17b7f4680c7fd4fbc3130655ad0e7f8f1d9",
			"build_pack": map[string]any{
				"name":    "anip-build-pack",
				"version": "0.1.0",
			},
			"verifier_pack": map[string]any{
				"name":    "anip-verifier",
				"version": "0.1.0",
			},
		},
		Readme: "Demo Registry package for the issue-tracker native and MCP fronting fixture.",
		SourceLinks: []PackageSourceLink{
			{Title: "Example Project", URL: "https://github.com/anip-protocol/anip"},
		},
	}

	publication := PublicationSummary{
		PackageID:            pkg.PackageID,
		PackageVersion:       pkg.PackageVersion,
		ProjectRef:           pkg.ProjectRef,
		ProductRevisionRef:   pkg.ProductRevisionRef,
		DeveloperRevisionRef: pkg.DeveloperRevisionRef,
		ContractSignature:    pkg.ContractSignature,
		PublisherID:          pkg.PublisherID,
		PublisherType:        pkg.PublisherType,
		Lineage:              pkg.Lineage,
		PublishedAt:          pkg.PublishedAt,
	}

	receiptPayload := buildReceiptPayload(pkg, pkg.PublishedAt)
	signature, err := signer.SignReceiptPayload(receiptPayload)
	if err != nil {
		panic(err)
	}
	receiptID, err := computeCanonicalDigest(map[string]any{
		"package_id":      pkg.PackageID,
		"package_version": pkg.PackageVersion,
		"issued_at":       pkg.PublishedAt,
	})
	if err != nil {
		panic(err)
	}

	receipt := registryReceiptWithSignatureMetadata(RegistryReceipt{
		ReceiptID:         receiptID,
		PackageID:         pkg.PackageID,
		PackageVersion:    pkg.PackageVersion,
		RegistrySignature: signature,
		PublisherID:       pkg.PublisherID,
		PublisherType:     pkg.PublisherType,
		IssuedAt:          pkg.PublishedAt,
	})

	return publication, pkg, receipt
}

func storeKey(packageID, version string) string {
	return fmt.Sprintf("%s@%s", packageID, version)
}

func normalizePublishRequest(request PublishPackageRequest) PublishPackageRequest {
	request.PublisherID = strings.TrimSpace(request.PublisherID)
	request.PublisherType = strings.TrimSpace(request.PublisherType)
	if request.PublisherType == "" && request.PublisherID != "" {
		request.PublisherType = "unknown"
	}
	if request.SchemaVersion == "" {
		request.SchemaVersion = "anip-service-definition/v1"
	}
	if request.Manifest == nil {
		request.Manifest = map[string]any{}
	}
	if request.ServiceDefinition == nil {
		request.ServiceDefinition = map[string]any{}
	}
	if request.RecommendedLock == nil {
		request.RecommendedLock = map[string]any{}
	}
	request.Readme = strings.TrimSpace(firstNonEmptyString(request.Readme, stringFromAny(request.Manifest["readme"])))
	request.SourceLinks = normalizeSourceLinks(firstNonEmptySourceLinks(request.SourceLinks, sourceLinksFromAny(request.Manifest["source_links"])))
	request.ImplementationMaterials = normalizeImplementationMaterials(firstNonEmptyImplementationMaterials(
		request.ImplementationMaterials,
		implementationMaterialsFromAny(request.Manifest["implementation_materials"]),
		implementationMaterialsFromAny(request.Manifest["implementation_material"]),
	))
	if request.Readme != "" {
		request.Manifest["readme"] = request.Readme
	}
	if len(request.SourceLinks) > 0 {
		request.Manifest["source_links"] = sourceLinksToAny(request.SourceLinks)
	}
	if len(request.ImplementationMaterials) > 0 {
		request.Manifest["implementation_material"] = map[string]any{
			"custom_code_bundles": implementationMaterialsToAny(request.ImplementationMaterials),
		}
	}
	request.Lineage = normalizeLineage(request.Lineage, request.Manifest, request.RecommendedLock)
	if len(request.Lineage) > 0 {
		if _, ok := request.Manifest["lineage"]; !ok {
			request.Manifest["lineage"] = request.Lineage
		}
		if _, ok := request.RecommendedLock["lineage"]; !ok {
			request.RecommendedLock["lineage"] = request.Lineage
		}
	}
	return request
}

func firstNonEmptySourceLinks(primary []PackageSourceLink, fallback []PackageSourceLink) []PackageSourceLink {
	if len(primary) > 0 {
		return primary
	}
	return fallback
}

func firstNonEmptyImplementationMaterials(candidates ...[]PackageImplementationMaterial) []PackageImplementationMaterial {
	for _, candidate := range candidates {
		if len(candidate) > 0 {
			return candidate
		}
	}
	return nil
}

func firstNonEmptyString(primary string, fallback string) string {
	if strings.TrimSpace(primary) != "" {
		return primary
	}
	return fallback
}

func defaultPackageLifecycle() PackageLifecycle {
	return PackageLifecycle{Status: PackageLifecycleActive}
}

func normalizePackageLifecycle(lifecycle PackageLifecycle) PackageLifecycle {
	lifecycle.Status = strings.TrimSpace(lifecycle.Status)
	if lifecycle.Status == "" {
		lifecycle.Status = PackageLifecycleActive
	}
	lifecycle.Reason = strings.TrimSpace(lifecycle.Reason)
	lifecycle.UpdatedAt = strings.TrimSpace(lifecycle.UpdatedAt)
	lifecycle.UpdatedBy = strings.TrimSpace(lifecycle.UpdatedBy)
	if lifecycle.Replacement != nil {
		lifecycle.Replacement.PackageID = strings.TrimSpace(lifecycle.Replacement.PackageID)
		lifecycle.Replacement.PackageVersion = strings.TrimSpace(lifecycle.Replacement.PackageVersion)
		if lifecycle.Replacement.PackageID == "" && lifecycle.Replacement.PackageVersion == "" {
			lifecycle.Replacement = nil
		}
	}
	return lifecycle
}

func validatePackageLifecycleUpdate(packageID string, packageVersion string, request UpdatePackageLifecycleRequest) (PackageLifecycle, error) {
	status := strings.TrimSpace(request.Status)
	if status == "" {
		return PackageLifecycle{}, fmt.Errorf("lifecycle status is required")
	}
	switch status {
	case PackageLifecycleActive, PackageLifecycleSuperseded, PackageLifecycleDeprecated, PackageLifecycleYanked, PackageLifecycleTakedown:
	default:
		return PackageLifecycle{}, fmt.Errorf("unsupported lifecycle status %q", status)
	}

	reason := strings.TrimSpace(request.Reason)
	if status != PackageLifecycleActive && reason == "" {
		return PackageLifecycle{}, fmt.Errorf("lifecycle reason is required for non-active status")
	}

	replacementID := strings.TrimSpace(request.ReplacementPackageID)
	replacementVersion := strings.TrimSpace(request.ReplacementPackageVersion)
	var replacement *PackageLifecycleReplacement
	if replacementID != "" || replacementVersion != "" {
		if replacementID == "" || replacementVersion == "" {
			return PackageLifecycle{}, fmt.Errorf("replacement package id and version must be provided together")
		}
		if replacementID == packageID && replacementVersion == packageVersion {
			return PackageLifecycle{}, fmt.Errorf("replacement package cannot point to itself")
		}
		replacement = &PackageLifecycleReplacement{PackageID: replacementID, PackageVersion: replacementVersion}
	}

	return PackageLifecycle{Status: status, Reason: reason, Replacement: replacement}, nil
}

func normalizeSourceLinks(links []PackageSourceLink) []PackageSourceLink {
	normalized := make([]PackageSourceLink, 0, len(links))
	for _, link := range links {
		title := strings.TrimSpace(link.Title)
		rawURL := strings.TrimSpace(link.URL)
		if title == "" && rawURL == "" {
			continue
		}
		normalized = append(normalized, PackageSourceLink{Title: title, URL: rawURL})
	}
	return normalized
}

func sourceLinksFromAny(value any) []PackageSourceLink {
	items, ok := value.([]any)
	if !ok {
		return nil
	}
	links := make([]PackageSourceLink, 0, len(items))
	for _, item := range items {
		link, ok := item.(map[string]any)
		if !ok {
			continue
		}
		links = append(links, PackageSourceLink{
			Title: stringFromAny(link["title"]),
			URL:   stringFromAny(link["url"]),
		})
	}
	return links
}

func sourceLinksToAny(links []PackageSourceLink) []any {
	items := make([]any, 0, len(links))
	for _, link := range links {
		items = append(items, map[string]any{
			"title": link.Title,
			"url":   link.URL,
		})
	}
	return items
}

func normalizeImplementationMaterials(materials []PackageImplementationMaterial) []PackageImplementationMaterial {
	normalized := make([]PackageImplementationMaterial, 0, len(materials))
	for _, material := range materials {
		title := strings.TrimSpace(material.Title)
		ref := strings.TrimSpace(material.Ref)
		treeDigest := strings.ToLower(strings.TrimSpace(material.BundleTreeSHA256))
		if title == "" && ref == "" && treeDigest == "" {
			continue
		}
		normalized = append(normalized, PackageImplementationMaterial{
			Title:            title,
			Ref:              ref,
			BundleTreeSHA256: treeDigest,
		})
	}
	return normalized
}

func implementationMaterialsFromAny(value any) []PackageImplementationMaterial {
	switch typed := value.(type) {
	case []any:
		materials := make([]PackageImplementationMaterial, 0, len(typed))
		for _, item := range typed {
			if material, ok := implementationMaterialFromMap(item); ok {
				materials = append(materials, material)
			}
		}
		return materials
	case map[string]any:
		if material, ok := implementationMaterialFromMap(typed); ok {
			return []PackageImplementationMaterial{material}
		}
		return implementationMaterialsFromAny(typed["custom_code_bundles"])
	default:
		return nil
	}
}

func implementationMaterialFromMap(value any) (PackageImplementationMaterial, bool) {
	item, ok := value.(map[string]any)
	if !ok {
		return PackageImplementationMaterial{}, false
	}
	ref := firstNonEmptyString(
		stringFromAny(item["ref"]),
		firstNonEmptyString(stringFromAny(item["uri"]), stringFromAny(item["url"])),
	)
	material := PackageImplementationMaterial{
		Title:            stringFromAny(item["title"]),
		Ref:              ref,
		BundleTreeSHA256: firstNonEmptyString(stringFromAny(item["bundle_tree_sha256"]), stringFromAny(item["tree_sha256"])),
	}
	return material, strings.TrimSpace(material.Ref) != "" || strings.TrimSpace(material.BundleTreeSHA256) != "" || strings.TrimSpace(material.Title) != ""
}

func implementationMaterialsToAny(materials []PackageImplementationMaterial) []any {
	items := make([]any, 0, len(materials))
	for _, material := range materials {
		item := map[string]any{
			"ref": material.Ref,
		}
		if material.Title != "" {
			item["title"] = material.Title
		}
		if material.BundleTreeSHA256 != "" {
			item["bundle_tree_sha256"] = material.BundleTreeSHA256
		}
		items = append(items, item)
	}
	return items
}

func stringFromAny(value any) string {
	if text, ok := value.(string); ok {
		return text
	}
	return ""
}

func sliceFromAny(value any) []any {
	items, ok := value.([]any)
	if !ok {
		return nil
	}
	return items
}

func normalizeLineage(candidates ...map[string]any) map[string]any {
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

func invalidPackagef(format string, args ...any) error {
	return fmt.Errorf("%w: %s", ErrInvalidPackage, fmt.Sprintf(format, args...))
}

func containsRetiredTypescriptReference(value any) bool {
	switch typed := value.(type) {
	case string:
		normalized := strings.ToLower(strings.TrimSpace(typed))
		return strings.Contains(normalized, "anip-build-pack-typescript") || strings.Contains(normalized, "typescript")
	case []any:
		for _, item := range typed {
			if containsRetiredTypescriptReference(item) {
				return true
			}
		}
	case map[string]any:
		for _, item := range typed {
			if containsRetiredTypescriptReference(item) {
				return true
			}
		}
	}
	return false
}

type packageResourceStats struct {
	ExampleBytes    int
	AttachmentBytes int
}

func validateJSONSize(label string, value any, maxBytes int) ([]byte, error) {
	bytes, err := json.Marshal(value)
	if err != nil {
		return nil, invalidPackagef("%s must be valid JSON: %v", label, err)
	}
	if len(bytes) > maxBytes {
		return nil, invalidPackagef("%s exceeds %d bytes", label, maxBytes)
	}
	return bytes, nil
}

func validatePackageJSONResourceLimits(label string, value any) error {
	stats := &packageResourceStats{}
	if err := inspectPackageJSON(label, label, value, 0, stats); err != nil {
		return err
	}
	if stats.ExampleBytes > MaxPackageExampleBytes {
		return invalidPackagef("%s examples exceed %d bytes", label, MaxPackageExampleBytes)
	}
	if stats.AttachmentBytes > MaxPackageAttachmentBytes {
		return invalidPackagef("%s attachments exceed %d bytes", label, MaxPackageAttachmentBytes)
	}
	return nil
}

func inspectPackageJSON(label string, path string, value any, depth int, stats *packageResourceStats) error {
	if depth > MaxPackageJSONDepth {
		return invalidPackagef("%s exceeds maximum JSON nesting depth %d", label, MaxPackageJSONDepth)
	}
	switch typed := value.(type) {
	case map[string]any:
		for key, item := range typed {
			if key == "" || len([]byte(key)) > 160 || hasUnsafeControlText(key) {
				return invalidPackagef("%s contains unsafe JSON object key at %s", label, path)
			}
			if err := inspectPackageJSON(label, path+"."+key, item, depth+1, stats); err != nil {
				return err
			}
		}
	case []any:
		for index, item := range typed {
			if err := inspectPackageJSON(label, fmt.Sprintf("%s[%d]", path, index), item, depth+1, stats); err != nil {
				return err
			}
		}
	case string:
		if hasUnsafeControlText(typed) {
			return invalidPackagef("%s contains unsafe control characters at %s", label, path)
		}
		size := len([]byte(typed))
		lowerPath := strings.ToLower(path)
		if strings.Contains(lowerPath, "example") {
			stats.ExampleBytes += size
		}
		if strings.Contains(lowerPath, "attachment") || strings.Contains(lowerPath, "artifact") {
			stats.AttachmentBytes += size
		}
		if looksSuspiciousBinaryPayload(lowerPath, typed) {
			return invalidPackagef("%s contains suspicious binary payload at %s", label, path)
		}
	case []byte:
		return invalidPackagef("%s contains raw binary payload at %s", label, path)
	}
	return nil
}

func hasUnsafeControlText(value string) bool {
	for _, r := range value {
		if r == '\t' || r == '\n' || r == '\r' {
			continue
		}
		if r < 0x20 || r == 0x7f {
			return true
		}
	}
	return false
}

func looksSuspiciousBinaryPayload(path string, value string) bool {
	trimmed := strings.TrimSpace(value)
	lower := strings.ToLower(trimmed)
	if strings.HasPrefix(lower, "data:application/octet-stream") || strings.HasPrefix(lower, "data:binary") {
		return true
	}
	if len(trimmed) < 4096 {
		return false
	}
	if !(strings.Contains(path, "attachment") ||
		strings.Contains(path, "payload") ||
		strings.Contains(path, "blob") ||
		strings.Contains(path, "binary") ||
		strings.Contains(path, "content") ||
		strings.Contains(path, "file")) {
		return false
	}
	base64ish := 0
	for _, r := range trimmed {
		if (r >= 'A' && r <= 'Z') || (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9') || r == '+' || r == '/' || r == '=' || r == '\n' || r == '\r' {
			base64ish++
		}
	}
	return base64ish*100/len(trimmed) > 95
}

func templateSummaryFromRecord(record RegistryTemplateRecord) TemplateSummary {
	return TemplateSummary{
		TemplateID:      record.TemplateID,
		TemplateVersion: record.TemplateVersion,
		TemplateKind:    record.TemplateKind,
		ProjectType:     record.ProjectType,
		ANIPSpecVersion: record.ANIPSpecVersion,
		Domain:          record.Domain,
		Industry:        record.Industry,
		Systems:         append([]string{}, record.Systems...),
		PublisherID:     record.PublisherID,
		PublisherType:   record.PublisherType,
		PublishedAt:     record.PublishedAt,
		DownloadCount:   record.DownloadCount,
		Manifest:        record.Manifest,
	}
}

func normalizeTemplatePublishRequest(request PublishTemplateRequest) PublishTemplateRequest {
	request.TemplateID = strings.TrimSpace(firstNonEmptyString(request.TemplateID, stringFromAny(request.Manifest["template_id"])))
	request.TemplateVersion = strings.TrimSpace(firstNonEmptyString(request.TemplateVersion, stringFromAny(request.Manifest["package_version"])))
	request.PublisherID = strings.TrimSpace(request.PublisherID)
	request.PublisherType = strings.TrimSpace(request.PublisherType)
	if request.PublisherType == "" && request.PublisherID != "" {
		request.PublisherType = "unknown"
	}
	if request.Manifest == nil {
		request.Manifest = map[string]any{}
	}
	if request.Template == nil {
		request.Template = map[string]any{}
	}
	if request.Package == nil {
		request.Package = map[string]any{
			"schema":          "anip-starter-template-package/v0",
			"package_kind":    "anip_starter_template",
			"package_version": request.TemplateVersion,
			"manifest":        request.Manifest,
			"template":        request.Template,
		}
	}
	return request
}

func validateTemplatePublishRequest(request PublishTemplateRequest) error {
	requestBytes, err := json.Marshal(request)
	if err != nil {
		return invalidPackagef("template publish request must be valid JSON: %v", err)
	}
	if len(requestBytes) > MaxTemplatePublishRequestBytes {
		return invalidPackagef("template publish request exceeds %d bytes", MaxTemplatePublishRequestBytes)
	}
	if request.TemplateID == "" || request.TemplateVersion == "" {
		return invalidPackagef("template_id and template_version are required")
	}
	if request.Package != nil && len(request.Package) > 0 {
		if request.Package["schema"] != nil && request.Package["schema"] != "anip-starter-template-package/v0" {
			return invalidPackagef("template package schema must be anip-starter-template-package/v0")
		}
		if request.Package["package_kind"] != nil && request.Package["package_kind"] != "anip_starter_template" {
			return invalidPackagef("template package_kind must be anip_starter_template")
		}
	}
	if request.Manifest["schema"] != "anip-starter-template-manifest/v0" {
		return invalidPackagef("template manifest schema must be anip-starter-template-manifest/v0")
	}
	if request.Template["schema"] != "anip-starter-template/v0" {
		return invalidPackagef("template schema must be anip-starter-template/v0")
	}
	if _, err := validateJSONSize("template manifest", request.Manifest, MaxTemplateManifestBytes); err != nil {
		return err
	}
	if _, err := validateJSONSize("template", request.Template, MaxTemplatePayloadBytes); err != nil {
		return err
	}
	if err := validatePackageJSONResourceLimits("template manifest", request.Manifest); err != nil {
		return err
	}
	if err := validatePackageJSONResourceLimits("template", request.Template); err != nil {
		return err
	}
	if err := definitionvalidation.ValidateKnownBusinessEffectsInPayload("template manifest", request.Manifest); err != nil {
		return invalidPackagef("%s", err.Error())
	}
	if err := definitionvalidation.ValidateKnownBusinessEffectsInPayload("template", request.Template); err != nil {
		return invalidPackagef("%s", err.Error())
	}
	if request.Package != nil && len(request.Package) > 0 {
		if err := definitionvalidation.ValidateKnownBusinessEffectsInPayload("template package", request.Package); err != nil {
			return invalidPackagef("%s", err.Error())
		}
	}
	if request.Package != nil && len(request.Package) > 0 {
		if err := validateNoExecutableTemplateFields("template package", request.Package); err != nil {
			return err
		}
	}
	if err := validateNoExecutableTemplateFields("template manifest", request.Manifest); err != nil {
		return err
	}
	if err := validateNoExecutableTemplateFields("template", request.Template); err != nil {
		return err
	}
	if err := validateStarterTemplatePayload(request.Manifest, request.Template); err != nil {
		return err
	}
	return nil
}

func validateNoExecutableTemplateFields(label string, value any) error {
	return inspectNoExecutableTemplateFields(label, label, value)
}

func inspectNoExecutableTemplateFields(label string, path string, value any) error {
	switch typed := value.(type) {
	case map[string]any:
		for key, item := range typed {
			normalized := strings.ToLower(strings.TrimSpace(key))
			switch normalized {
			case "script", "scripts", "preinstall", "postinstall", "install", "command", "commands":
				return invalidPackagef("%s contains executable-looking field %q at %s", label, key, path)
			}
			if err := inspectNoExecutableTemplateFields(label, path+"."+key, item); err != nil {
				return err
			}
		}
	case []any:
		for index, item := range typed {
			if err := inspectNoExecutableTemplateFields(label, fmt.Sprintf("%s[%d]", path, index), item); err != nil {
				return err
			}
		}
	}
	return nil
}

func validateStarterTemplatePayload(manifest map[string]any, template map[string]any) error {
	if stringFromAny(manifest["template_id"]) != stringFromAny(template["id"]) {
		return invalidPackagef("template manifest template_id must match template.id")
	}
	if stringFromAny(template["anipSpecVersion"]) != core.ProtocolVersion {
		return invalidPackagef("template anipSpecVersion must be %s", core.ProtocolVersion)
	}
	if stringFromAny(manifest["anip_spec_version"]) != stringFromAny(template["anipSpecVersion"]) {
		return invalidPackagef("template manifest anip_spec_version must match template.anipSpecVersion")
	}
	expectedDigest, err := computeCanonicalDigest(template)
	if err != nil {
		return invalidPackagef("template digest could not be computed: %v", err)
	}
	if stringFromAny(manifest["template_digest"]) != expectedDigest {
		return invalidPackagef("template manifest template_digest must match canonical template digest")
	}
	documents := sliceFromAny(template["documents"])
	connections := sliceFromAny(template["connections"])
	discoveryRecords := sliceFromAny(template["discoveryRecords"])
	mappings := sliceFromAny(template["capabilityMappings"])
	if len(documents) > MaxTemplateDocuments {
		return invalidPackagef("template documents exceed %d entries", MaxTemplateDocuments)
	}
	if len(connections) > MaxTemplateConnections {
		return invalidPackagef("template connections exceed %d entries", MaxTemplateConnections)
	}
	if len(discoveryRecords) > MaxTemplateDiscoveryRecords {
		return invalidPackagef("template discoveryRecords exceed %d entries", MaxTemplateDiscoveryRecords)
	}
	if len(mappings) > MaxTemplateCapabilityMappings {
		return invalidPackagef("template capabilityMappings exceed %d entries", MaxTemplateCapabilityMappings)
	}
	for index, item := range documents {
		document, ok := item.(map[string]any)
		if !ok {
			return invalidPackagef("template documents[%d] must be an object", index)
		}
		filename := stringFromAny(document["filename"])
		if filename == "" || strings.Contains(filename, "..") || strings.Contains(filename, "/") || strings.Contains(filename, "\\") || !strings.HasSuffix(strings.ToLower(filename), ".md") {
			return invalidPackagef("template documents[%d].filename must be a safe Markdown .md filename", index)
		}
		content := stringFromAny(document["content"])
		if len([]byte(content)) > MaxTemplateDocumentBytes {
			return invalidPackagef("template documents[%d].content exceeds %d bytes", index, MaxTemplateDocumentBytes)
		}
	}
	for index, item := range connections {
		connection, ok := item.(map[string]any)
		if !ok {
			return invalidPackagef("template connections[%d] must be an object", index)
		}
		secretRef := stringFromAny(connection["secret_ref"])
		if secretRef != "" && !isEnvStyleRef(secretRef) {
			return invalidPackagef("template connections[%d].secret_ref must be an environment-style reference", index)
		}
	}
	return nil
}

func isEnvStyleRef(value string) bool {
	if len(value) < 2 || len(value) > 128 {
		return false
	}
	for index, r := range value {
		if index == 0 {
			if r < 'A' || r > 'Z' {
				return false
			}
			continue
		}
		if (r >= 'A' && r <= 'Z') || (r >= '0' && r <= '9') || r == '_' {
			continue
		}
		return false
	}
	return true
}

func buildPublishedTemplate(request PublishTemplateRequest, publishedAt time.Time) (RegistryTemplateRecord, error) {
	request = normalizeTemplatePublishRequest(request)
	if err := validateTemplatePublishRequest(request); err != nil {
		return RegistryTemplateRecord{}, err
	}
	manifestDigest, err := computeCanonicalDigest(request.Manifest)
	if err != nil {
		return RegistryTemplateRecord{}, err
	}
	templateDigest, err := computeCanonicalDigest(request.Template)
	if err != nil {
		return RegistryTemplateRecord{}, err
	}
	packageDigest, err := computeCanonicalDigest(request.Package)
	if err != nil {
		return RegistryTemplateRecord{}, err
	}
	record := RegistryTemplateRecord{
		TemplateID:      request.TemplateID,
		TemplateVersion: request.TemplateVersion,
		TemplateKind:    stringFromAny(request.Template["kind"]),
		ProjectType:     stringFromAny(request.Template["projectType"]),
		ANIPSpecVersion: stringFromAny(request.Template["anipSpecVersion"]),
		Domain:          stringFromAny(request.Template["domain"]),
		Industry:        stringFromAny(request.Manifest["industry"]),
		Systems:         stringsFromAny(request.Manifest["systems"]),
		PublisherID:     request.PublisherID,
		PublisherType:   request.PublisherType,
		PublishedAt:     publishedAt.UTC().Format(time.RFC3339),
		ManifestDigest:  manifestDigest,
		TemplateDigest:  templateDigest,
		PackageDigest:   packageDigest,
		Manifest:        request.Manifest,
		Template:        request.Template,
		Package:         request.Package,
	}
	if record.Industry == "" {
		record.Industry = stringFromAny(request.Template["industry"])
	}
	return record, nil
}

func stringsFromAny(value any) []string {
	items := sliceFromAny(value)
	output := make([]string, 0, len(items))
	for _, item := range items {
		if text, ok := item.(string); ok && strings.TrimSpace(text) != "" {
			output = append(output, strings.TrimSpace(text))
		}
	}
	return output
}

func validatePublishPackageRequest(request PublishPackageRequest) error {
	requestBytes, err := json.Marshal(request)
	if err != nil {
		return invalidPackagef("publish request must be valid JSON: %v", err)
	}
	if len(requestBytes) > MaxPublishRequestBytes {
		return invalidPackagef("publish request exceeds %d bytes", MaxPublishRequestBytes)
	}
	if len([]byte(request.Readme)) > MaxPackageReadmeBytes {
		return invalidPackagef("readme exceeds %d bytes", MaxPackageReadmeBytes)
	}
	if len(request.SourceLinks) > MaxPackageSourceLinks {
		return invalidPackagef("source_links exceeds %d entries", MaxPackageSourceLinks)
	}
	for index, link := range request.SourceLinks {
		if link.Title == "" || link.URL == "" {
			return invalidPackagef("source_links[%d] requires title and url", index)
		}
		if len([]byte(link.Title)) > 120 {
			return invalidPackagef("source_links[%d].title exceeds 120 bytes", index)
		}
		if len([]byte(link.URL)) > 2048 {
			return invalidPackagef("source_links[%d].url exceeds 2048 bytes", index)
		}
		parsed, err := url.ParseRequestURI(link.URL)
		if err != nil || (parsed.Scheme != "http" && parsed.Scheme != "https") || parsed.Host == "" {
			return invalidPackagef("source_links[%d].url must be an http(s) URL", index)
		}
	}
	if len(request.ImplementationMaterials) > MaxPackageImplementationMaterials {
		return invalidPackagef("implementation_materials exceeds %d entries", MaxPackageImplementationMaterials)
	}
	for index, material := range request.ImplementationMaterials {
		if material.Ref == "" {
			return invalidPackagef("implementation_materials[%d].ref is required", index)
		}
		if len([]byte(material.Title)) > 120 {
			return invalidPackagef("implementation_materials[%d].title exceeds 120 bytes", index)
		}
		if len([]byte(material.Ref)) > 2048 {
			return invalidPackagef("implementation_materials[%d].ref exceeds 2048 bytes", index)
		}
		if _, err := bundlerefs.ValidateCustomCodeBundleRef(material.Ref); err != nil {
			return invalidPackagef("implementation_materials[%d].ref is invalid: %v", index, err)
		}
		if material.BundleTreeSHA256 != "" && !bundlerefs.IsSHA256Digest(material.BundleTreeSHA256) {
			return invalidPackagef("implementation_materials[%d].bundle_tree_sha256 must be sha256:<64 hex chars>", index)
		}
	}
	if request.SchemaVersion != "anip-service-definition/v1" {
		return invalidPackagef("schema_version must be anip-service-definition/v1")
	}
	if stringFromAny(request.Manifest["anip_spec_version"]) != core.ProtocolVersion {
		return invalidPackagef("manifest anip_spec_version must be %s", core.ProtocolVersion)
	}
	if containsRetiredTypescriptReference(request.Manifest) || containsRetiredTypescriptReference(request.RecommendedLock) {
		return invalidPackagef("retired TypeScript build-pack references are not publishable")
	}
	if _, err := validateJSONSize("manifest", request.Manifest, MaxPackageManifestBytes); err != nil {
		return err
	}
	definitionBytes, err := validateJSONSize("service_definition", request.ServiceDefinition, MaxPackageServiceDefinitionBytes)
	if err != nil {
		return err
	}
	if _, err := validateJSONSize("recommended_lock", request.RecommendedLock, MaxPackageLockBytes); err != nil {
		return err
	}
	if err := validatePackageJSONResourceLimits("manifest", request.Manifest); err != nil {
		return err
	}
	if err := validatePackageJSONResourceLimits("service_definition", request.ServiceDefinition); err != nil {
		return err
	}
	if err := validatePackageJSONResourceLimits("recommended_lock", request.RecommendedLock); err != nil {
		return err
	}
	if err := definitionvalidation.ValidateKnownBusinessEffectsInPayload("manifest", request.Manifest); err != nil {
		return invalidPackagef("%s", err.Error())
	}
	if err := definitionvalidation.ValidateKnownBusinessEffectsInPayload("recommended_lock", request.RecommendedLock); err != nil {
		return invalidPackagef("%s", err.Error())
	}
	if _, err := bundlerefs.CustomCodeBundleMaterialsFromMetadata(request.Manifest, request.RecommendedLock); err != nil {
		return invalidPackagef("%s", err.Error())
	}
	if capabilities := sliceFromAny(request.ServiceDefinition["capability_formalizations"]); len(capabilities) > MaxPackageCapabilities {
		return invalidPackagef("service_definition capability count exceeds %d", MaxPackageCapabilities)
	}
	var definition map[string]any
	if err := json.Unmarshal(definitionBytes, &definition); err != nil {
		return invalidPackagef("%s", err.Error())
	}
	if err := definitionvalidation.ValidateServiceDefinition(definition); err != nil {
		return invalidPackagef("%s", err.Error())
	}
	return nil
}

func stampServerDefinitionDigest(request *PublishPackageRequest, definitionDigest string) {
	if request.Manifest == nil {
		request.Manifest = map[string]any{}
	}
	if request.RecommendedLock == nil {
		request.RecommendedLock = map[string]any{}
	}
	request.Manifest["service_definition_digest"] = definitionDigest
	request.Manifest["service_definition_digest_algorithm"] = "sha256"
	request.Manifest["schema_version"] = request.SchemaVersion
	request.RecommendedLock["service_definition_digest"] = definitionDigest
	request.RecommendedLock["schema_version"] = request.SchemaVersion
	request.RecommendedLock["anip_spec_version"] = core.ProtocolVersion
}

func computePackageExecutionSignature(request PublishPackageRequest) (string, error) {
	lineage := request.Lineage
	if len(lineage) == 0 {
		lineage = map[string]any{}
	}
	payload := map[string]any{
		"schema_version":                     "anip-package-execution-signature/v1",
		"service_definition":                 request.ServiceDefinition,
		"agent_consumability":                stripPackageExecutionSignatureMap(request.Manifest)["agent_consumability"],
		"agent_consumption_readiness":        stripPackageExecutionSignatureMap(request.Manifest)["agent_consumption_readiness"],
		"agent_consumption_publication_gate": stripPackageExecutionSignatureMap(request.Manifest)["agent_consumption_publication_gate"],
		"implementation_materials":           implementationMaterialsToAny(request.ImplementationMaterials),
		"recommended_lock":                   stripPackageExecutionSignatureMap(request.RecommendedLock),
		"lineage":                            lineage,
	}
	return computeCanonicalDigest(payload)
}

func stripPackageExecutionSignatureMap(value map[string]any) map[string]any {
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

func validatePackageExecutionMetadata(request PublishPackageRequest) error {
	agentConsumability := mapFromAny(request.Manifest["agent_consumability"])
	if len(agentConsumability) == 0 {
		agentConsumability = mapFromAny(request.RecommendedLock["agent_consumability"])
	}
	if len(agentConsumability) == 0 {
		return invalidPackagef("agent_consumability metadata is required")
	}
	if strings.TrimSpace(stringFromAny(agentConsumability["schema_version"])) == "" {
		return invalidPackagef("agent_consumability.schema_version is required")
	}
	definitionIDs := capabilityIDSet(request.ServiceDefinition)
	consumabilityIDs := consumabilityCapabilityIDSet(agentConsumability)
	if len(definitionIDs) == 0 || !stringSetEqual(definitionIDs, consumabilityIDs) {
		return invalidPackagef("agent_consumability capabilities must match service_definition capabilities: definition=%v consumability=%v", sortedStringSet(definitionIDs), sortedStringSet(consumabilityIDs))
	}
	readiness := mapFromAny(request.Manifest["agent_consumption_readiness"])
	if len(readiness) == 0 {
		readiness = mapFromAny(request.RecommendedLock["agent_consumption_readiness"])
	}
	if strings.ToLower(strings.TrimSpace(stringFromAny(readiness["status"]))) != "ready" {
		return invalidPackagef("agent_consumption_readiness.status must be ready")
	}
	summary := mapFromAny(readiness["summary"])
	if numericFromAny(summary["blockers"]) != 0 {
		return invalidPackagef("agent_consumption_readiness.summary.blockers must be 0")
	}
	if numericFromAny(summary["warnings"]) != 0 {
		return invalidPackagef("agent_consumption_readiness.summary.warnings must be 0")
	}
	return nil
}

func mapFromAny(value any) map[string]any {
	if typed, ok := value.(map[string]any); ok {
		return typed
	}
	return nil
}

func capabilityIDSet(definition map[string]any) map[string]struct{} {
	result := map[string]struct{}{}
	for _, item := range sliceFromAny(definition["capability_formalizations"]) {
		capability := mapFromAny(item)
		capabilityID := strings.TrimSpace(stringFromAny(capability["capability_id"]))
		if capabilityID != "" {
			result[capabilityID] = struct{}{}
		}
	}
	return result
}

func consumabilityCapabilityIDSet(agentConsumability map[string]any) map[string]struct{} {
	result := map[string]struct{}{}
	for capabilityID := range mapFromAny(agentConsumability["capabilities"]) {
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

func sortedStringSet(values map[string]struct{}) []string {
	result := make([]string, 0, len(values))
	for value := range values {
		result = append(result, value)
	}
	sort.Strings(result)
	return result
}

func numericFromAny(value any) float64 {
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

func buildReceiptPayload(pkg RegistryPackageRecord, issuedAt string) map[string]any {
	payload := map[string]any{
		"package_id":                  pkg.PackageID,
		"package_version":             pkg.PackageVersion,
		"contract_signature":          pkg.ContractSignature,
		"definition_digest":           pkg.DefinitionDigest,
		"manifest_digest":             pkg.ManifestDigest,
		"lock_digest":                 pkg.LockDigest,
		"package_execution_signature": pkg.PackageExecutionSignature,
		"issued_at":                   issuedAt,
	}
	if pkg.PublisherID != "" {
		payload["publisher_id"] = pkg.PublisherID
	}
	if pkg.PublisherType != "" {
		payload["publisher_type"] = pkg.PublisherType
	}
	if len(pkg.Lineage) > 0 {
		payload["lineage"] = pkg.Lineage
	}
	return payload
}

func registryReceiptWithSignatureMetadata(receipt RegistryReceipt) RegistryReceipt {
	algorithm, keyID, _, ok := ParseRegistrySignature(receipt.RegistrySignature)
	if ok {
		receipt.SignatureAlgorithm = algorithm
		receipt.KeyID = keyID
	}
	return receipt
}

func buildPublishedArtifacts(request PublishPackageRequest, publishedAt time.Time, signer *RegistrySigner) (PublicationSummary, RegistryPackageRecord, RegistryReceipt, error) {
	request = normalizePublishRequest(request)
	if err := validatePublishPackageRequest(request); err != nil {
		return PublicationSummary{}, RegistryPackageRecord{}, RegistryReceipt{}, err
	}
	if signer == nil {
		signer = NewDevRegistrySigner()
	}

	var err error
	request.ServiceDefinition, err = normalizeJSONMap(request.ServiceDefinition)
	if err != nil {
		return PublicationSummary{}, RegistryPackageRecord{}, RegistryReceipt{}, err
	}
	definitionDigest, err := computeCanonicalDigest(request.ServiceDefinition)
	if err != nil {
		return PublicationSummary{}, RegistryPackageRecord{}, RegistryReceipt{}, err
	}
	stampServerDefinitionDigest(&request, definitionDigest)
	request.Manifest, err = normalizeJSONMap(request.Manifest)
	if err != nil {
		return PublicationSummary{}, RegistryPackageRecord{}, RegistryReceipt{}, err
	}
	request.RecommendedLock, err = normalizeJSONMap(request.RecommendedLock)
	if err != nil {
		return PublicationSummary{}, RegistryPackageRecord{}, RegistryReceipt{}, err
	}
	if err := validatePackageExecutionMetadata(request); err != nil {
		return PublicationSummary{}, RegistryPackageRecord{}, RegistryReceipt{}, err
	}
	packageExecutionSignature, err := computePackageExecutionSignature(request)
	if err != nil {
		return PublicationSummary{}, RegistryPackageRecord{}, RegistryReceipt{}, err
	}
	request.Manifest["package_execution_signature"] = packageExecutionSignature
	request.RecommendedLock["package_execution_signature"] = packageExecutionSignature
	request.Manifest, err = normalizeJSONMap(request.Manifest)
	if err != nil {
		return PublicationSummary{}, RegistryPackageRecord{}, RegistryReceipt{}, err
	}
	request.RecommendedLock, err = normalizeJSONMap(request.RecommendedLock)
	if err != nil {
		return PublicationSummary{}, RegistryPackageRecord{}, RegistryReceipt{}, err
	}
	manifestDigest, err := computeCanonicalDigest(request.Manifest)
	if err != nil {
		return PublicationSummary{}, RegistryPackageRecord{}, RegistryReceipt{}, err
	}
	lockDigest, err := computeCanonicalDigest(request.RecommendedLock)
	if err != nil {
		return PublicationSummary{}, RegistryPackageRecord{}, RegistryReceipt{}, err
	}

	publication := PublicationSummary{
		PackageID:            request.PackageID,
		PackageVersion:       request.PackageVersion,
		ProjectRef:           request.ProjectRef,
		ProductRevisionRef:   request.ProductRevisionRef,
		DeveloperRevisionRef: request.DeveloperRevisionRef,
		ContractSignature:    request.ContractSignature,
		PublisherID:          request.PublisherID,
		PublisherType:        request.PublisherType,
		Lineage:              request.Lineage,
		PublishedAt:          publishedAt.UTC().Format(time.RFC3339),
		Lifecycle:            defaultPackageLifecycle(),
	}

	pkg := RegistryPackageRecord{
		PackageID:                 request.PackageID,
		PackageVersion:            request.PackageVersion,
		ProjectRef:                request.ProjectRef,
		ProductRevisionRef:        request.ProductRevisionRef,
		DeveloperRevisionRef:      request.DeveloperRevisionRef,
		ContractSignature:         request.ContractSignature,
		PublisherID:               request.PublisherID,
		PublisherType:             request.PublisherType,
		Lineage:                   request.Lineage,
		SchemaVersion:             request.SchemaVersion,
		ManifestDigest:            manifestDigest,
		DefinitionDigest:          definitionDigest,
		LockDigest:                lockDigest,
		PackageExecutionSignature: packageExecutionSignature,
		PublishedAt:               publishedAt.UTC().Format(time.RFC3339),
		Manifest:                  request.Manifest,
		Lifecycle:                 defaultPackageLifecycle(),
		ServiceDefinition:         request.ServiceDefinition,
		RecommendedLock:           request.RecommendedLock,
		Readme:                    request.Readme,
		SourceLinks:               request.SourceLinks,
		ImplementationMaterials:   request.ImplementationMaterials,
	}

	issuedAt := publishedAt.UTC().Format(time.RFC3339)
	receiptSignature, err := signer.SignReceiptPayload(buildReceiptPayload(pkg, issuedAt))
	if err != nil {
		return PublicationSummary{}, RegistryPackageRecord{}, RegistryReceipt{}, err
	}
	receiptID, err := computeCanonicalDigest(map[string]any{
		"package_id":      pkg.PackageID,
		"package_version": pkg.PackageVersion,
		"issued_at":       issuedAt,
	})
	if err != nil {
		return PublicationSummary{}, RegistryPackageRecord{}, RegistryReceipt{}, err
	}

	receipt := registryReceiptWithSignatureMetadata(RegistryReceipt{
		ReceiptID:         receiptID,
		PackageID:         pkg.PackageID,
		PackageVersion:    pkg.PackageVersion,
		RegistrySignature: receiptSignature,
		PublisherID:       pkg.PublisherID,
		PublisherType:     pkg.PublisherType,
		IssuedAt:          issuedAt,
	})

	return publication, pkg, receipt, nil
}

func (s *MemoryStore) ListPublications() []PublicationSummary {
	items := make([]PublicationSummary, 0, len(s.publications))
	for _, item := range s.publications {
		if pkg, ok := s.packages[storeKey(item.PackageID, item.PackageVersion)]; ok {
			item.DownloadCount = pkg.DownloadCount
			item.Lifecycle = normalizePackageLifecycle(pkg.Lifecycle)
		} else {
			item.Lifecycle = normalizePackageLifecycle(item.Lifecycle)
		}
		items = append(items, item)
	}
	sort.SliceStable(items, func(i, j int) bool {
		if items[i].DownloadCount != items[j].DownloadCount {
			return items[i].DownloadCount > items[j].DownloadCount
		}
		if items[i].PublishedAt != items[j].PublishedAt {
			return items[i].PublishedAt > items[j].PublishedAt
		}
		if items[i].PackageID != items[j].PackageID {
			return items[i].PackageID < items[j].PackageID
		}
		return items[i].PackageVersion > items[j].PackageVersion
	})
	return items
}

func (s *MemoryStore) GetPackage(packageID, version string) (RegistryPackageRecord, bool) {
	record, ok := s.packages[storeKey(packageID, version)]
	record.Lifecycle = normalizePackageLifecycle(record.Lifecycle)
	return record, ok
}

func (s *MemoryStore) RecordPackageDownload(packageID, version string) (RegistryPackageRecord, bool) {
	key := storeKey(packageID, version)
	record, ok := s.packages[key]
	if !ok {
		return RegistryPackageRecord{}, false
	}
	record.DownloadCount++
	record.Lifecycle = normalizePackageLifecycle(record.Lifecycle)
	s.packages[key] = record
	return record, true
}

func (s *MemoryStore) GetReceipt(packageID, version string) (RegistryReceipt, bool) {
	record, ok := s.receipts[storeKey(packageID, version)]
	return record, ok
}

func (s *MemoryStore) ListPublicKeys() []RegistryPublicKey {
	if len(s.publicKeys) == 0 {
		return []RegistryPublicKey{s.signer.PublicKeyRecord()}
	}
	keys := make([]RegistryPublicKey, 0, len(s.publicKeys))
	keys = append(keys, s.publicKeys...)
	return keys
}

func (s *MemoryStore) CheckReady(ctx context.Context) error {
	return nil
}

func (s *MemoryStore) MigrationStatus(ctx context.Context) (MigrationStatus, error) {
	return MigrationStatus{Applied: true}, nil
}

func (s *MemoryStore) PublishPackage(request PublishPackageRequest) (PublishPackageResult, error) {
	return s.PublishPackageAt(request, time.Now().UTC())
}

func (s *MemoryStore) PublishPackageAt(request PublishPackageRequest, publishedAt time.Time) (PublishPackageResult, error) {
	if _, exists := s.packages[storeKey(request.PackageID, request.PackageVersion)]; exists {
		return PublishPackageResult{}, ErrPackageVersionExists
	}

	publication, pkg, receipt, err := buildPublishedArtifacts(request, publishedAt.UTC(), s.signer)
	if err != nil {
		return PublishPackageResult{}, err
	}

	s.publications = append([]PublicationSummary{publication}, s.publications...)
	s.packages[storeKey(pkg.PackageID, pkg.PackageVersion)] = pkg
	s.receipts[storeKey(receipt.PackageID, receipt.PackageVersion)] = receipt

	return PublishPackageResult{
		Publication: publication,
		Package:     pkg,
		Receipt:     receipt,
	}, nil
}

func normalizeJSONMap(value map[string]any) (map[string]any, error) {
	bytes, err := json.Marshal(value)
	if err != nil {
		return nil, err
	}
	var normalized map[string]any
	if err := json.Unmarshal(bytes, &normalized); err != nil {
		return nil, err
	}
	if normalized == nil {
		normalized = map[string]any{}
	}
	return normalized, nil
}

func (s *MemoryStore) ListTemplates() []TemplateSummary {
	items := make([]TemplateSummary, 0, len(s.templates))
	for _, record := range s.templates {
		items = append(items, templateSummaryFromRecord(record))
	}
	sort.SliceStable(items, func(i, j int) bool {
		if items[i].DownloadCount != items[j].DownloadCount {
			return items[i].DownloadCount > items[j].DownloadCount
		}
		if items[i].PublishedAt != items[j].PublishedAt {
			return items[i].PublishedAt > items[j].PublishedAt
		}
		if items[i].TemplateID != items[j].TemplateID {
			return items[i].TemplateID < items[j].TemplateID
		}
		return items[i].TemplateVersion > items[j].TemplateVersion
	})
	return items
}

func (s *MemoryStore) GetTemplate(templateID, version string) (RegistryTemplateRecord, bool) {
	record, ok := s.templates[storeKey(templateID, version)]
	return record, ok
}

func (s *MemoryStore) RecordTemplateDownload(templateID, version string) (RegistryTemplateRecord, bool) {
	key := storeKey(templateID, version)
	record, ok := s.templates[key]
	if !ok {
		return RegistryTemplateRecord{}, false
	}
	record.DownloadCount++
	s.templates[key] = record
	return record, true
}

func (s *MemoryStore) PublishTemplate(request PublishTemplateRequest) (PublishTemplateResult, error) {
	request = normalizeTemplatePublishRequest(request)
	if _, exists := s.templates[storeKey(request.TemplateID, request.TemplateVersion)]; exists {
		return PublishTemplateResult{}, ErrPackageVersionExists
	}
	record, err := buildPublishedTemplate(request, time.Now().UTC())
	if err != nil {
		return PublishTemplateResult{}, err
	}
	s.templates[storeKey(record.TemplateID, record.TemplateVersion)] = record
	return PublishTemplateResult{Template: record}, nil
}
