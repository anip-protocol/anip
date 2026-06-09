package main

import (
	"bytes"
	"context"
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

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/generator"
	"github.com/anip-protocol/anip/packages/go/registryapi"
	"github.com/anip-protocol/anip/packages/go/verifier"
)

type smokeResult struct {
	Status                 string   `json:"status"`
	RegistryURL            string   `json:"registry_url"`
	RegistryUIURL          string   `json:"registry_ui_url"`
	StudioAPIURL           string   `json:"studio_api_url,omitempty"`
	PackageID              string   `json:"package_id"`
	PackageVersion         string   `json:"package_version"`
	ContractSignature      string   `json:"contract_signature"`
	DefinitionDigest       string   `json:"definition_digest"`
	ManifestDigest         string   `json:"manifest_digest"`
	LockDigest             string   `json:"lock_digest"`
	ReceiptKeyID           string   `json:"receipt_key_id"`
	ReceiptAlgorithm       string   `json:"receipt_algorithm"`
	GeneratedOutput        string   `json:"generated_output"`
	GeneratedFileCount     int      `json:"generated_file_count"`
	StudioArtifactRecorded bool     `json:"studio_artifact_recorded"`
	Checks                 []string `json:"checks"`
}

func main() {
	var registryURL string
	var studioAPIURL string
	var definitionPath string
	var packageID string
	var packageVersion string
	var publishToken string
	var outputDir string
	var target string

	defaultStamp := time.Now().UTC().Format("20060102150405")
	flag.StringVar(&registryURL, "registry-url", "http://127.0.0.1:8200", "Base URL of the ANIP Registry service")
	flag.StringVar(&studioAPIURL, "studio-api-url", strings.TrimSpace(os.Getenv("STUDIO_API_URL")), "Optional Studio API URL for recording the Registry publication artifact")
	flag.StringVar(&definitionPath, "definition", filepath.Join("generator", "testdata", "work-item-fronting-definition.json"), "Path to an anip-service-definition.json fixture")
	flag.StringVar(&packageID, "package-id", "studio-registry-smoke-"+defaultStamp, "Package id to publish")
	flag.StringVar(&packageVersion, "package-version", "0.1.0", "Package version to publish")
	flag.StringVar(&publishToken, "publish-token", strings.TrimSpace(os.Getenv("ANIP_REGISTRY_PUBLISH_TOKEN")), "Registry publish bearer token. Defaults to ANIP_REGISTRY_PUBLISH_TOKEN")
	flag.StringVar(&outputDir, "output", filepath.Join(os.TempDir(), "anip-registry-smoke-generated-"+defaultStamp), "Generated project output directory")
	flag.StringVar(&target, "target", "typescript", "Generation target to smoke; currently supports typescript")
	flag.Parse()

	if target != "typescript" {
		fail(fmt.Sprintf("unsupported smoke target %q; use typescript", target))
	}

	client := http.DefaultClient
	registryURL = strings.TrimRight(strings.TrimSpace(registryURL), "/")
	if registryURL == "" {
		fail("registry-url is required")
	}

	definition, err := readJSONFile(definitionPath)
	if err != nil {
		fail(err.Error())
	}
	contractSignature := nestedString(definition, "compiled_contract_identity", "signature")
	if contractSignature == "" {
		fail("definition compiled_contract_identity.signature is required")
	}
	schemaVersion := stringValue(definition["contract_schema_version"])
	if schemaVersion == "" {
		schemaVersion = "anip-service-definition/v1"
	}
	agentReadiness := smokeAgentReadiness()
	agentConsumability := smokeAgentConsumability(definition)

	result := smokeResult{
		Status:            "ok",
		RegistryURL:       registryURL,
		RegistryUIURL:     registryURL + "/registry/packages",
		StudioAPIURL:      strings.TrimRight(strings.TrimSpace(studioAPIURL), "/"),
		PackageID:         packageID,
		PackageVersion:    packageVersion,
		ContractSignature: contractSignature,
		GeneratedOutput:   outputDir,
	}

	if err := expectOK(client, registryURL+"/registry-api/v1/healthz", "registry health"); err != nil {
		fail(err.Error())
	}
	result.Checks = append(result.Checks, "registry_api_reachable")

	publishRequest := registryapi.PublishPackageRequest{
		PackageID:            packageID,
		PackageVersion:       packageVersion,
		ProjectRef:           packageID,
		ProductRevisionRef:   "product-smoke-r1",
		DeveloperRevisionRef: "developer-smoke-r1",
		ContractSignature:    contractSignature,
		SchemaVersion:        schemaVersion,
		Manifest: map[string]any{
			"package_kind":                "anip_service_blueprint",
			"blueprint_id":                packageID,
			"name":                        "Studio Registry Smoke",
			"version":                     packageVersion,
			"schema_version":              schemaVersion,
			"anip_spec_version":           core.ProtocolVersion,
			"agent_consumption_readiness": agentReadiness,
			"agent_consumability":         agentConsumability,
		},
		ServiceDefinition: definition,
		RecommendedLock: map[string]any{
			"lock_kind":                   "publisher_recommended_lock",
			"blueprint_id":                packageID,
			"blueprint_version":           packageVersion,
			"build_packs":                 []any{"anip-build-pack@local"},
			"verifier_packs":              []any{"anip-verifier@local"},
			"runtime_packages":            []any{},
			"agent_consumption_readiness": agentReadiness,
			"agent_consumability":         agentConsumability,
		},
	}
	published, err := publishPackage(client, registryURL, publishToken, publishRequest)
	if err != nil {
		fail(err.Error())
	}
	result.DefinitionDigest = published.Package.DefinitionDigest
	result.ManifestDigest = published.Package.ManifestDigest
	result.LockDigest = published.Package.LockDigest
	result.ReceiptKeyID = published.Receipt.KeyID
	result.ReceiptAlgorithm = published.Receipt.SignatureAlgorithm
	result.Checks = append(result.Checks, "registry_publication_created")

	if result.StudioAPIURL != "" {
		recorded, err := recordStudioPublication(client, result.StudioAPIURL, published)
		if err != nil {
			fail(err.Error())
		}
		result.StudioArtifactRecorded = recorded
		result.Checks = append(result.Checks, "studio_publication_artifact_recorded")
	}

	if err := expectBodyContains(client, registryURL+"/registry/packages", "ANIP Registry", "registry UI shell"); err != nil {
		fail(err.Error())
	}
	result.Checks = append(result.Checks, "registry_ui_shell_served")

	detailURL := fmt.Sprintf(
		"%s/registry/packages/%s/%s",
		registryURL,
		url.PathEscape(packageID),
		url.PathEscape(packageVersion),
	)
	if err := expectBodyContains(client, detailURL, "ANIP Registry", "registry UI package detail route"); err != nil {
		fail(err.Error())
	}
	result.Checks = append(result.Checks, "registry_ui_detail_route_served")

	verifyResult, err := verifier.VerifyServiceDefinition(context.Background(), client, verifier.VerifyOptions{
		RegistryBase:              registryURL,
		PackageRef:                packageID + "@" + packageVersion,
		ExpectedContractSignature: contractSignature,
	})
	if err != nil {
		fail(fmt.Sprintf("verify registry package: %v", err))
	}
	if verifyResult.Status != "ok" {
		bytes, _ := json.MarshalIndent(verifyResult, "", "  ")
		fail("verify registry package failed: " + string(bytes))
	}
	result.Checks = append(result.Checks, "go_verifier_trusts_registry_package")

	resolved, err := generator.ResolveServiceDefinition(context.Background(), client, generator.ResolveServiceDefinitionOptions{
		RegistryBase: registryURL,
		PackageRef:   packageID + "@" + packageVersion,
	})
	if err != nil {
		fail(fmt.Sprintf("resolve registry package for generation: %v", err))
	}
	parsedDefinition, err := generator.ParseServiceDefinition(resolved.DefinitionBytes)
	if err != nil {
		fail(fmt.Sprintf("parse resolved service definition: %v", err))
	}
	project, err := generator.BuildTypeScriptProject(parsedDefinition, generator.BuildTypeScriptProjectOptions{
		DependencySource: generator.DependencySourceLocal,
		HttpRuntime:      generator.HttpRuntimeHono,
		Port:             4100,
	})
	if err != nil {
		fail(fmt.Sprintf("build TypeScript project: %v", err))
	}
	if err := generator.WriteGeneratedProject(project, outputDir, true); err != nil {
		fail(fmt.Sprintf("write generated project: %v", err))
	}
	result.GeneratedFileCount = len(project.Files)
	result.Checks = append(result.Checks, "go_generator_generated_from_registry_package")

	encoder := json.NewEncoder(os.Stdout)
	encoder.SetIndent("", "  ")
	_ = encoder.Encode(result)
}

func smokeAgentReadiness() map[string]any {
	return map[string]any{
		"artifact_type":     "agent_consumption_readiness",
		"status":            "ready",
		"score":             float64(100),
		"findings":          []any{},
		"required_app_glue": []any{},
		"summary": map[string]any{
			"blockers":          float64(0),
			"warnings":          float64(0),
			"info":              float64(0),
			"probes":            float64(1),
			"required_app_glue": float64(0),
		},
		"probes": []any{
			map[string]any{
				"id":               "registry-smoke-probe",
				"expected_outcome": "success",
			},
		},
	}
}

func smokeAgentConsumability(definition map[string]any) map[string]any {
	capabilities := map[string]any{}
	for _, item := range sliceValue(definition["capability_formalizations"]) {
		capability, _ := item.(map[string]any)
		if len(capability) == 0 {
			continue
		}
		capabilityID := stringValue(capability["capability_id"])
		if capabilityID == "" {
			capabilityID = stringValue(capability["id"])
		}
		if capabilityID == "" {
			continue
		}
		summary := stringValue(capability["summary"])
		if summary == "" {
			summary = stringValue(capability["title"])
		}
		capabilities[capabilityID] = map[string]any{
			"intent": map[string]any{
				"category": capabilityID,
				"summary":  summary,
			},
			"business_effects": map[string]any{
				"produces":         []any{canonicalSmokeProducedEffect(capability)},
				"does_not_produce": []any{"raw_data_export", "system.mutation"},
			},
		}
	}
	if len(capabilities) == 0 {
		capabilities["registry.smoke"] = map[string]any{
			"intent": map[string]any{
				"category": "registry.smoke",
				"summary":  "Registry smoke capability hint.",
			},
			"business_effects": map[string]any{
				"produces":         []any{"data.read"},
				"does_not_produce": []any{"raw_data_export", "system.mutation"},
			},
		}
	}
	return map[string]any{
		"artifact_type":  "agent_consumability_metadata",
		"schema_version": "anip-agent-consumability/v0",
		"capabilities":   capabilities,
	}
}

func canonicalSmokeProducedEffect(capability map[string]any) string {
	operationType := stringValue(capability["operation_type"])
	sideEffectLevel := stringValue(capability["side_effect_level"])
	switch {
	case operationType == "create" || operationType == "update" || operationType == "delete":
		return "system.preview_mutation"
	case sideEffectLevel == "external":
		return "external_dispatch"
	case operationType == "summarize":
		return "content.summary"
	case operationType == "recommend":
		return "content.recommendation"
	default:
		return "data.read"
	}
}

func readJSONFile(path string) (map[string]any, error) {
	bytes, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("read definition: %w", err)
	}
	var payload map[string]any
	if err := json.Unmarshal(bytes, &payload); err != nil {
		return nil, fmt.Errorf("decode definition: %w", err)
	}
	return payload, nil
}

func publishPackage(client *http.Client, registryURL string, publishToken string, request registryapi.PublishPackageRequest) (registryapi.PublishPackageResult, error) {
	var result registryapi.PublishPackageResult
	encoded, err := json.Marshal(request)
	if err != nil {
		return result, fmt.Errorf("encode publish request: %w", err)
	}
	httpRequest, err := http.NewRequest(http.MethodPost, registryURL+"/registry-api/v1/publications", bytes.NewReader(encoded))
	if err != nil {
		return result, fmt.Errorf("create publish request: %w", err)
	}
	httpRequest.Header.Set("Content-Type", "application/json")
	if strings.TrimSpace(publishToken) != "" {
		httpRequest.Header.Set("Authorization", "Bearer "+strings.TrimSpace(publishToken))
	}
	resp, err := client.Do(httpRequest)
	if err != nil {
		return result, fmt.Errorf("publish package: %w", err)
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(io.LimitReader(resp.Body, 1_000_000))
	if resp.StatusCode != http.StatusCreated {
		return result, fmt.Errorf("publish package failed (%d): %s", resp.StatusCode, strings.TrimSpace(string(body)))
	}
	if err := json.Unmarshal(body, &result); err != nil {
		return result, fmt.Errorf("decode publish result: %w", err)
	}
	return result, nil
}

func recordStudioPublication(client *http.Client, studioAPIURL string, published registryapi.PublishPackageResult) (bool, error) {
	projectID := published.Package.ProjectRef
	if err := ensureStudioProject(client, studioAPIURL, projectID); err != nil {
		return false, err
	}
	artifact := map[string]any{
		"id":    fmt.Sprintf("%s-registry-publication-%d", projectID, time.Now().UTC().UnixNano()),
		"title": fmt.Sprintf("Registry Publication %s@%s", published.Package.PackageID, published.Package.PackageVersion),
		"data": map[string]any{
			"artifact_type": "developer_registry_publication",
			"authority":     "remote-registry",
			"publication":   published.Publication,
			"package":       published.Package,
			"receipt":       published.Receipt,
			"published_from_saved_revision": map[string]any{
				"revision_number":      1,
				"revision_artifact_id": published.Package.DeveloperRevisionRef,
				"baseline_locked_at":   published.Publication.PublishedAt,
			},
		},
	}
	encoded, err := json.Marshal(artifact)
	if err != nil {
		return false, fmt.Errorf("encode Studio artifact: %w", err)
	}
	resp, err := client.Post(studioAPIURL+"/api/projects/"+url.PathEscape(projectID)+"/pm-artifacts", "application/json", bytes.NewReader(encoded))
	if err != nil {
		return false, fmt.Errorf("record Studio publication artifact: %w", err)
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(io.LimitReader(resp.Body, 64_000))
	if resp.StatusCode != http.StatusCreated {
		return false, fmt.Errorf("record Studio publication artifact failed (%d): %s", resp.StatusCode, strings.TrimSpace(string(body)))
	}
	return true, nil
}

func ensureStudioProject(client *http.Client, studioAPIURL string, projectID string) error {
	body := map[string]any{
		"id":           projectID,
		"name":         "Studio Registry Smoke",
		"summary":      "Generated by anip-registry-smoke.",
		"domain":       "registry-smoke",
		"labels":       []any{"registry", "smoke"},
		"project_type": "governed_service_project",
		"integration_profile": map[string]any{
			"kind":    "native_api",
			"systems": []any{"work-items"},
		},
	}
	encoded, err := json.Marshal(body)
	if err != nil {
		return fmt.Errorf("encode Studio project: %w", err)
	}
	resp, err := client.Post(studioAPIURL+"/api/projects", "application/json", bytes.NewReader(encoded))
	if err != nil {
		return fmt.Errorf("create Studio project: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode == http.StatusCreated || resp.StatusCode == http.StatusConflict {
		return nil
	}
	responseBody, _ := io.ReadAll(io.LimitReader(resp.Body, 64_000))
	return fmt.Errorf("create Studio project failed (%d): %s", resp.StatusCode, strings.TrimSpace(string(responseBody)))
}

func expectOK(client *http.Client, requestURL string, label string) error {
	resp, err := client.Get(requestURL)
	if err != nil {
		return fmt.Errorf("%s request failed: %w", label, err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
		return fmt.Errorf("%s returned %d: %s", label, resp.StatusCode, strings.TrimSpace(string(body)))
	}
	return nil
}

func expectBodyContains(client *http.Client, requestURL string, expected string, label string) error {
	resp, err := client.Get(requestURL)
	if err != nil {
		return fmt.Errorf("%s request failed: %w", label, err)
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(io.LimitReader(resp.Body, 1_000_000))
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("%s returned %d: %s", label, resp.StatusCode, strings.TrimSpace(string(body)))
	}
	if !strings.Contains(string(body), expected) {
		return fmt.Errorf("%s did not contain %q", label, expected)
	}
	return nil
}

func nestedString(payload map[string]any, keys ...string) string {
	var current any = payload
	for _, key := range keys {
		next, ok := current.(map[string]any)
		if !ok {
			return ""
		}
		current = next[key]
	}
	value, _ := current.(string)
	return value
}

func stringValue(value any) string {
	text, _ := value.(string)
	return text
}

func sliceValue(value any) []any {
	items, _ := value.([]any)
	return items
}

func fail(message string) {
	fmt.Fprintln(os.Stderr, message)
	os.Exit(1)
}
