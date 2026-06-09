package packagecmd

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/anip-protocol/anip/packages/go/bundlerefs"
	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/definitionvalidation"
	"github.com/anip-protocol/anip/packages/go/generator"
	"github.com/anip-protocol/anip/packages/go/registryapi"
)

type cliError struct {
	message string
	code    int
}

func Run(args []string, stdout io.Writer, stderr io.Writer) (exitCode int) {
	if stdout == nil {
		stdout = os.Stdout
	}
	if stderr == nil {
		stderr = os.Stderr
	}
	defer func() {
		if recovered := recover(); recovered != nil {
			if err, ok := recovered.(cliError); ok {
				fmt.Fprintln(stderr, err.message)
				exitCode = err.code
				return
			}
			panic(recovered)
		}
	}()

	if len(args) == 0 {
		printUsage(stderr)
		return 2
	}
	switch args[0] {
	case "build-local":
		return runBuildLocal(args[1:], stdout, stderr)
	case "publish-bundle":
		return runPublishBundle(args[1:], stdout, stderr)
	case "attach-implementation":
		return runAttachImplementation(args[1:], stdout, stderr)
	case "audit-effects":
		return runAuditEffects(args[1:], stdout, stderr)
	case "help", "-h", "--help":
		printUsage(stdout)
		return 0
	default:
		fmt.Fprintf(stderr, "unknown package command %q\n", args[0])
		printUsage(stderr)
		return 2
	}
}

func printUsage(writer io.Writer) {
	fmt.Fprintln(writer, `Usage:
  anip package build-local [flags]
  anip package publish-bundle [flags]
  anip package attach-implementation [flags]
  anip package audit-effects [flags]

Commands:
  build-local            Build a signed local package bundle from a service definition.
  publish-bundle         Publish an existing package bundle to a Registry.
  attach-implementation  Add immutable implementation material metadata and produce or publish a new package revision.
  audit-effects          Scan JSON package/template/project artifacts for non-canonical effect IDs.`)
}

type repeatedStrings []string

func (values *repeatedStrings) String() string {
	return strings.Join(*values, ",")
}

func (values *repeatedStrings) Set(value string) error {
	trimmed := strings.TrimSpace(value)
	if trimmed != "" {
		*values = append(*values, trimmed)
	}
	return nil
}

type effectAuditFinding struct {
	File     string `json:"file"`
	Path     string `json:"path"`
	EffectID string `json:"effect_id"`
}

func runAuditEffects(args []string, stdout io.Writer, stderr io.Writer) int {
	var paths repeatedStrings
	fs := flag.NewFlagSet("anip package audit-effects", flag.ContinueOnError)
	if hasHelpFlag(args) {
		fs.SetOutput(stdout)
	} else {
		fs.SetOutput(stderr)
	}
	fs.Usage = func() {
		writer := fs.Output()
		fmt.Fprintln(writer, `Usage:
  anip package audit-effects --path <file-or-directory> [--path <file-or-directory> ...]

Scans JSON Studio, Registry package, template, and generated service-definition
artifacts for effect fields that are not in the current ANIP effect vocabulary.
The command exits non-zero when any non-canonical effect ID is found.

Flags:`)
		fs.PrintDefaults()
	}
	fs.Var(&paths, "path", "JSON file or directory to scan. Repeat for multiple roots.")
	if err := fs.Parse(args); err != nil {
		if err == flag.ErrHelp {
			return 0
		}
		return 2
	}
	if len(paths) == 0 {
		fail("--path is required", 2)
	}

	files := []string{}
	for _, rawPath := range paths {
		info, err := os.Stat(rawPath)
		if err != nil {
			fail(fmt.Sprintf("stat %s: %v", rawPath, err), 1)
		}
		if !info.IsDir() {
			if isJSONAuditFile(rawPath) {
				files = append(files, rawPath)
			}
			continue
		}
		err = filepath.WalkDir(rawPath, func(path string, entry os.DirEntry, walkErr error) error {
			if walkErr != nil {
				return walkErr
			}
			if entry.IsDir() {
				name := entry.Name()
				if name == "node_modules" || name == ".git" || name == "dist" || name == "build" {
					return filepath.SkipDir
				}
				return nil
			}
			if isJSONAuditFile(path) {
				files = append(files, path)
			}
			return nil
		})
		if err != nil {
			fail(fmt.Sprintf("scan %s: %v", rawPath, err), 1)
		}
	}

	findings := []effectAuditFinding{}
	parseErrors := []map[string]string{}
	for _, file := range files {
		payload, err := readJSONAny(file)
		if err != nil {
			parseErrors = append(parseErrors, map[string]string{"file": file, "error": err.Error()})
			continue
		}
		findings = append(findings, auditEffectPayload(file, "$", payload)...)
	}
	report := map[string]any{
		"status":              "ok",
		"files_scanned":       len(files),
		"known_effect_ids":    definitionvalidation.KnownBusinessEffectIDs(),
		"non_canonical_count": len(findings),
		"findings":            findings,
	}
	if len(parseErrors) > 0 {
		report["parse_errors"] = parseErrors
	}
	if len(findings) > 0 || len(parseErrors) > 0 {
		report["status"] = "failed"
		writeIndentedJSON(stdout, report)
		return 1
	}
	writeIndentedJSON(stdout, report)
	return 0
}

func isJSONAuditFile(path string) bool {
	lower := strings.ToLower(path)
	return strings.HasSuffix(lower, ".json")
}

func readJSONAny(path string) (any, error) {
	bytes, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var payload any
	if err := json.Unmarshal(bytes, &payload); err != nil {
		return nil, err
	}
	return payload, nil
}

func auditEffectPayload(file string, path string, value any) []effectAuditFinding {
	findings := []effectAuditFinding{}
	switch typed := value.(type) {
	case map[string]any:
		for key, item := range typed {
			childPath := path + "." + key
			if key == "business_effects" {
				if effects, ok := item.(map[string]any); ok {
					for _, field := range []string{"produces", "does_not_produce"} {
						findings = append(findings, auditEffectList(file, childPath+"."+field, effects[field])...)
					}
				}
				findings = append(findings, auditEffectPayload(file, childPath, item)...)
				continue
			}
			if key == "unsupported_effects" || key == "suppress_unsupported_effects" {
				findings = append(findings, auditEffectList(file, childPath, item)...)
				continue
			}
			findings = append(findings, auditEffectPayload(file, childPath, item)...)
		}
	case []any:
		for index, item := range typed {
			findings = append(findings, auditEffectPayload(file, fmt.Sprintf("%s[%d]", path, index), item)...)
		}
	}
	return findings
}

func auditEffectList(file string, path string, value any) []effectAuditFinding {
	items, ok := value.([]any)
	if !ok {
		return nil
	}
	findings := []effectAuditFinding{}
	for index, item := range items {
		effectID, ok := item.(string)
		if !ok {
			continue
		}
		effectID = strings.TrimSpace(effectID)
		if effectID == "" || definitionvalidation.IsKnownBusinessEffect(effectID) {
			continue
		}
		findings = append(findings, effectAuditFinding{
			File:     file,
			Path:     fmt.Sprintf("%s[%d]", path, index),
			EffectID: effectID,
		})
	}
	return findings
}

func runBuildLocal(args []string, stdout io.Writer, stderr io.Writer) int {
	var definitionPath string
	var packageID string
	var packageVersion string
	var outputDir string
	var packageName string
	var projectRef string
	var productRevisionRef string
	var developerRevisionRef string
	var sourceDocURL string
	var showcaseURL string
	var generatedAt string
	var writeDefinition bool
	var port int

	fs := flag.NewFlagSet("anip package build-local", flag.ContinueOnError)
	if hasHelpFlag(args) {
		fs.SetOutput(stdout)
	} else {
		fs.SetOutput(stderr)
	}
	fs.Usage = func() {
		writer := fs.Output()
		fmt.Fprintln(writer, `Usage:
  anip package build-local --definition <anip-service-definition.json> --package-id <id> --package-version <version> --output-dir <dir> [flags]

Builds a local example package bundle signed by the deterministic development
Registry key. This is intended for examples, local smoke tests, and reproducible
showcase artifacts. Production publication should use a real Registry.

Flags:`)
		fs.PrintDefaults()
	}
	fs.StringVar(&definitionPath, "definition", "", "Path to an anip-service-definition.json")
	fs.StringVar(&packageID, "package-id", "", "Package id")
	fs.StringVar(&packageVersion, "package-version", "", "Package version")
	fs.StringVar(&outputDir, "output-dir", "", "Directory for manifest, lock, bundle, and README artifacts")
	fs.StringVar(&packageName, "name", "", "Package display name. Defaults to service definition identity.system_name")
	fs.StringVar(&projectRef, "project-ref", "", "Project lineage reference. Defaults to studio-source:<package-id>")
	fs.StringVar(&productRevisionRef, "product-revision-ref", "", "Product revision reference")
	fs.StringVar(&developerRevisionRef, "developer-revision-ref", "", "Developer revision reference")
	fs.StringVar(&sourceDocURL, "source-doc-url", "", "Optional HTTPS source documentation URL")
	fs.StringVar(&showcaseURL, "showcase-url", "", "Optional HTTPS showcase files URL")
	fs.StringVar(&generatedAt, "generated-at", "2026-05-15T00:00:00Z", "Deterministic generated/published timestamp")
	fs.BoolVar(&writeDefinition, "write-definition", false, "Also write <package-id>-<version>-service-definition.json")
	fs.IntVar(&port, "port", 9100, "Example generated service port used in README commands")
	if err := fs.Parse(args); err != nil {
		if err == flag.ErrHelp {
			return 0
		}
		return 2
	}

	if strings.TrimSpace(definitionPath) == "" {
		fail("--definition is required", 2)
	}
	if strings.TrimSpace(packageID) == "" {
		fail("--package-id is required", 2)
	}
	if strings.TrimSpace(packageVersion) == "" {
		fail("--package-version is required", 2)
	}
	if strings.TrimSpace(outputDir) == "" {
		fail("--output-dir is required", 2)
	}

	definition, err := readJSONMap(definitionPath)
	if err != nil {
		fail(err.Error(), 1)
	}
	schemaVersion := firstNonEmpty(stringValue(definition["contract_schema_version"]), "anip-service-definition/v1")
	if schemaVersion != "anip-service-definition/v1" {
		fail("service definition contract_schema_version must be anip-service-definition/v1", 2)
	}

	definitionDigest, err := canonicalDigest(definition)
	if err != nil {
		fail(fmt.Sprintf("compute definition digest: %v", err), 1)
	}
	systemName := firstNonEmpty(packageName, nestedString(definition, "identity", "system_name"), packageID)
	serviceIDs := serviceIDsFromDefinition(definition)
	capabilityIDs := capabilityIDsFromDefinition(definition)
	if projectRef == "" {
		projectRef = "studio-source:" + packageID
	}
	if productRevisionRef == "" {
		productRevisionRef = packageID + ":product:v1"
	}
	if developerRevisionRef == "" {
		developerRevisionRef = packageID + ":developer:v1"
	}
	publishedAt, err := time.Parse(time.RFC3339, generatedAt)
	if err != nil {
		fail("--generated-at must be an RFC3339 timestamp", 2)
	}

	readme := buildLocalPackageReadme(systemName, packageID, packageVersion, port, capabilityIDs, serviceIDs)
	readiness := buildLocalAgentReadiness(definition, capabilityIDs)
	consumability := buildLocalAgentConsumability(definition)
	lineage := map[string]any{
		"project_ref": projectRef,
		"product_revision": map[string]any{
			"ref":                productRevisionRef,
			"artifact_id":        productRevisionRef,
			"revision_number":    float64(1),
			"baseline_locked_at": generatedAt,
		},
		"developer_revision": map[string]any{
			"ref":                developerRevisionRef,
			"artifact_id":        developerRevisionRef,
			"revision_number":    float64(1),
			"contract_signature": definitionDigest,
		},
	}
	sourceLinks := []registryapi.PackageSourceLink{}
	if sourceDocURL != "" {
		sourceLinks = append(sourceLinks, registryapi.PackageSourceLink{Title: "Source documentation", URL: sourceDocURL})
	}
	if showcaseURL != "" {
		sourceLinks = append(sourceLinks, registryapi.PackageSourceLink{Title: "Showcase files", URL: showcaseURL})
	}

	manifest := map[string]any{
		"package_kind":                "anip_service_blueprint",
		"artifact_type":               "anip_package_manifest",
		"blueprint_id":                packageID,
		"package_id":                  packageID,
		"name":                        systemName + " Service Blueprint",
		"version":                     packageVersion,
		"package_version":             packageVersion,
		"schema_version":              schemaVersion,
		"anip_spec_version":           core.ProtocolVersion,
		"publisher":                   map[string]any{"id": "local-dev-registry", "display_name": "Local development registry"},
		"service_definition":          "anip-service-definition.json",
		"service_definition_digest":   definitionDigest,
		"build_packs":                 map[string]any{"recommended": []any{"anip-build-pack@local"}},
		"verifier_packs":              map[string]any{"recommended": []any{"anip-verifier@local"}},
		"readme":                      readme,
		"usage":                       buildLocalUsageCommands(packageID, packageVersion, port),
		"source_links":                sourceLinksAsMaps(sourceLinks),
		"capability_count":            float64(len(capabilityIDs)),
		"service_count":               float64(len(serviceIDs)),
		"service_ids":                 stringsToAny(serviceIDs),
		"lineage":                     lineage,
		"agent_consumption_readiness": readiness,
		"agent_consumability":         consumability,
		"generated_at":                generatedAt,
	}
	lock := map[string]any{
		"lock_kind":                   "publisher_recommended_lock",
		"artifact_type":               "anip_package_lock",
		"blueprint_id":                packageID,
		"blueprint_version":           packageVersion,
		"package_id":                  packageID,
		"package_version":             packageVersion,
		"schema_version":              schemaVersion,
		"anip_spec_version":           core.ProtocolVersion,
		"service_definition_digest":   definitionDigest,
		"build_packs":                 []any{"anip-build-pack@local"},
		"verifier_packs":              []any{"anip-verifier@local"},
		"runtime_packages":            []any{},
		"extension_packs":             []any{},
		"regression_packs":            []any{},
		"selected_service_ids":        stringsToAny(serviceIDs),
		"capability_ids":              stringsToAny(capabilityIDs),
		"contract_signature":          definitionDigest,
		"lineage":                     lineage,
		"agent_consumption_readiness": readiness,
		"agent_consumability":         consumability,
		"generated_at":                generatedAt,
	}
	request := registryapi.PublishPackageRequest{
		PackageID:            packageID,
		PackageVersion:       packageVersion,
		ProjectRef:           projectRef,
		ProductRevisionRef:   productRevisionRef,
		DeveloperRevisionRef: developerRevisionRef,
		ContractSignature:    definitionDigest,
		PublisherID:          "local-dev-registry",
		PublisherType:        "local",
		Lineage:              lineage,
		SchemaVersion:        schemaVersion,
		Manifest:             manifest,
		ServiceDefinition:    definition,
		RecommendedLock:      lock,
		Readme:               readme,
		SourceLinks:          sourceLinks,
	}

	store := registryapi.NewMemoryStore()
	published, err := store.PublishPackageAt(request, publishedAt)
	if err != nil {
		fail(fmt.Sprintf("build local package: %v", err), 1)
	}
	keys := make([]any, 0, len(store.ListPublicKeys()))
	for _, key := range store.ListPublicKeys() {
		keys = append(keys, map[string]any{
			"key_id":     key.KeyID,
			"algorithm":  key.Algorithm,
			"public_key": key.PublicKey,
		})
	}
	bundle := map[string]any{
		"bundle_schema_version": "anip-package-bundle/v1",
		"authority":             "local-dev-registry",
		"publication":           published.Publication,
		"package":               published.Package,
		"receipt":               published.Receipt,
		"lineage":               published.Package.Lineage,
		"manifest":              published.Package.Manifest,
		"service_definition":    published.Package.ServiceDefinition,
		"lock":                  published.Package.RecommendedLock,
		"registry_keys":         keys,
		"digests": map[string]any{
			"manifest":           published.Package.ManifestDigest,
			"service_definition": published.Package.DefinitionDigest,
			"lock":               published.Package.LockDigest,
			"receipt":            published.Receipt.ReceiptID,
		},
	}

	if err := os.MkdirAll(outputDir, 0o755); err != nil {
		fail(fmt.Sprintf("create output dir: %v", err), 1)
	}
	prefix := filepath.Join(outputDir, packageID+"-"+packageVersion)
	if writeDefinition {
		writeJSONFile(prefix+"-service-definition.json", published.Package.ServiceDefinition)
	}
	writeJSONFile(prefix+"-manifest.json", published.Package.Manifest)
	writeJSONFile(prefix+"-lock.json", published.Package.RecommendedLock)
	writeJSONFile(prefix+".anip-package.json", bundle)
	writeTextFile(filepath.Join(outputDir, "README.md"), readme)
	fmt.Fprintf(stdout, "wrote local package bundle: %s\n", prefix+".anip-package.json")
	return 0
}

func runPublishBundle(args []string, stdout io.Writer, stderr io.Writer) int {
	var packageBundle string
	var outputPath string
	var registryURL string
	var publishToken string

	fs := flag.NewFlagSet("anip package publish-bundle", flag.ContinueOnError)
	if hasHelpFlag(args) {
		fs.SetOutput(stdout)
	} else {
		fs.SetOutput(stderr)
	}
	fs.Usage = func() {
		writer := fs.Output()
		fmt.Fprintln(writer, `Usage:
  anip package publish-bundle --package-bundle <bundle> --registry-url <url> [flags]

Publishes an existing portable package bundle to a Registry. Without
--registry-url, the command writes the exact Registry publish request JSON for
review or offline signing workflows.

Flags:`)
		fs.PrintDefaults()
	}
	fs.StringVar(&packageBundle, "package-bundle", "", "Path to an existing package bundle or registry package record JSON")
	fs.StringVar(&outputPath, "output", "", "Write the publish request JSON to this path instead of stdout")
	fs.StringVar(&registryURL, "registry-url", "", "Registry base URL. When present, publish the bundle instead of only writing the request")
	fs.StringVar(&publishToken, "publish-token", "", "Registry publish bearer token. Defaults to ANIP_REGISTRY_PUBLISH_TOKEN")
	if err := fs.Parse(args); err != nil {
		if err == flag.ErrHelp {
			return 0
		}
		return 2
	}

	if strings.TrimSpace(packageBundle) == "" {
		fail("--package-bundle is required", 2)
	}

	request, err := buildPublishBundleRequest(packageBundle)
	if err != nil {
		fail(err.Error(), 1)
	}

	if strings.TrimSpace(registryURL) != "" {
		if strings.TrimSpace(outputPath) != "" {
			fail("--output cannot be combined with --registry-url", 2)
		}
		token := strings.TrimSpace(firstNonEmpty(publishToken, os.Getenv("ANIP_REGISTRY_PUBLISH_TOKEN")))
		if token == "" {
			fail("--registry-url requires --publish-token or ANIP_REGISTRY_PUBLISH_TOKEN", 2)
		}
		result, err := publishPackageRequest(context.Background(), registryURL, token, request)
		if err != nil {
			fail(err.Error(), 1)
		}
		writeIndentedJSON(stdout, result)
		return 0
	}

	if strings.TrimSpace(outputPath) != "" {
		bytes, err := json.MarshalIndent(request, "", "  ")
		if err != nil {
			fail(fmt.Sprintf("encode publish request: %v", err), 1)
		}
		bytes = append(bytes, '\n')
		if err := os.WriteFile(outputPath, bytes, 0o600); err != nil {
			fail(fmt.Sprintf("write output: %v", err), 1)
		}
		fmt.Fprintf(stdout, "wrote publish request: %s\n", outputPath)
		return 0
	}

	writeIndentedJSON(stdout, request)
	return 0
}

func runAttachImplementation(args []string, stdout io.Writer, stderr io.Writer) int {
	var packageBundle string
	var packageVersion string
	var implementationTitle string
	var implementationRef string
	var customCodeBundleRef string
	var bundleTreeSHA256 string
	var customCodeBundle string
	var outputPath string
	var registryURL string
	var publishToken string

	fs := flag.NewFlagSet("anip package attach-implementation", flag.ContinueOnError)
	if hasHelpFlag(args) {
		fs.SetOutput(stdout)
	} else {
		fs.SetOutput(stderr)
	}
	fs.Usage = func() {
		writer := fs.Output()
		fmt.Fprintln(writer, `Usage:
  anip package attach-implementation --package-bundle <bundle> --package-version <new-version> --custom-code-bundle-ref <immutable-ref> [flags]

The command does not upload or fetch custom code. It records immutable implementation
material metadata in the publish request so the Registry can sign it as part of the
new package revision manifest.

Flags:`)
		fs.PrintDefaults()
	}
	fs.StringVar(&packageBundle, "package-bundle", "", "Path to an existing package bundle or registry package record JSON")
	fs.StringVar(&packageVersion, "package-version", "", "New package version to publish")
	fs.StringVar(&implementationTitle, "implementation-material-title", "", "Human-readable implementation material title")
	fs.StringVar(&implementationRef, "implementation-material-ref", "", "Immutable implementation material ref. Alias for --custom-code-bundle-ref")
	fs.StringVar(&customCodeBundleRef, "custom-code-bundle-ref", "", "Immutable custom bundle ref, for example git+https://repo.git@commit#sha256:<digest>")
	fs.StringVar(&bundleTreeSHA256, "bundle-tree-sha256", "", "Expected normalized local custom bundle tree digest, sha256:<64 hex chars>")
	fs.StringVar(&customCodeBundle, "custom-code-bundle", "", "Reviewed local custom bundle directory used only to compute bundle-tree-sha256; not uploaded")
	fs.StringVar(&outputPath, "output", "", "Write the publish request JSON to this path instead of stdout")
	fs.StringVar(&registryURL, "registry-url", "", "Registry base URL. When present, publish the new revision instead of only writing the request")
	fs.StringVar(&publishToken, "publish-token", "", "Registry publish bearer token. Defaults to ANIP_REGISTRY_PUBLISH_TOKEN")
	if err := fs.Parse(args); err != nil {
		if err == flag.ErrHelp {
			return 0
		}
		return 2
	}

	if strings.TrimSpace(packageBundle) == "" {
		fail("--package-bundle is required", 2)
	}
	if strings.TrimSpace(packageVersion) == "" {
		fail("--package-version is required", 2)
	}
	ref := firstNonEmpty(implementationRef, customCodeBundleRef)
	if ref == "" {
		fail("--custom-code-bundle-ref or --implementation-material-ref is required", 2)
	}
	if _, err := bundlerefs.ValidateCustomCodeBundleRef(ref); err != nil {
		fail(fmt.Sprintf("invalid custom code bundle ref: %v", err), 2)
	}
	if strings.TrimSpace(customCodeBundle) != "" {
		digest, err := generator.ComputeCustomCodeBundleTreeDigest(customCodeBundle)
		if err != nil {
			fail(err.Error(), 1)
		}
		if strings.TrimSpace(bundleTreeSHA256) != "" && !strings.EqualFold(strings.TrimSpace(bundleTreeSHA256), digest) {
			fail(fmt.Sprintf("--bundle-tree-sha256 does not match local custom bundle: expected %s computed %s", strings.ToLower(strings.TrimSpace(bundleTreeSHA256)), digest), 1)
		}
		bundleTreeSHA256 = digest
	}
	if strings.TrimSpace(bundleTreeSHA256) != "" && !bundlerefs.IsSHA256Digest(bundleTreeSHA256) {
		fail("--bundle-tree-sha256 must be sha256:<64 hex chars>", 2)
	}

	request, err := buildAttachImplementationRequest(packageBundle, packageVersion, registryapi.PackageImplementationMaterial{
		Title:            strings.TrimSpace(implementationTitle),
		Ref:              ref,
		BundleTreeSHA256: strings.ToLower(strings.TrimSpace(bundleTreeSHA256)),
	})
	if err != nil {
		fail(err.Error(), 1)
	}

	if strings.TrimSpace(registryURL) != "" {
		if strings.TrimSpace(outputPath) != "" {
			fail("--output cannot be combined with --registry-url", 2)
		}
		token := strings.TrimSpace(firstNonEmpty(publishToken, os.Getenv("ANIP_REGISTRY_PUBLISH_TOKEN")))
		if token == "" {
			fail("--registry-url requires --publish-token or ANIP_REGISTRY_PUBLISH_TOKEN", 2)
		}
		result, err := publishPackageRequest(context.Background(), registryURL, token, request)
		if err != nil {
			fail(err.Error(), 1)
		}
		writeIndentedJSON(stdout, result)
		return 0
	}

	if strings.TrimSpace(outputPath) != "" {
		bytes, err := json.MarshalIndent(request, "", "  ")
		if err != nil {
			fail(fmt.Sprintf("encode publish request: %v", err), 1)
		}
		bytes = append(bytes, '\n')
		if err := os.WriteFile(outputPath, bytes, 0o600); err != nil {
			fail(fmt.Sprintf("write output: %v", err), 1)
		}
		fmt.Fprintf(stdout, "wrote publish request: %s\n", outputPath)
		return 0
	}

	writeIndentedJSON(stdout, request)
	return 0
}

func buildAttachImplementationRequest(path string, packageVersion string, material registryapi.PackageImplementationMaterial) (registryapi.PublishPackageRequest, error) {
	request, err := buildPublishBundleRequest(path)
	if err != nil {
		return registryapi.PublishPackageRequest{}, err
	}
	request.PackageVersion = strings.TrimSpace(packageVersion)
	request.ImplementationMaterials = append(request.ImplementationMaterials, material)
	request.ImplementationMaterials = dedupeImplementationMaterials(request.ImplementationMaterials)
	return request, nil
}

func buildPublishBundleRequest(path string) (registryapi.PublishPackageRequest, error) {
	bytes, err := os.ReadFile(path)
	if err != nil {
		return registryapi.PublishPackageRequest{}, fmt.Errorf("read package bundle: %w", err)
	}
	var root map[string]any
	if err := json.Unmarshal(bytes, &root); err != nil {
		return registryapi.PublishPackageRequest{}, fmt.Errorf("decode package bundle: %w", err)
	}
	packageMap := mapValue(root["package"])
	publicationMap := mapValue(root["publication"])
	source := mergeMaps(packageMap, root)
	lineageMap := firstMap(mapValue(source["lineage"]), mapValue(root["lineage"]), mapValue(publicationMap["lineage"]))

	request := registryapi.PublishPackageRequest{
		PackageID:      stringValue(source["package_id"]),
		PackageVersion: stringValue(source["package_version"]),
		ProjectRef:     firstNonEmpty(stringValue(source["project_ref"]), stringValue(publicationMap["project_ref"]), stringValue(lineageMap["project_ref"])),
		ProductRevisionRef: firstNonEmpty(
			stringValue(source["product_revision_ref"]),
			stringValue(publicationMap["product_revision_ref"]),
			stringValue(lineageMap["product_revision_ref"]),
			stringValue(mapValue(lineageMap["product_revision"])["ref"]),
		),
		DeveloperRevisionRef: firstNonEmpty(
			stringValue(source["developer_revision_ref"]),
			stringValue(publicationMap["developer_revision_ref"]),
			stringValue(lineageMap["developer_revision_ref"]),
			stringValue(mapValue(lineageMap["developer_revision"])["ref"]),
		),
		ContractSignature: firstNonEmpty(
			stringValue(source["contract_signature"]),
			stringValue(publicationMap["contract_signature"]),
			stringValue(mapValue(lineageMap["developer_revision"])["contract_signature"]),
		),
		PublisherID:       firstNonEmpty(stringValue(source["publisher_id"]), stringValue(publicationMap["publisher_id"])),
		PublisherType:     firstNonEmpty(stringValue(source["publisher_type"]), stringValue(publicationMap["publisher_type"])),
		Lineage:           lineageMap,
		SchemaVersion:     firstNonEmpty(stringValue(source["schema_version"]), "anip-service-definition/v1"),
		Manifest:          firstMap(mapValue(root["manifest"]), mapValue(source["manifest"])),
		ServiceDefinition: firstMap(mapValue(root["service_definition"]), mapValue(source["service_definition"])),
		RecommendedLock:   firstMap(mapValue(root["lock"]), mapValue(source["recommended_lock"])),
		Readme:            firstNonEmpty(stringValue(source["readme"]), stringValue(mapValue(source["manifest"])["readme"])),
		SourceLinks:       sourceLinksFromAny(firstNonNil(source["source_links"], mapValue(source["manifest"])["source_links"])),
	}
	if request.PackageID == "" {
		return registryapi.PublishPackageRequest{}, fmt.Errorf("package bundle does not contain package_id")
	}
	if request.PackageVersion == "" {
		return registryapi.PublishPackageRequest{}, fmt.Errorf("package bundle does not contain package_version")
	}
	if request.ProjectRef == "" {
		return registryapi.PublishPackageRequest{}, fmt.Errorf("package bundle does not contain project_ref")
	}
	if request.ProductRevisionRef == "" || request.DeveloperRevisionRef == "" || request.ContractSignature == "" {
		return registryapi.PublishPackageRequest{}, fmt.Errorf("package bundle must contain product_revision_ref, developer_revision_ref, and contract_signature")
	}
	if len(request.Manifest) == 0 || len(request.ServiceDefinition) == 0 || len(request.RecommendedLock) == 0 {
		return registryapi.PublishPackageRequest{}, fmt.Errorf("package bundle must contain manifest, service_definition, and recommended_lock or lock")
	}

	request.ImplementationMaterials = existingImplementationMaterials(source)
	request.ImplementationMaterials = dedupeImplementationMaterials(request.ImplementationMaterials)
	return request, nil
}

func publishPackageRequest(ctx context.Context, registryBase string, token string, request registryapi.PublishPackageRequest) (map[string]any, error) {
	payload, err := json.Marshal(request)
	if err != nil {
		return nil, fmt.Errorf("encode publish request: %w", err)
	}
	publishURL, err := url.JoinPath(registryAPIBase(registryBase), "publications")
	if err != nil {
		return nil, fmt.Errorf("build registry publish URL: %w", err)
	}
	httpRequest, err := http.NewRequestWithContext(ctx, http.MethodPost, publishURL, bytes.NewReader(payload))
	if err != nil {
		return nil, fmt.Errorf("create registry publish request: %w", err)
	}
	httpRequest.Header.Set("Authorization", "Bearer "+token)
	httpRequest.Header.Set("Content-Type", "application/json")
	response, err := http.DefaultClient.Do(httpRequest)
	if err != nil {
		return nil, fmt.Errorf("publish package revision: %w", err)
	}
	defer response.Body.Close()
	body, _ := io.ReadAll(io.LimitReader(response.Body, 1<<20))
	if response.StatusCode < 200 || response.StatusCode >= 300 {
		return nil, fmt.Errorf("publish package revision failed: %s: %s", response.Status, strings.TrimSpace(string(body)))
	}
	var result map[string]any
	if err := json.Unmarshal(body, &result); err != nil {
		return nil, fmt.Errorf("decode registry publish response: %w", err)
	}
	return result, nil
}

func registryAPIBase(registryBase string) string {
	base := strings.TrimRight(strings.TrimSpace(registryBase), "/")
	if strings.HasSuffix(base, "/registry-api/v1") {
		return base
	}
	return base + "/registry-api/v1"
}

func existingImplementationMaterials(source map[string]any) []registryapi.PackageImplementationMaterial {
	materials := implementationMaterialsFromAny(source["implementation_materials"])
	if len(materials) > 0 {
		return materials
	}
	return implementationMaterialsFromAny(mapValue(source["manifest"])["implementation_material"])
}

func implementationMaterialsFromAny(value any) []registryapi.PackageImplementationMaterial {
	items := []any{}
	switch typed := value.(type) {
	case []any:
		items = typed
	case map[string]any:
		if nested, ok := typed["custom_code_bundles"].([]any); ok {
			items = nested
		} else {
			items = []any{typed}
		}
	default:
		return nil
	}
	materials := make([]registryapi.PackageImplementationMaterial, 0, len(items))
	for _, item := range items {
		mapped := mapValue(item)
		ref := stringValue(mapped["ref"])
		tree := firstNonEmpty(stringValue(mapped["bundle_tree_sha256"]), stringValue(mapped["tree_sha256"]))
		title := stringValue(mapped["title"])
		if ref == "" && tree == "" && title == "" {
			continue
		}
		materials = append(materials, registryapi.PackageImplementationMaterial{
			Title:            title,
			Ref:              ref,
			BundleTreeSHA256: strings.ToLower(tree),
		})
	}
	return materials
}

func dedupeImplementationMaterials(materials []registryapi.PackageImplementationMaterial) []registryapi.PackageImplementationMaterial {
	seen := map[string]struct{}{}
	output := make([]registryapi.PackageImplementationMaterial, 0, len(materials))
	for _, material := range materials {
		material.Ref = strings.TrimSpace(material.Ref)
		material.Title = strings.TrimSpace(material.Title)
		material.BundleTreeSHA256 = strings.ToLower(strings.TrimSpace(material.BundleTreeSHA256))
		if material.Ref == "" {
			continue
		}
		key := material.Ref + "\x00" + material.BundleTreeSHA256
		if _, ok := seen[key]; ok {
			continue
		}
		seen[key] = struct{}{}
		output = append(output, material)
	}
	return output
}

func sourceLinksFromAny(value any) []registryapi.PackageSourceLink {
	items, ok := value.([]any)
	if !ok {
		return nil
	}
	links := make([]registryapi.PackageSourceLink, 0, len(items))
	for _, item := range items {
		mapped := mapValue(item)
		title := stringValue(mapped["title"])
		urlValue := stringValue(mapped["url"])
		if title == "" && urlValue == "" {
			continue
		}
		links = append(links, registryapi.PackageSourceLink{Title: title, URL: urlValue})
	}
	return links
}

func readJSONMap(path string) (map[string]any, error) {
	bytes, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("read %s: %w", path, err)
	}
	var value map[string]any
	if err := json.Unmarshal(bytes, &value); err != nil {
		return nil, fmt.Errorf("decode %s: %w", path, err)
	}
	return value, nil
}

func canonicalDigest(value any) (string, error) {
	var buffer bytes.Buffer
	encoder := json.NewEncoder(&buffer)
	encoder.SetEscapeHTML(false)
	if err := encoder.Encode(value); err != nil {
		return "", err
	}
	payload := bytes.TrimSuffix(buffer.Bytes(), []byte("\n"))
	digest := sha256.Sum256(payload)
	return "sha256:" + hex.EncodeToString(digest[:]), nil
}

func nestedString(source map[string]any, path ...string) string {
	current := source
	for index, key := range path {
		value, ok := current[key]
		if !ok {
			return ""
		}
		if index == len(path)-1 {
			return stringValue(value)
		}
		current = mapValue(value)
		if len(current) == 0 {
			return ""
		}
	}
	return ""
}

func serviceIDsFromDefinition(definition map[string]any) []string {
	seen := map[string]struct{}{}
	ids := []string{}
	for _, item := range sliceFromAny(definition["service_topology_bindings"]) {
		mapped := mapValue(item)
		id := firstNonEmpty(stringValue(mapped["service_id"]), stringValue(mapped["id"]))
		if id == "" {
			continue
		}
		if _, ok := seen[id]; ok {
			continue
		}
		seen[id] = struct{}{}
		ids = append(ids, id)
	}
	for _, item := range sliceFromAny(definition["capability_formalizations"]) {
		id := stringValue(mapValue(item)["service_id"])
		if id == "" {
			continue
		}
		if _, ok := seen[id]; ok {
			continue
		}
		seen[id] = struct{}{}
		ids = append(ids, id)
	}
	return ids
}

func capabilityIDsFromDefinition(definition map[string]any) []string {
	seen := map[string]struct{}{}
	ids := []string{}
	for _, item := range sliceFromAny(definition["capability_formalizations"]) {
		mapped := mapValue(item)
		id := firstNonEmpty(stringValue(mapped["capability_id"]), stringValue(mapped["id"]))
		if id == "" {
			continue
		}
		if _, ok := seen[id]; ok {
			continue
		}
		seen[id] = struct{}{}
		ids = append(ids, id)
	}
	return ids
}

func buildLocalPackageReadme(systemName string, packageID string, packageVersion string, port int, capabilityIDs []string, serviceIDs []string) string {
	var buffer strings.Builder
	fmt.Fprintf(&buffer, "# %s\n\n", systemName)
	fmt.Fprintf(&buffer, "ANIP package `%s@%s` for local showcase and registry smoke usage.\n\n", packageID, packageVersion)
	fmt.Fprintf(&buffer, "## Contents\n\n")
	fmt.Fprintf(&buffer, "- Services: %d\n", len(serviceIDs))
	fmt.Fprintf(&buffer, "- Capabilities: %d\n", len(capabilityIDs))
	fmt.Fprintf(&buffer, "- ANIP spec: `%s`\n\n", core.ProtocolVersion)
	if len(capabilityIDs) > 0 {
		fmt.Fprintf(&buffer, "## Capability Surface\n\n")
		for _, id := range capabilityIDs {
			fmt.Fprintf(&buffer, "- `%s`\n", id)
		}
		fmt.Fprintln(&buffer)
	}
	fmt.Fprint(&buffer, "## Generate\n\n")
	fmt.Fprint(&buffer, "From a downloaded package bundle:\n\n")
	fmt.Fprintf(&buffer, "```bash\ngo run ./cmd/anip-generate --package-bundle <downloaded-package>.anip-package.json --target python --dependency-source local --output ./generated/%s --force\n```\n\n", packageID)
	fmt.Fprint(&buffer, "From a trusted registry package:\n\n")
	fmt.Fprintf(&buffer, "```bash\ngo run ./cmd/anip-generate --registry-url <registry-url> --package-id %s --package-version %s --target python --dependency-source registry --output ./generated/%s --force\n```\n\n", packageID, packageVersion, packageID)
	fmt.Fprint(&buffer, "## Verify\n\n")
	fmt.Fprint(&buffer, "```bash\ngo run ./cmd/anip-verify --definition anip-service-definition.json\ngo run ./cmd/anip-verify --package-bundle <downloaded-package>.anip-package.json\n```\n\n")
	fmt.Fprint(&buffer, "## Run Locally\n\n")
	fmt.Fprintf(&buffer, "Generated services default to port `%d` unless overridden by the generated runtime configuration.\n", port)
	return buffer.String()
}

func buildLocalUsageCommands(packageID string, packageVersion string, port int) map[string]any {
	return map[string]any{
		"generate_from_bundle": fmt.Sprintf("go run ./cmd/anip-generate --package-bundle <downloaded-package>.anip-package.json --target python --dependency-source local --output ./generated/%s --force", packageID),
		"generate_from_registry": fmt.Sprintf(
			"go run ./cmd/anip-generate --registry-url <registry-url> --package-id %s --package-version %s --target python --dependency-source registry --output ./generated/%s --force",
			packageID,
			packageVersion,
			packageID,
		),
		"verify_definition": "go run ./cmd/anip-verify --definition anip-service-definition.json",
		"verify_bundle":     "go run ./cmd/anip-verify --package-bundle <downloaded-package>.anip-package.json",
		"local_port":        float64(port),
	}
}

func buildLocalAgentReadiness(definition map[string]any, capabilityIDs []string) map[string]any {
	findings := buildLocalAgentReadinessFindings(definition)
	warnings := len(findings)
	warningPenalty := warnings * 5
	if warningPenalty > 45 {
		warningPenalty = 45
	}
	score := 100 - warningPenalty
	status := "ready"
	if warnings > 0 {
		status = "needs_review"
	}
	probes := make([]any, 0, len(capabilityIDs))
	for _, id := range capabilityIDs {
		probes = append(probes, map[string]any{
			"capability_id": id,
			"status":        "ready",
			"kind":          "contract_declared",
		})
	}
	return map[string]any{
		"artifact_type":  "agent_consumption_readiness",
		"schema_version": "anip-agent-consumption-readiness/v0",
		"status":         status,
		"score":          float64(score),
		"summary": map[string]any{
			"blockers":           float64(0),
			"warnings":           float64(warnings),
			"info":               float64(0),
			"required_app_glue":  float64(0),
			"probes":             float64(len(probes)),
			"capability_surface": float64(len(capabilityIDs)),
		},
		"findings":          findings,
		"probes":            probes,
		"required_app_glue": []any{},
	}
}

func buildLocalAgentReadinessFindings(definition map[string]any) []any {
	findings := []any{}
	for _, item := range sliceFromAny(definition["capability_formalizations"]) {
		capability := mapValue(item)
		capabilityID := firstNonEmpty(stringValue(capability["capability_id"]), stringValue(capability["id"]))
		if capabilityID == "" {
			continue
		}
		for _, inputItem := range sliceFromAny(capability["inputs"]) {
			input := mapValue(inputItem)
			required, _ := input["required"].(bool)
			if !required || hasLocalAgentInputClassification(input) {
				continue
			}
			inputName := stringValue(input["input_name"])
			if inputName == "" {
				continue
			}
			findings = append(findings, map[string]any{
				"id":             capabilityID + ":" + inputName + ":classification",
				"severity":       "warning",
				"category":       "clarification_behavior",
				"owner":          "developer_contract",
				"title":          "Required input needs meaning",
				"detail":         inputName + " is required, but the contract does not yet state what kind of business value it represents or how a user should provide it.",
				"recommendation": "Review this input and add its business meaning, format, allowed values, or clarification guidance before publishing.",
				"capability_id":  capabilityID,
				"input_name":     inputName,
				"source":         "capability",
			})
		}
	}
	return findings
}

func hasLocalAgentInputClassification(input map[string]any) bool {
	if strings.TrimSpace(stringValue(input["semantic_type"])) != "" {
		return true
	}
	if strings.TrimSpace(stringValue(input["input_format"])) != "" {
		return true
	}
	if strings.TrimSpace(stringValue(input["validation_pattern"])) != "" {
		return true
	}
	if strings.TrimSpace(stringValue(input["clarification_hint"])) != "" {
		return true
	}
	if entityReference, ok := input["entity_reference"].(bool); ok && entityReference {
		return true
	}
	return len(sliceFromAny(input["allowed_values"])) > 0
}

func buildLocalAgentConsumability(definition map[string]any) map[string]any {
	hints := []any{}
	capabilities := map[string]any{}
	for _, item := range sliceFromAny(definition["capability_formalizations"]) {
		capability := mapValue(item)
		id := firstNonEmpty(stringValue(capability["capability_id"]), stringValue(capability["id"]))
		if id == "" {
			continue
		}
		context := []any{}
		for _, inputItem := range sliceFromAny(capability["inputs"]) {
			input := mapValue(inputItem)
			name := stringValue(input["input_name"])
			if name == "" {
				continue
			}
			posture := "optional"
			if required, ok := input["required"].(bool); ok && required {
				posture = "required"
			}
			if hint := stringValue(input["clarification_hint"]); hint != "" {
				posture = posture + ":clarify"
			}
			context = append(context, map[string]any{
				"input":         name,
				"posture":       posture,
				"semantic_type": stringValue(input["semantic_type"]),
			})
		}
		hints = append(hints, map[string]any{
			"capability_id":     id,
			"title":             stringValue(capability["title"]),
			"summary":           stringValue(capability["summary"]),
			"side_effect_level": stringValue(capability["side_effect_level"]),
			"required_context":  context,
		})
		capabilities[id] = map[string]any{
			"intent": map[string]any{
				"category": id,
				"summary":  stringValue(capability["summary"]),
			},
			"business_effects": mapValue(capability["business_effects"]),
			"required_context": context,
		}
	}
	return map[string]any{
		"artifact_type":    "agent_consumability_metadata",
		"schema_version":   "anip-agent-consumability/v0",
		"capabilities":     capabilities,
		"capability_hints": hints,
	}
}

func sourceLinksAsMaps(links []registryapi.PackageSourceLink) []any {
	output := make([]any, 0, len(links))
	for _, link := range links {
		output = append(output, map[string]any{"title": link.Title, "url": link.URL})
	}
	return output
}

func stringsToAny(values []string) []any {
	output := make([]any, 0, len(values))
	for _, value := range values {
		output = append(output, value)
	}
	return output
}

func sliceFromAny(value any) []any {
	items, ok := value.([]any)
	if !ok {
		return nil
	}
	return items
}

func writeJSONFile(path string, value any) {
	bytes, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		fail(fmt.Sprintf("encode %s: %v", path, err), 1)
	}
	bytes = append(bytes, '\n')
	if err := os.WriteFile(path, bytes, 0o600); err != nil {
		fail(fmt.Sprintf("write %s: %v", path, err), 1)
	}
}

func writeTextFile(path string, value string) {
	if err := os.WriteFile(path, []byte(value), 0o600); err != nil {
		fail(fmt.Sprintf("write %s: %v", path, err), 1)
	}
}

func mapValue(value any) map[string]any {
	if mapped, ok := value.(map[string]any); ok {
		return mapped
	}
	return map[string]any{}
}

func firstMap(candidates ...map[string]any) map[string]any {
	for _, candidate := range candidates {
		if len(candidate) > 0 {
			return candidate
		}
	}
	return map[string]any{}
}

func mergeMaps(primary map[string]any, fallback map[string]any) map[string]any {
	merged := map[string]any{}
	for key, value := range fallback {
		merged[key] = value
	}
	for key, value := range primary {
		merged[key] = value
	}
	return merged
}

func firstNonNil(values ...any) any {
	for _, value := range values {
		if value != nil {
			return value
		}
	}
	return nil
}

func stringValue(value any) string {
	if text, ok := value.(string); ok {
		return strings.TrimSpace(text)
	}
	return ""
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if trimmed := strings.TrimSpace(value); trimmed != "" {
			return trimmed
		}
	}
	return ""
}

func writeIndentedJSON(writer io.Writer, value any) {
	encoder := json.NewEncoder(writer)
	encoder.SetIndent("", "  ")
	_ = encoder.Encode(value)
}

func fail(message string, code int) {
	panic(cliError{message: message, code: code})
}

func hasHelpFlag(args []string) bool {
	for _, arg := range args {
		if arg == "-h" || arg == "--help" {
			return true
		}
	}
	return false
}
