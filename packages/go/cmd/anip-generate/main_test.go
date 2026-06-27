package main

import (
	"context"
	"encoding/json"
	"net/http/httptest"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"

	"github.com/anip-protocol/anip/packages/go/registryapi"
)

func testCapabilityIDsFromDefinition(t *testing.T, definition map[string]any) []string {
	t.Helper()
	rawCapabilities, ok := definition["capability_formalizations"].([]any)
	if !ok || len(rawCapabilities) == 0 {
		t.Fatalf("definition fixture is missing capability_formalizations")
	}
	ids := make([]string, 0, len(rawCapabilities))
	for _, raw := range rawCapabilities {
		capability, ok := raw.(map[string]any)
		if !ok {
			t.Fatalf("invalid capability fixture entry: %+v", raw)
		}
		id, _ := capability["capability_id"].(string)
		if strings.TrimSpace(id) == "" {
			t.Fatalf("capability fixture entry is missing capability_id: %+v", capability)
		}
		ids = append(ids, id)
	}
	return ids
}

func testAgentConsumptionReadiness() map[string]any {
	return map[string]any{
		"artifact_type": "agent_consumption_readiness",
		"status":        "ready",
		"score":         float64(100),
		"summary": map[string]any{
			"blockers":          float64(0),
			"warnings":          float64(0),
			"info":              float64(0),
			"probes":            float64(1),
			"required_app_glue": float64(0),
		},
		"findings":          []any{},
		"required_app_glue": []any{},
		"probes": []any{
			map[string]any{
				"id":               "probe-1",
				"label":            "Search work items",
				"prompt":           "Search work items",
				"expected_outcome": "success",
				"rationale":        "Smoke test covers the published capability surface.",
			},
		},
	}
}

func testAgentConsumabilityFor(ids []string) map[string]any {
	capabilities := map[string]any{}
	for _, id := range ids {
		capabilities[id] = map[string]any{
			"intent": map[string]any{
				"category": id,
				"summary":  "Governed capability exposed by the package fixture.",
			},
			"business_effects": map[string]any{
				"produces":         []any{"data.read"},
				"does_not_produce": []any{"system.mutation"},
			},
		}
	}
	return map[string]any{
		"artifact_type":  "agent_consumability_metadata",
		"schema_version": "anip-agent-consumability/v0",
		"capabilities":   capabilities,
	}
}

func testPackageManifest(t *testing.T, definition map[string]any, name string, version string) map[string]any {
	t.Helper()
	ids := testCapabilityIDsFromDefinition(t, definition)
	return map[string]any{
		"name":                        name,
		"version":                     version,
		"anip_spec_version":           "anip/0.24",
		"agent_consumability":         testAgentConsumabilityFor(ids),
		"agent_consumption_readiness": testAgentConsumptionReadiness(),
	}
}

func TestCLIGeneratesAllTargetsFromFixture(t *testing.T) {
	wd, err := os.Getwd()
	if err != nil {
		t.Fatalf("get working directory: %v", err)
	}
	definitionPath := fixtureDefinitionPath(wd)

	cases := []struct {
		target       string
		expectedFile string
	}{
		{target: "typescript", expectedFile: filepath.Join("src", "main.ts")},
		{target: "go", expectedFile: "main.go"},
		{target: "python", expectedFile: filepath.Join("src", "work_item_governance_service", "app.py")},
		{target: "java", expectedFile: "pom.xml"},
		{target: "csharp", expectedFile: "WorkItemGovernanceService.csproj"},
	}

	for _, tc := range cases {
		t.Run(tc.target, func(t *testing.T) {
			outputDir := filepath.Join(t.TempDir(), tc.target)
			args := []string{
				"run", ".",
				"--definition", definitionPath,
				"--target", tc.target,
				"--dependency-source", "local",
				"--output", outputDir,
				"--force",
			}
			cmd := exec.Command("go", args...)
			cmd.Dir = wd
			cmd.Env = append(os.Environ(), "GOCACHE="+filepath.Join(t.TempDir(), "gocache"))

			out, err := cmd.CombinedOutput()
			if err != nil {
				t.Fatalf("go %v failed: %v\n%s", args, err, out)
			}

			var result struct {
				Status        string `json:"status"`
				Target        string `json:"target"`
				SourceKind    string `json:"source_kind"`
				PackageName   string `json:"package_name"`
				SystemName    string `json:"system_name"`
				FileCount     int    `json:"file_count"`
				AgentKitFiles int    `json:"agent_consumption_kit_files"`
			}
			if err := json.Unmarshal(out, &result); err != nil {
				t.Fatalf("parse CLI JSON output: %v\n%s", err, out)
			}
			if result.Status != "ok" || result.Target != tc.target || result.SourceKind != "file" {
				t.Fatalf("unexpected CLI result: %+v", result)
			}
			if result.SystemName != "work-item-governance-service" || result.FileCount == 0 {
				t.Fatalf("unexpected generated project metadata: %+v", result)
			}
			if result.AgentKitFiles == 0 {
				t.Fatalf("expected generated agent consumption kit files: %+v", result)
			}

			if _, err := os.Stat(filepath.Join(outputDir, tc.expectedFile)); err != nil {
				t.Fatalf("expected generated file %s: %v", tc.expectedFile, err)
			}
			if _, err := os.Stat(filepath.Join(outputDir, "agent-consumption", "capability-index.json")); err != nil {
				t.Fatalf("expected generated agent consumption kit: %v", err)
			}
		})
	}
}

func TestCLIGeneratesStdioRunners(t *testing.T) {
	wd, err := os.Getwd()
	if err != nil {
		t.Fatalf("get working directory: %v", err)
	}
	definitionPath := fixtureDefinitionPath(wd)

	cases := []struct {
		target       string
		expectedFile string
	}{
		{target: "typescript", expectedFile: filepath.Join("src", "stdio.ts")},
		{target: "go", expectedFile: "main.go"},
		{target: "python", expectedFile: filepath.Join("src", "work_item_governance_service", "stdio_app.py")},
		{target: "java", expectedFile: filepath.Join("src", "main", "java", "dev", "anip", "generated", "work_item_governance_service", "StdioMain.java")},
		{target: "csharp", expectedFile: "Program.cs"},
	}

	for _, tc := range cases {
		t.Run(tc.target, func(t *testing.T) {
			outputDir := filepath.Join(t.TempDir(), tc.target)
			args := []string{
				"run", ".",
				"--definition", definitionPath,
				"--target", tc.target,
				"--transport", "stdio",
				"--dependency-source", "local",
				"--output", outputDir,
				"--force",
			}
			cmd := exec.Command("go", args...)
			cmd.Dir = wd
			cmd.Env = append(os.Environ(), "GOCACHE="+filepath.Join(t.TempDir(), "gocache"))

			out, err := cmd.CombinedOutput()
			if err != nil {
				t.Fatalf("go %v failed: %v\n%s", args, err, out)
			}

			var result struct {
				Status     string   `json:"status"`
				Target     string   `json:"target"`
				Transports []string `json:"transports"`
			}
			if err := json.Unmarshal(out, &result); err != nil {
				t.Fatalf("parse CLI JSON output: %v\n%s", err, out)
			}
			if result.Status != "ok" || result.Target != tc.target {
				t.Fatalf("unexpected CLI result: %+v", result)
			}
			if !stringSliceContains(result.Transports, "http") || !stringSliceContains(result.Transports, "stdio") {
				t.Fatalf("expected http and stdio transports, got %+v", result.Transports)
			}
			content, err := os.ReadFile(filepath.Join(outputDir, tc.expectedFile))
			if err != nil {
				t.Fatalf("expected generated stdio file %s: %v", tc.expectedFile, err)
			}
			if !strings.Contains(strings.ToLower(string(content)), "stdio") {
				t.Fatalf("expected %s to contain stdio runner code", tc.expectedFile)
			}
		})
	}
}

func TestCLIGeneratesJavaQuarkusFramework(t *testing.T) {
	wd, err := os.Getwd()
	if err != nil {
		t.Fatalf("get working directory: %v", err)
	}
	outputDir := filepath.Join(t.TempDir(), "java-quarkus")
	args := []string{
		"run", ".",
		"--definition", fixtureDefinitionPath(wd),
		"--target", "java",
		"--framework", "quarkus",
		"--dependency-source", "local",
		"--output", outputDir,
		"--force",
	}
	cmd := exec.Command("go", args...)
	cmd.Dir = wd
	cmd.Env = append(os.Environ(), "GOCACHE="+filepath.Join(t.TempDir(), "gocache"))

	out, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("go %v failed: %v\n%s", args, err, out)
	}

	var result struct {
		Status    string `json:"status"`
		Target    string `json:"target"`
		Framework string `json:"framework"`
	}
	if err := json.Unmarshal(out, &result); err != nil {
		t.Fatalf("parse CLI JSON output: %v\n%s", err, out)
	}
	if result.Status != "ok" || result.Target != "java" || result.Framework != "quarkus" {
		t.Fatalf("unexpected CLI result: %+v", result)
	}
	pom, err := os.ReadFile(filepath.Join(outputDir, "pom.xml"))
	if err != nil {
		t.Fatalf("read quarkus pom: %v", err)
	}
	if !strings.Contains(string(pom), "<artifactId>quarkus-rest-jackson</artifactId>") || !strings.Contains(string(pom), "packages/java/anip-quarkus/src/main/java") {
		t.Fatalf("expected generated quarkus pom")
	}
}

func TestCLIGeneratesTypeScriptExpressFramework(t *testing.T) {
	wd, err := os.Getwd()
	if err != nil {
		t.Fatalf("get working directory: %v", err)
	}
	outputDir := filepath.Join(t.TempDir(), "typescript-express")
	args := []string{
		"run", ".",
		"--definition", fixtureDefinitionPath(wd),
		"--target", "typescript",
		"--framework", "express",
		"--dependency-source", "local",
		"--output", outputDir,
		"--force",
	}
	cmd := exec.Command("go", args...)
	cmd.Dir = wd
	cmd.Env = append(os.Environ(), "GOCACHE="+filepath.Join(t.TempDir(), "gocache"))

	out, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("go %v failed: %v\n%s", args, err, out)
	}

	var result struct {
		Status    string `json:"status"`
		Target    string `json:"target"`
		Framework string `json:"framework"`
	}
	if err := json.Unmarshal(out, &result); err != nil {
		t.Fatalf("parse CLI JSON output: %v\n%s", err, out)
	}
	if result.Status != "ok" || result.Target != "typescript" || result.Framework != "express" {
		t.Fatalf("unexpected CLI result: %+v", result)
	}
	app, err := os.ReadFile(filepath.Join(outputDir, "src", "app.ts"))
	if err != nil {
		t.Fatalf("read generated app: %v", err)
	}
	if !strings.Contains(string(app), `import express from "express";`) || !strings.Contains(string(app), `@anip-dev/express`) {
		t.Fatalf("expected generated Express app")
	}
}

func TestCLIGeneratesFromPackageBundle(t *testing.T) {
	wd, err := os.Getwd()
	if err != nil {
		t.Fatalf("get working directory: %v", err)
	}
	definitionPath := fixtureDefinitionPath(wd)
	definitionBytes, err := os.ReadFile(definitionPath)
	if err != nil {
		t.Fatalf("read definition fixture: %v", err)
	}
	var serviceDefinition map[string]any
	if err := json.Unmarshal(definitionBytes, &serviceDefinition); err != nil {
		t.Fatalf("decode definition fixture: %v", err)
	}

	tempDir := t.TempDir()
	bundlePath := filepath.Join(tempDir, "work-item-fronting-0.2.0.anip-package.json")
	lineage := map[string]any{
		"project_ref": "work-item-fronting",
		"product_revision": map[string]any{
			"ref":             "product-r3",
			"artifact_id":     "product-r3",
			"revision_number": float64(3),
		},
		"developer_revision": map[string]any{
			"ref":                "developer-r5",
			"artifact_id":        "developer-r5",
			"revision_number":    float64(5),
			"contract_signature": "sha256:test-contract",
		},
	}
	implementationMaterials := []registryapi.PackageImplementationMaterial{
		{
			Title: "Reviewed app glue",
			Ref:   "registry://acme/work-item-glue@1.2.3#sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
		},
	}
	packageResult, err := registryapi.NewMemoryStore().PublishPackage(registryapi.PublishPackageRequest{
		PackageID:               "work-item-fronting",
		PackageVersion:          "0.2.0",
		ProjectRef:              "work-item-fronting",
		ProductRevisionRef:      "product-r3",
		DeveloperRevisionRef:    "developer-r5",
		ContractSignature:       "sha256:test-contract",
		Lineage:                 lineage,
		SchemaVersion:           "anip-service-definition/v1",
		Manifest:                testPackageManifest(t, serviceDefinition, "Work Item Fronting", "0.2.0"),
		ServiceDefinition:       serviceDefinition,
		RecommendedLock:         map[string]any{"verifier_pack": map[string]any{"name": "anip-verifier"}},
		ImplementationMaterials: implementationMaterials,
	})
	if err != nil {
		t.Fatalf("publish package fixture: %v", err)
	}
	bundleBytes, err := json.Marshal(map[string]any{
		"bundle_schema_version": "anip-package-bundle/v1",
		"authority":             "local-studio",
		"lineage":               lineage,
		"package":               packageResult.Package,
		"receipt": map[string]any{
			"registry_signature":  packageResult.Receipt.RegistrySignature,
			"issued_at":           packageResult.Receipt.IssuedAt,
			"authority":           "local-studio",
			"key_id":              packageResult.Receipt.KeyID,
			"signature_algorithm": packageResult.Receipt.SignatureAlgorithm,
		},
	})
	if err != nil {
		t.Fatalf("marshal package bundle: %v", err)
	}
	if err := os.WriteFile(bundlePath, bundleBytes, 0o600); err != nil {
		t.Fatalf("write package bundle: %v", err)
	}

	outputDir := filepath.Join(tempDir, "generated")
	args := []string{
		"run", ".",
		"--package-bundle", bundlePath,
		"--target", "typescript",
		"--dependency-source", "local",
		"--output", outputDir,
		"--force",
	}
	cmd := exec.Command("go", args...)
	cmd.Dir = wd
	cmd.Env = append(os.Environ(), "GOCACHE="+filepath.Join(t.TempDir(), "gocache"))

	out, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("go %v failed: %v\n%s", args, err, out)
	}

	var result struct {
		Status            string         `json:"status"`
		Target            string         `json:"target"`
		SourceKind        string         `json:"source_kind"`
		PackageID         string         `json:"package_id"`
		PackageVersion    string         `json:"package_version"`
		ReceiptAuthority  string         `json:"receipt_authority"`
		ReceiptSignature  string         `json:"receipt_signature"`
		ProductRevision   map[string]any `json:"product_revision"`
		DeveloperRevision map[string]any `json:"developer_revision"`
		FileCount         int            `json:"file_count"`
		AgentKitFiles     int            `json:"agent_consumption_kit_files"`
		CustomRefs        []struct {
			Ref    string `json:"ref"`
			Kind   string `json:"kind"`
			Source string `json:"source"`
		} `json:"custom_code_bundle_refs"`
		CustomWarnings []string `json:"custom_code_bundle_warnings"`
	}
	if err := json.Unmarshal(out, &result); err != nil {
		t.Fatalf("parse CLI JSON output: %v\n%s", err, out)
	}
	if result.Status != "ok" || result.Target != "typescript" || result.SourceKind != "package-bundle" {
		t.Fatalf("unexpected CLI result: %+v", result)
	}
	if result.PackageID != "work-item-fronting" || result.PackageVersion != "0.2.0" || result.FileCount == 0 {
		t.Fatalf("unexpected package bundle metadata: %+v", result)
	}
	if result.AgentKitFiles == 0 {
		t.Fatalf("expected generated agent consumption kit metadata: %+v", result)
	}
	if len(result.CustomRefs) != 1 || result.CustomRefs[0].Kind != "registry" || !strings.Contains(result.CustomRefs[0].Source, "manifest") {
		t.Fatalf("expected package-declared custom bundle ref metadata, got %+v", result.CustomRefs)
	}
	if len(result.CustomWarnings) == 0 || !strings.Contains(result.CustomWarnings[0], "not fetched or applied") {
		t.Fatalf("expected metadata-only custom bundle warning, got %+v", result.CustomWarnings)
	}
	if result.ReceiptAuthority != "local-studio" || result.ReceiptSignature != packageResult.Receipt.RegistrySignature {
		t.Fatalf("expected receipt metadata, got %+v", result)
	}
	if result.ProductRevision["ref"] != "product-r3" || result.DeveloperRevision["ref"] != "developer-r5" {
		t.Fatalf("expected lineage metadata, got product=%+v developer=%+v", result.ProductRevision, result.DeveloperRevision)
	}
	if _, err := os.Stat(filepath.Join(outputDir, "src", "main.ts")); err != nil {
		t.Fatalf("expected generated TypeScript host: %v", err)
	}
	if _, err := os.Stat(filepath.Join(outputDir, "agent-consumption", "prompt-brief.md")); err != nil {
		t.Fatalf("expected generated agent prompt brief: %v", err)
	}
}

func TestCLIGeneratesFromTrustedRegistryPackage(t *testing.T) {
	wd, err := os.Getwd()
	if err != nil {
		t.Fatalf("get working directory: %v", err)
	}
	definitionPath := fixtureDefinitionPath(wd)
	definitionBytes, err := os.ReadFile(definitionPath)
	if err != nil {
		t.Fatalf("read definition fixture: %v", err)
	}
	var serviceDefinition map[string]any
	if err := json.Unmarshal(definitionBytes, &serviceDefinition); err != nil {
		t.Fatalf("decode definition fixture: %v", err)
	}

	store := registryapi.NewMemoryStore()
	if _, err := store.PublishPackage(registryapi.PublishPackageRequest{
		PackageID:            "work-item-fronting",
		PackageVersion:       "0.2.0",
		ProjectRef:           "work-item-fronting",
		ProductRevisionRef:   "product-r3",
		DeveloperRevisionRef: "developer-r5",
		ContractSignature:    "sha256:test-contract",
		Lineage: map[string]any{
			"project_ref": "work-item-fronting",
			"product_revision": map[string]any{
				"ref":             "product-r3",
				"artifact_id":     "product-r3",
				"revision_number": float64(3),
			},
			"developer_revision": map[string]any{
				"ref":                "developer-r5",
				"artifact_id":        "developer-r5",
				"revision_number":    float64(5),
				"contract_signature": "sha256:test-contract",
			},
		},
		SchemaVersion:     "anip-service-definition/v1",
		Manifest:          testPackageManifest(t, serviceDefinition, "Work Item Fronting", "0.2.0"),
		ServiceDefinition: serviceDefinition,
		RecommendedLock:   map[string]any{"verifier_pack": map[string]any{"name": "anip-verifier"}},
	}); err != nil {
		t.Fatalf("publish package: %v", err)
	}
	if _, _, err := store.UpdatePackageLifecycle(context.Background(), "work-item-fronting", "0.2.0", registryapi.UpdatePackageLifecycleRequest{
		Status:                    registryapi.PackageLifecycleSuperseded,
		Reason:                    "Use the regenerated package.",
		ReplacementPackageID:      "work-item-fronting",
		ReplacementPackageVersion: "0.2.1",
	}, "admin"); err != nil {
		t.Fatalf("update package lifecycle: %v", err)
	}
	server := httptest.NewServer(registryapi.NewHandler(store))
	t.Cleanup(server.Close)

	tempDir := t.TempDir()
	outputDir := filepath.Join(tempDir, "generated")
	lockPath := filepath.Join(tempDir, "work-item-fronting.anip.lock.json")
	args := []string{
		"run", ".",
		"--registry-url", server.URL,
		"--package", "work-item-fronting@0.2.0",
		"--target", "typescript",
		"--dependency-source", "local",
		"--output", outputDir,
		"--write-lock", lockPath,
		"--force",
	}
	cmd := exec.Command("go", args...)
	cmd.Dir = wd
	cmd.Env = append(os.Environ(), "GOCACHE="+filepath.Join(t.TempDir(), "gocache"))

	out, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("go %v failed: %v\n%s", args, err, out)
	}

	var result struct {
		Status            string `json:"status"`
		Target            string `json:"target"`
		SourceKind        string `json:"source_kind"`
		PackageID         string `json:"package_id"`
		PackageVersion    string `json:"package_version"`
		LockDigest        string `json:"lock_digest"`
		RegistryTrusted   bool   `json:"registry_trusted"`
		WrittenLockFile   string `json:"written_lock_file"`
		WrittenLockDigest string `json:"written_lock_digest"`
		ReceiptAuthority  string `json:"receipt_authority"`
		ReceiptSignature  string `json:"receipt_signature"`
		PackageLifecycle  struct {
			Status string `json:"status"`
		} `json:"package_lifecycle"`
		PackageLifecycleWarning string         `json:"package_lifecycle_warning"`
		ProductRevision         map[string]any `json:"product_revision"`
		DeveloperRevision       map[string]any `json:"developer_revision"`
		FileCount               int            `json:"file_count"`
	}
	if err := json.Unmarshal(out, &result); err != nil {
		t.Fatalf("parse CLI JSON output: %v\n%s", err, out)
	}
	if result.Status != "ok" || result.Target != "typescript" || result.SourceKind != "registry" {
		t.Fatalf("unexpected CLI result: %+v", result)
	}
	if result.PackageID != "work-item-fronting" || result.PackageVersion != "0.2.0" || result.LockDigest == "" || !result.RegistryTrusted {
		t.Fatalf("unexpected registry metadata: %+v", result)
	}
	if result.WrittenLockFile != lockPath || result.WrittenLockDigest != result.LockDigest {
		t.Fatalf("expected written lock metadata, got %+v", result)
	}
	if result.ReceiptAuthority != "remote-registry" || result.ReceiptSignature == "" {
		t.Fatalf("expected registry receipt metadata, got %+v", result)
	}
	if result.PackageLifecycle.Status != registryapi.PackageLifecycleSuperseded || !strings.Contains(result.PackageLifecycleWarning, "work-item-fronting@0.2.1") {
		t.Fatalf("expected package lifecycle metadata, got %+v warning=%q", result.PackageLifecycle, result.PackageLifecycleWarning)
	}
	if result.ProductRevision["ref"] != "product-r3" || result.DeveloperRevision["ref"] != "developer-r5" {
		t.Fatalf("expected registry lineage metadata, got product=%+v developer=%+v", result.ProductRevision, result.DeveloperRevision)
	}
	if result.FileCount == 0 {
		t.Fatalf("expected generated files, got %+v", result)
	}
	if _, err := os.Stat(filepath.Join(outputDir, "src", "main.ts")); err != nil {
		t.Fatalf("expected generated TypeScript host: %v", err)
	}
	lockBytes, err := os.ReadFile(lockPath)
	if err != nil {
		t.Fatalf("expected written lock file: %v", err)
	}
	var lockPayload struct {
		RegistryURL      string `json:"registry_url"`
		PackageID        string `json:"package_id"`
		PackageVersion   string `json:"package_version"`
		DefinitionDigest string `json:"definition_digest"`
		LockDigest       string `json:"lock_digest"`
	}
	if err := json.Unmarshal(lockBytes, &lockPayload); err != nil {
		t.Fatalf("decode written lock: %v", err)
	}
	if lockPayload.RegistryURL == "" || lockPayload.PackageID != "work-item-fronting" || lockPayload.LockDigest != result.LockDigest {
		t.Fatalf("unexpected written lock payload: %+v", lockPayload)
	}

	lockedOutputDir := filepath.Join(tempDir, "generated-from-lock")
	lockArgs := []string{
		"run", ".",
		"--lock-file", lockPath,
		"--target", "typescript",
		"--dependency-source", "local",
		"--output", lockedOutputDir,
		"--force",
	}
	lockCmd := exec.Command("go", lockArgs...)
	lockCmd.Dir = wd
	lockCmd.Env = append(os.Environ(), "GOCACHE="+filepath.Join(t.TempDir(), "gocache"))
	if out, err := lockCmd.CombinedOutput(); err != nil {
		t.Fatalf("go %v failed: %v\n%s", lockArgs, err, out)
	}
	if _, err := os.Stat(filepath.Join(lockedOutputDir, "src", "main.ts")); err != nil {
		t.Fatalf("expected generated TypeScript host from lock: %v", err)
	}

	badLockPath := filepath.Join(tempDir, "bad.anip.lock.json")
	badLock := strings.Replace(string(lockBytes), result.LockDigest, "sha256:not-the-same-lock", 1)
	if err := os.WriteFile(badLockPath, []byte(badLock), 0o600); err != nil {
		t.Fatalf("write bad lock: %v", err)
	}
	badArgs := []string{
		"run", ".",
		"--lock-file", badLockPath,
		"--target", "typescript",
		"--dependency-source", "local",
		"--output", filepath.Join(tempDir, "bad-output"),
		"--force",
	}
	badCmd := exec.Command("go", badArgs...)
	badCmd.Dir = wd
	badCmd.Env = append(os.Environ(), "GOCACHE="+filepath.Join(t.TempDir(), "gocache"))
	badOut, err := badCmd.CombinedOutput()
	if err == nil || !strings.Contains(string(badOut), "lock mismatch for lock_digest") {
		t.Fatalf("expected lock digest mismatch, err=%v out=%s", err, badOut)
	}
}

func TestCLIGeneratesWithCustomCodeBundleAndContainerArtifacts(t *testing.T) {
	wd, err := os.Getwd()
	if err != nil {
		t.Fatalf("get working directory: %v", err)
	}
	tempDir := t.TempDir()
	bundleDir := filepath.Join(tempDir, "custom-bundle")
	bundleFile := filepath.Join(bundleDir, "src", "work_item_governance_service", "backend_adapter.py")
	if err := os.MkdirAll(filepath.Dir(bundleFile), 0o755); err != nil {
		t.Fatalf("create bundle dir: %v", err)
	}
	if err := os.WriteFile(bundleFile, []byte("# custom backend adapter\nCUSTOM_BACKEND = True\n"), 0o600); err != nil {
		t.Fatalf("write bundle file: %v", err)
	}
	customApp := filepath.Join(bundleDir, "src", "custom_work_item", "app.py")
	if err := os.MkdirAll(filepath.Dir(customApp), 0o755); err != nil {
		t.Fatalf("create custom app dir: %v", err)
	}
	if err := os.WriteFile(customApp, []byte("# custom app entrypoint\n"), 0o600); err != nil {
		t.Fatalf("write custom app: %v", err)
	}
	if err := os.WriteFile(filepath.Join(bundleDir, "pyproject.toml"), []byte("[project]\nname = \"custom-work-item\"\nversion = \"0.1.0\"\n"), 0o600); err != nil {
		t.Fatalf("write custom pyproject: %v", err)
	}

	outputDir := filepath.Join(tempDir, "generated")
	args := []string{
		"run", ".",
		"--definition", fixtureDefinitionPath(wd),
		"--target", "python",
		"--dependency-source", "local",
		"--output", outputDir,
		"--custom-code-bundle", bundleDir,
		"--dockerfile",
		"--docker-compose",
		"--force",
	}
	cmd := exec.Command("go", args...)
	cmd.Dir = wd
	cmd.Env = append(os.Environ(), "GOCACHE="+filepath.Join(t.TempDir(), "gocache"))

	out, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("go %v failed: %v\n%s", args, err, out)
	}

	var result struct {
		Status                 string `json:"status"`
		Target                 string `json:"target"`
		CustomCodeBundle       string `json:"custom_code_bundle"`
		CustomFilesApplied     int    `json:"custom_files_applied"`
		CustomCodeBundleReport struct {
			Files []struct {
				Path   string `json:"path"`
				SHA256 string `json:"sha256"`
				Seam   string `json:"seam"`
				Mode   string `json:"mode"`
			} `json:"files"`
		} `json:"custom_code_bundle_report"`
		Dockerfile    bool `json:"dockerfile"`
		DockerCompose bool `json:"docker_compose"`
	}
	if err := json.Unmarshal(out, &result); err != nil {
		t.Fatalf("parse CLI JSON output: %v\n%s", err, out)
	}
	if result.Status != "ok" || result.Target != "python" || result.CustomCodeBundle != bundleDir || result.CustomFilesApplied != 3 {
		t.Fatalf("unexpected custom bundle result: %+v", result)
	}
	if len(result.CustomCodeBundleReport.Files) != 3 {
		t.Fatalf("expected custom bundle provenance for 3 files, got %+v", result.CustomCodeBundleReport)
	}
	var foundAdapter bool
	for _, file := range result.CustomCodeBundleReport.Files {
		if !strings.HasPrefix(file.SHA256, "sha256:") {
			t.Fatalf("expected digest for custom file %+v", file)
		}
		if file.Path == "src/work_item_governance_service/backend_adapter.py" {
			foundAdapter = true
			if file.Seam != "backend_adapter" || file.Mode != "extension_overlay" {
				t.Fatalf("expected backend adapter extension overlay, got %+v", file)
			}
		}
	}
	if !foundAdapter {
		t.Fatalf("expected backend adapter provenance, got %+v", result.CustomCodeBundleReport)
	}
	if !result.Dockerfile || !result.DockerCompose {
		t.Fatalf("expected container artifact flags in result: %+v", result)
	}
	if _, err := os.Stat(filepath.Join(outputDir, "custom-code-bundle-report.json")); err != nil {
		t.Fatalf("expected custom bundle report file: %v", err)
	}
	adapterBytes, err := os.ReadFile(filepath.Join(outputDir, "src", "work_item_governance_service", "backend_adapter.py"))
	if err != nil {
		t.Fatalf("read overlaid backend adapter: %v", err)
	}
	if string(adapterBytes) != "# custom backend adapter\nCUSTOM_BACKEND = True\n" {
		t.Fatalf("custom bundle did not replace backend adapter: %s", adapterBytes)
	}
	if _, err := os.Stat(filepath.Join(outputDir, "Dockerfile")); err != nil {
		t.Fatalf("expected Dockerfile: %v", err)
	}
	if _, err := os.Stat(filepath.Join(outputDir, "src", "custom_work_item", "capabilities.py")); err != nil {
		t.Fatalf("expected generated support module in custom package: %v", err)
	}
	dockerfileBytes, err := os.ReadFile(filepath.Join(outputDir, "Dockerfile"))
	if err != nil {
		t.Fatalf("read Dockerfile: %v", err)
	}
	if !strings.Contains(string(dockerfileBytes), `CMD ["python", "-m", "custom_work_item.app"]`) {
		t.Fatalf("Dockerfile should use custom bundle app entrypoint: %s", dockerfileBytes)
	}
	if _, err := os.Stat(filepath.Join(outputDir, "docker-compose.yml")); err != nil {
		t.Fatalf("expected docker-compose.yml: %v", err)
	}
}

func TestCLIValidatesCustomCodeBundleRefsWithoutAutomaticFetch(t *testing.T) {
	wd, err := os.Getwd()
	if err != nil {
		t.Fatalf("get working directory: %v", err)
	}
	digest := "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
	validRef := "git+https://github.com/acme/anip-glue.git@0123456789abcdef0123456789abcdef01234567#sha256:" + digest
	outputDir := filepath.Join(t.TempDir(), "generated")
	args := []string{
		"run", ".",
		"--definition", fixtureDefinitionPath(wd),
		"--target", "python",
		"--dependency-source", "local",
		"--output", outputDir,
		"--custom-code-bundle-ref", validRef,
		"--force",
	}
	cmd := exec.Command("go", args...)
	cmd.Dir = wd
	cmd.Env = append(os.Environ(), "GOCACHE="+filepath.Join(t.TempDir(), "gocache"))

	out, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("go %v failed: %v\n%s", args, err, out)
	}
	var result struct {
		Status         string   `json:"status"`
		CustomRefs     []any    `json:"custom_code_bundle_refs"`
		CustomWarnings []string `json:"custom_code_bundle_warnings"`
	}
	if err := json.Unmarshal(out, &result); err != nil {
		t.Fatalf("parse CLI JSON output: %v\n%s", err, out)
	}
	if result.Status != "ok" || len(result.CustomRefs) != 1 || len(result.CustomWarnings) == 0 {
		t.Fatalf("expected metadata-only custom ref generation, got %+v", result)
	}
	if _, err := os.Stat(filepath.Join(outputDir, "src", "work_item_governance_service", "app.py")); err != nil {
		t.Fatalf("expected generated package despite metadata-only custom ref: %v", err)
	}
}

func TestCLIRejectsInvalidOrExplicitFetchCustomCodeBundleRefs(t *testing.T) {
	wd, err := os.Getwd()
	if err != nil {
		t.Fatalf("get working directory: %v", err)
	}
	digest := "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
	validRef := "git+https://github.com/acme/anip-glue.git@0123456789abcdef0123456789abcdef01234567#sha256:" + digest
	cases := []struct {
		name    string
		ref     string
		fetch   bool
		message string
	}{
		{
			name:    "valid but explicit remote fetch disabled",
			ref:     validRef,
			fetch:   true,
			message: "passed immutable reference validation, but remote bundle fetching is not enabled yet",
		},
		{
			name:    "invalid unpinned branch",
			ref:     "git+https://github.com/acme/anip-glue.git@main#sha256:" + digest,
			message: "invalid --custom-code-bundle-ref",
		},
		{
			name:    "invalid missing digest",
			ref:     "registry://acme/gtm-agent-glue@1.2.3",
			message: "must include a sha256 digest",
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			args := []string{
				"run", ".",
				"--definition", fixtureDefinitionPath(wd),
				"--target", "python",
				"--dependency-source", "local",
				"--output", filepath.Join(t.TempDir(), "generated"),
				"--custom-code-bundle-ref", tc.ref,
				"--force",
			}
			if tc.fetch {
				args = append(args, "--fetch-custom-code-bundle")
			}
			cmd := exec.Command("go", args...)
			cmd.Dir = wd
			cmd.Env = append(os.Environ(), "GOCACHE="+filepath.Join(t.TempDir(), "gocache"))

			out, err := cmd.CombinedOutput()
			if err == nil || !strings.Contains(string(out), tc.message) {
				t.Fatalf("expected failure containing %q, got err=%v\n%s", tc.message, err, out)
			}
		})
	}
}

func TestCLIRejectsLocalCustomBundleDigestMismatch(t *testing.T) {
	wd, err := os.Getwd()
	if err != nil {
		t.Fatalf("get working directory: %v", err)
	}
	bundleDir := t.TempDir()
	bundleFile := filepath.Join(bundleDir, "src", "work_item_governance_service", "backend_adapter.py")
	if err := os.MkdirAll(filepath.Dir(bundleFile), 0o755); err != nil {
		t.Fatalf("create bundle dir: %v", err)
	}
	if err := os.WriteFile(bundleFile, []byte("# custom backend adapter\n"), 0o600); err != nil {
		t.Fatalf("write bundle file: %v", err)
	}
	args := []string{
		"run", ".",
		"--definition", fixtureDefinitionPath(wd),
		"--target", "python",
		"--dependency-source", "local",
		"--output", filepath.Join(t.TempDir(), "generated"),
		"--custom-code-bundle", bundleDir,
		"--verify-custom-code-bundle-digest", "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
		"--force",
	}
	cmd := exec.Command("go", args...)
	cmd.Dir = wd
	cmd.Env = append(os.Environ(), "GOCACHE="+filepath.Join(t.TempDir(), "gocache"))

	out, err := cmd.CombinedOutput()
	if err == nil || !strings.Contains(string(out), "custom code bundle digest mismatch") {
		t.Fatalf("expected digest mismatch failure, got err=%v\n%s", err, out)
	}
}

func fixtureDefinitionPath(wd string) string {
	return filepath.Clean(filepath.Join(wd, "..", "..", "generator", "testdata", "work-item-fronting-definition.json"))
}

func stringSliceContains(values []string, expected string) bool {
	for _, value := range values {
		if value == expected {
			return true
		}
	}
	return false
}
