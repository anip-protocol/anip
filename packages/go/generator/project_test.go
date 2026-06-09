package generator

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestApplyCustomCodeBundleEmptyPathIsNoop(t *testing.T) {
	project := &GeneratedProject{
		PackageName: "test",
		SystemName:  "test",
		Files: []GeneratedFile{
			{Path: "README.md", Content: "generated"},
		},
	}

	applied, err := ApplyCustomCodeBundle(project, "")
	if err != nil {
		t.Fatalf("ApplyCustomCodeBundle: %v", err)
	}
	if applied != 0 {
		t.Fatalf("expected no custom files, got %d", applied)
	}
	if len(project.Files) != 1 {
		t.Fatalf("empty bundle path should not change generated files, got %d", len(project.Files))
	}
}

func TestApplyCustomCodeBundleRejectsCapabilityIDsOutsideContract(t *testing.T) {
	project := &GeneratedProject{
		PackageName: "test",
		SystemName:  "test",
		Services: []GeneratedServiceMetadata{
			{
				ServiceID:               "pipeline-service",
				FormalizedCapabilityIDs: []string{"pipeline.summary"},
			},
		},
		Files: []GeneratedFile{
			{Path: "README.md", Content: "generated"},
		},
	}
	bundleDir := t.TempDir()
	appPath := filepath.Join(bundleDir, "src", "custom_service", "app.py")
	if err := os.MkdirAll(filepath.Dir(appPath), 0o755); err != nil {
		t.Fatalf("create bundle dir: %v", err)
	}
	if err := os.WriteFile(appPath, []byte(`CapabilityDeclaration(name="gtm.pipeline_summary")`), 0o600); err != nil {
		t.Fatalf("write bundle file: %v", err)
	}

	_, err := ApplyCustomCodeBundle(project, bundleDir)
	if err == nil {
		t.Fatal("expected custom bundle capability mismatch error")
	}
	if !strings.Contains(err.Error(), "gtm.pipeline_summary") || !strings.Contains(err.Error(), "not present in the service definition") {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestApplyCustomCodeBundleRejectsUnderscoreCapabilityIDsOutsideContract(t *testing.T) {
	project := &GeneratedProject{
		PackageName: "test",
		SystemName:  "test",
		Services: []GeneratedServiceMetadata{
			{
				ServiceID:               "pipeline-service",
				FormalizedCapabilityIDs: []string{"pipeline.summary"},
			},
		},
		Files: []GeneratedFile{
			{Path: "README.md", Content: "generated"},
		},
	}
	bundleDir := t.TempDir()
	appPath := filepath.Join(bundleDir, "src", "custom_service", "app.py")
	if err := os.MkdirAll(filepath.Dir(appPath), 0o755); err != nil {
		t.Fatalf("create bundle dir: %v", err)
	}
	if err := os.WriteFile(appPath, []byte(`CapabilityDeclaration(name="gtm.prioritized_outreach_draft")`), 0o600); err != nil {
		t.Fatalf("write bundle file: %v", err)
	}

	_, err := ApplyCustomCodeBundle(project, bundleDir)
	if err == nil {
		t.Fatal("expected custom bundle capability mismatch error")
	}
	if !strings.Contains(err.Error(), "gtm.prioritized_outreach_draft") {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestApplyCustomCodeBundleIgnoresCapabilityInputNames(t *testing.T) {
	project := &GeneratedProject{
		PackageName: "test",
		SystemName:  "test",
		Services: []GeneratedServiceMetadata{
			{
				ServiceID:               "pipeline-service",
				FormalizedCapabilityIDs: []string{"pipeline.summary"},
			},
		},
		Files: []GeneratedFile{
			{Path: "README.md", Content: "generated"},
		},
	}
	bundleDir := t.TempDir()
	appPath := filepath.Join(bundleDir, "src", "custom_service", "app.py")
	if err := os.MkdirAll(filepath.Dir(appPath), 0o755); err != nil {
		t.Fatalf("create bundle dir: %v", err)
	}
	source := `
CapabilityDeclaration(
    name="pipeline.summary",
    inputs=[
        CapabilityInput(name="target_ref", type="string"),
        CapabilityInput(name="context.scope", type="string"),
    ],
)
`
	if err := os.WriteFile(appPath, []byte(source), 0o600); err != nil {
		t.Fatalf("write bundle file: %v", err)
	}

	if _, err := ApplyCustomCodeBundle(project, bundleDir); err != nil {
		t.Fatalf("ApplyCustomCodeBundle should ignore CapabilityInput names: %v", err)
	}
}

func TestApplyCustomCodeBundleAllowsMatchingCapabilityIDs(t *testing.T) {
	project := &GeneratedProject{
		PackageName: "test",
		SystemName:  "test",
		Services: []GeneratedServiceMetadata{
			{
				ServiceID:               "pipeline-service",
				FormalizedCapabilityIDs: []string{"pipeline.summary"},
			},
		},
		Files: []GeneratedFile{
			{Path: "README.md", Content: "generated"},
		},
	}
	bundleDir := t.TempDir()
	appPath := filepath.Join(bundleDir, "src", "custom_service", "app.py")
	if err := os.MkdirAll(filepath.Dir(appPath), 0o755); err != nil {
		t.Fatalf("create bundle dir: %v", err)
	}
	if err := os.WriteFile(appPath, []byte(`CapabilityDeclaration(name="pipeline.summary")`), 0o600); err != nil {
		t.Fatalf("write bundle file: %v", err)
	}

	applied, err := ApplyCustomCodeBundle(project, bundleDir)
	if err != nil {
		t.Fatalf("ApplyCustomCodeBundle: %v", err)
	}
	if applied != 1 {
		t.Fatalf("expected one custom file, got %d", applied)
	}
}

func TestApplyCustomCodeBundleReportsStableTreeDigest(t *testing.T) {
	project := &GeneratedProject{
		PackageName: "test",
		SystemName:  "test",
		Files: []GeneratedFile{
			{Path: "README.md", Content: "generated"},
		},
	}
	bundleDir := t.TempDir()
	if err := os.WriteFile(filepath.Join(bundleDir, "README.md"), []byte("custom readme"), 0o600); err != nil {
		t.Fatalf("write bundle file: %v", err)
	}

	first, err := ApplyCustomCodeBundleWithReport(project, bundleDir)
	if err != nil {
		t.Fatalf("ApplyCustomCodeBundleWithReport: %v", err)
	}
	if first.BundleSHA256 == "" || !strings.HasPrefix(first.BundleSHA256, "sha256:") {
		t.Fatalf("expected bundle tree digest, got %+v", first)
	}

	projectAgain := &GeneratedProject{
		PackageName: "test",
		SystemName:  "test",
		Files: []GeneratedFile{
			{Path: "README.md", Content: "generated"},
		},
	}
	second, err := ApplyCustomCodeBundleWithReport(projectAgain, bundleDir)
	if err != nil {
		t.Fatalf("ApplyCustomCodeBundleWithReport again: %v", err)
	}
	if first.BundleSHA256 != second.BundleSHA256 {
		t.Fatalf("expected stable tree digest, first=%s second=%s", first.BundleSHA256, second.BundleSHA256)
	}
}

func TestComputeCustomCodeBundleTreeDigestMatchesAppliedDigest(t *testing.T) {
	project := &GeneratedProject{
		PackageName: "test",
		SystemName:  "test",
		Files: []GeneratedFile{
			{Path: "README.md", Content: "generated"},
		},
	}
	bundleDir := t.TempDir()
	if err := os.WriteFile(filepath.Join(bundleDir, "README.md"), []byte("custom readme"), 0o600); err != nil {
		t.Fatalf("write bundle file: %v", err)
	}
	if err := os.WriteFile(filepath.Join(bundleDir, "notes.txt"), []byte("not applied"), 0o600); err != nil {
		t.Fatalf("write ignored file: %v", err)
	}
	cacheDir := filepath.Join(bundleDir, "__pycache__")
	if err := os.Mkdir(cacheDir, 0o700); err != nil {
		t.Fatalf("create cache dir: %v", err)
	}
	if err := os.WriteFile(filepath.Join(cacheDir, "app.cpython-311.pyc"), []byte("ignored bytecode"), 0o600); err != nil {
		t.Fatalf("write ignored bytecode: %v", err)
	}

	applied, err := ApplyCustomCodeBundleWithReport(project, bundleDir)
	if err != nil {
		t.Fatalf("ApplyCustomCodeBundleWithReport: %v", err)
	}
	computed, err := ComputeCustomCodeBundleTreeDigest(bundleDir)
	if err != nil {
		t.Fatalf("ComputeCustomCodeBundleTreeDigest: %v", err)
	}
	if computed != applied.BundleSHA256 {
		t.Fatalf("expected digest parity, computed=%s applied=%s", computed, applied.BundleSHA256)
	}
}

func TestWriteGeneratedProjectRejectsPathTraversal(t *testing.T) {
	project := &GeneratedProject{
		PackageName: "test",
		SystemName:  "test",
		Files: []GeneratedFile{
			{Path: "../escape.txt", Content: "unsafe"},
		},
	}

	if err := WriteGeneratedProject(project, filepath.Join(t.TempDir(), "out"), false); err == nil || !strings.Contains(err.Error(), "escapes output directory") {
		t.Fatalf("expected path traversal rejection, got %v", err)
	}
}

func TestApplyCustomCodeBundleRejectsGeneratedContractOverride(t *testing.T) {
	project := &GeneratedProject{
		PackageName: "test",
		SystemName:  "test",
		Files: []GeneratedFile{
			{Path: "anip-service-definition.json", Content: "{}"},
		},
	}
	bundleDir := t.TempDir()
	if err := os.WriteFile(filepath.Join(bundleDir, "anip-service-definition.json"), []byte("{}"), 0o600); err != nil {
		t.Fatalf("write bundle file: %v", err)
	}

	if _, err := ApplyCustomCodeBundle(project, bundleDir); err == nil || !strings.Contains(err.Error(), "generated substrate") {
		t.Fatalf("expected generated substrate rejection, got %v", err)
	}
}

func TestApplyCustomCodeBundleRejectsGeneratedCapabilitiesOverride(t *testing.T) {
	project := &GeneratedProject{
		PackageName: "test",
		SystemName:  "test",
		Files: []GeneratedFile{
			{Path: "src/test_service/capabilities.py", Content: "generated"},
		},
	}
	bundleDir := t.TempDir()
	bundlePath := filepath.Join(bundleDir, "src", "test_service", "capabilities.py")
	if err := os.MkdirAll(filepath.Dir(bundlePath), 0o755); err != nil {
		t.Fatalf("create bundle dir: %v", err)
	}
	if err := os.WriteFile(bundlePath, []byte("custom"), 0o600); err != nil {
		t.Fatalf("write bundle file: %v", err)
	}

	if _, err := ApplyCustomCodeBundle(project, bundleDir); err == nil || !strings.Contains(err.Error(), "generated substrate") {
		t.Fatalf("expected generated substrate rejection, got %v", err)
	}
}

func TestApplyCustomCodeBundleAllowsBackendAdapterExtensionSeam(t *testing.T) {
	project := &GeneratedProject{
		PackageName: "test",
		SystemName:  "test",
		Files: []GeneratedFile{
			{Path: "src/test_service/backend_adapter.py", Content: "generated"},
		},
	}
	bundleDir := t.TempDir()
	bundlePath := filepath.Join(bundleDir, "src", "test_service", "backend_adapter.py")
	if err := os.MkdirAll(filepath.Dir(bundlePath), 0o755); err != nil {
		t.Fatalf("create bundle dir: %v", err)
	}
	if err := os.WriteFile(bundlePath, []byte("custom"), 0o600); err != nil {
		t.Fatalf("write bundle file: %v", err)
	}

	applied, err := ApplyCustomCodeBundle(project, bundleDir)
	if err != nil {
		t.Fatalf("ApplyCustomCodeBundle: %v", err)
	}
	if applied != 1 || project.Files[0].Content != "custom" {
		t.Fatalf("expected backend adapter overlay, applied=%d file=%+v", applied, project.Files[0])
	}
}

func TestApplyCustomCodeBundleRemapsPythonBackendAdapterToGeneratedModule(t *testing.T) {
	project := &GeneratedProject{
		PackageName: "test",
		SystemName:  "test",
		CustomBundleTemplateValues: map[string]string{
			"PYTHON_MODULE_NAME": "generated_jira",
		},
		Files: []GeneratedFile{
			{Path: "src/generated_jira/backend_adapter.py", Content: "generated"},
		},
	}
	bundleDir := t.TempDir()
	bundlePath := filepath.Join(bundleDir, "src", "historical_jira", "backend_adapter.py")
	if err := os.MkdirAll(filepath.Dir(bundlePath), 0o755); err != nil {
		t.Fatalf("create bundle dir: %v", err)
	}
	if err := os.WriteFile(bundlePath, []byte("custom"), 0o600); err != nil {
		t.Fatalf("write bundle file: %v", err)
	}

	applied, err := ApplyCustomCodeBundle(project, bundleDir)
	if err != nil {
		t.Fatalf("ApplyCustomCodeBundle: %v", err)
	}
	if applied != 1 {
		t.Fatalf("expected one custom file applied, got %d", applied)
	}
	if content, ok := generatedProjectFileContent(project, "src/generated_jira/backend_adapter.py"); !ok || content != "custom" {
		t.Fatalf("expected backend adapter remapped into generated module, got ok=%v content=%q", ok, content)
	}
	if _, ok := generatedProjectFileContent(project, "src/historical_jira/backend_adapter.py"); ok {
		t.Fatalf("did not expect stale historical module backend adapter to remain")
	}
}

func TestApplyCustomCodeBundleRemapsPythonPackageRuntimeToGeneratedModule(t *testing.T) {
	project := &GeneratedProject{
		PackageName: "test",
		SystemName:  "test",
		CustomBundleTemplateValues: map[string]string{
			"PYTHON_MODULE_NAME": "generated_gtm",
		},
		Files: []GeneratedFile{
			{Path: "src/generated_gtm/backend_adapter.py", Content: "generated"},
		},
	}
	bundleDir := t.TempDir()
	files := map[string]string{
		"src/historical_gtm/backend_adapter.py":     "custom adapter",
		"src/historical_gtm/app.py":                 "custom app",
		"src/historical_gtm/runtime/actor.py":       "custom actor",
		"src/historical_gtm/services/search/app.py": "custom service",
		"src/shared/actor_identity.py":              "shared helper",
	}
	for name, content := range files {
		bundlePath := filepath.Join(bundleDir, filepath.FromSlash(name))
		if err := os.MkdirAll(filepath.Dir(bundlePath), 0o755); err != nil {
			t.Fatalf("create bundle dir: %v", err)
		}
		if err := os.WriteFile(bundlePath, []byte(content), 0o600); err != nil {
			t.Fatalf("write bundle file: %v", err)
		}
	}

	_, err := ApplyCustomCodeBundle(project, bundleDir)
	if err != nil {
		t.Fatalf("ApplyCustomCodeBundle: %v", err)
	}
	for path, expected := range map[string]string{
		"src/generated_gtm/backend_adapter.py":     "custom adapter",
		"src/generated_gtm/runtime/actor.py":       "custom actor",
		"src/generated_gtm/services/search/app.py": "custom service",
		"src/historical_gtm/app.py":                "custom app",
		"src/shared/actor_identity.py":             "shared helper",
	} {
		if content, ok := generatedProjectFileContent(project, path); !ok || content != expected {
			t.Fatalf("expected %s to contain %q, got ok=%v content=%q", path, expected, ok, content)
		}
	}
	if _, ok := generatedProjectFileContent(project, "src/historical_gtm/runtime/actor.py"); ok {
		t.Fatalf("did not expect stale historical runtime module to remain")
	}
}

func TestApplyCustomCodeBundleRemapsTemplatedJavaPackagePaths(t *testing.T) {
	project := &GeneratedProject{
		PackageName: "test",
		SystemName:  "test",
		CustomBundleTemplateValues: map[string]string{
			"JAVA_PACKAGE_NAME": "dev.anip.generated.demo",
			"JAVA_PACKAGE_PATH": "dev/anip/generated/demo",
		},
		Files: []GeneratedFile{
			{Path: "src/main/java/dev/anip/generated/demo/BackendAdapter.java", Content: "generated adapter"},
			{Path: "src/main/java/dev/anip/generated/demo/Policy.java", Content: "generated policy"},
		},
	}
	bundleDir := t.TempDir()
	oldBase := filepath.Join(bundleDir, "src", "main", "java", "com", "example", "old")
	if err := os.MkdirAll(oldBase, 0o755); err != nil {
		t.Fatalf("create bundle dir: %v", err)
	}
	if err := os.WriteFile(filepath.Join(oldBase, "BackendAdapter.java"), []byte("package {{ANIP_JAVA_PACKAGE_NAME}};\npublic interface BackendAdapter {}\n"), 0o600); err != nil {
		t.Fatalf("write backend adapter: %v", err)
	}
	if err := os.WriteFile(filepath.Join(oldBase, "Policy.java"), []byte("package {{ANIP_JAVA_PACKAGE_NAME}};\npublic final class Policy {}\n"), 0o600); err != nil {
		t.Fatalf("write policy: %v", err)
	}
	if err := os.WriteFile(filepath.Join(oldBase, "GtmApprovalController.java"), []byte("package {{ANIP_JAVA_PACKAGE_NAME}};\npublic final class GtmApprovalController {}\n"), 0o600); err != nil {
		t.Fatalf("write approval controller: %v", err)
	}

	report, err := ApplyCustomCodeBundleWithReport(project, bundleDir)
	if err != nil {
		t.Fatalf("ApplyCustomCodeBundleWithReport: %v", err)
	}

	expectedAdapterPath := "src/main/java/dev/anip/generated/demo/BackendAdapter.java"
	expectedPolicyPath := "src/main/java/dev/anip/generated/demo/Policy.java"
	expectedControllerPath := "src/main/java/dev/anip/generated/demo/GtmApprovalController.java"
	for _, expectedPath := range []string{expectedAdapterPath, expectedPolicyPath, expectedControllerPath} {
		content, ok := generatedProjectFileContent(project, expectedPath)
		if !ok {
			t.Fatalf("expected remapped generated file %s", expectedPath)
		}
		if !strings.Contains(content, "package dev.anip.generated.demo;") {
			t.Fatalf("expected Java package template substitution in %s, content=%q", expectedPath, content)
		}
	}
	if _, ok := generatedProjectFileContent(project, "src/main/java/com/example/old/BackendAdapter.java"); ok {
		t.Fatal("expected old Java custom bundle path not to be emitted")
	}
	reportPaths := map[string]bool{}
	for _, file := range report.Files {
		reportPaths[file.Path] = true
	}
	for _, expectedPath := range []string{expectedAdapterPath, expectedPolicyPath, expectedControllerPath} {
		if !reportPaths[expectedPath] {
			t.Fatalf("expected remapped report path %s in %+v", expectedPath, report.Files)
		}
	}
}

func TestApplyCustomCodeBundleRejectsGeneratedEntrypointOverrideAcrossTargets(t *testing.T) {
	entrypoints := []string{
		"src/generated_service/app.py",
		"src/main.ts",
		"main.go",
		"src/main/java/dev/anip/generated/service/Application.java",
		"Program.cs",
	}
	for _, entrypoint := range entrypoints {
		t.Run(entrypoint, func(t *testing.T) {
			project := &GeneratedProject{
				PackageName: "test",
				SystemName:  "test",
				Files: []GeneratedFile{
					{Path: entrypoint, Content: "generated entrypoint"},
				},
			}
			bundleDir := t.TempDir()
			bundlePath := filepath.Join(append([]string{bundleDir}, strings.Split(entrypoint, "/")...)...)
			if err := os.MkdirAll(filepath.Dir(bundlePath), 0o755); err != nil {
				t.Fatalf("create bundle dir: %v", err)
			}
			if err := os.WriteFile(bundlePath, []byte("custom entrypoint"), 0o600); err != nil {
				t.Fatalf("write bundle file: %v", err)
			}

			if _, err := ApplyCustomCodeBundle(project, bundleDir); err == nil || !strings.Contains(err.Error(), "generated substrate") {
				t.Fatalf("expected generated entrypoint override rejection, got %v", err)
			}
		})
	}
}

func TestApplyCustomCodeBundleAllowsAdditionalCustomEntrypointMaterial(t *testing.T) {
	project := &GeneratedProject{
		PackageName: "test",
		SystemName:  "test",
		Files: []GeneratedFile{
			{Path: "src/generated_service/app.py", Content: "generated entrypoint"},
		},
	}
	bundleDir := t.TempDir()
	bundlePath := filepath.Join(bundleDir, "src", "custom_service", "app.py")
	if err := os.MkdirAll(filepath.Dir(bundlePath), 0o755); err != nil {
		t.Fatalf("create bundle dir: %v", err)
	}
	if err := os.WriteFile(bundlePath, []byte("custom alternate entrypoint"), 0o600); err != nil {
		t.Fatalf("write bundle file: %v", err)
	}

	applied, err := ApplyCustomCodeBundle(project, bundleDir)
	if err != nil {
		t.Fatalf("ApplyCustomCodeBundle: %v", err)
	}
	if applied != 1 {
		t.Fatalf("expected custom entrypoint material to be added, got %d", applied)
	}
	if content, ok := generatedProjectFileContent(project, "src/generated_service/app.py"); !ok || content != "generated entrypoint" {
		t.Fatalf("expected generated entrypoint to remain unchanged, ok=%v content=%q", ok, content)
	}
	if content, ok := generatedProjectFileContent(project, "src/custom_service/app.py"); !ok || content != "custom alternate entrypoint" {
		t.Fatalf("expected custom entrypoint material to be added, ok=%v content=%q", ok, content)
	}
}

func TestApplyCustomCodeBundleRejectsCaseVariantGeneratedPathOverride(t *testing.T) {
	project := &GeneratedProject{
		PackageName: "test",
		SystemName:  "test",
		Files: []GeneratedFile{
			{Path: "src/main.ts", Content: "generated entrypoint"},
		},
	}
	bundleDir := t.TempDir()
	bundlePath := filepath.Join(bundleDir, "Src", "Main.ts")
	if err := os.MkdirAll(filepath.Dir(bundlePath), 0o755); err != nil {
		t.Fatalf("create bundle dir: %v", err)
	}
	if err := os.WriteFile(bundlePath, []byte("custom entrypoint"), 0o600); err != nil {
		t.Fatalf("write bundle file: %v", err)
	}

	if _, err := ApplyCustomCodeBundle(project, bundleDir); err == nil || !strings.Contains(err.Error(), "generated substrate") {
		t.Fatalf("expected case-variant generated path override rejection, got %v", err)
	}
}

func TestEnsurePythonCustomModuleSupportCopiesGeneratedServiceEntrypoints(t *testing.T) {
	project := &GeneratedProject{
		PackageName: "test",
		SystemName:  "test",
		Files: []GeneratedFile{
			{Path: "pyproject.toml", Content: "[project]\nname = \"custom-work-item\"\n"},
			{Path: "src/generated_work_item/runtime_target.py", Content: "runtime"},
			{Path: "src/generated_work_item/backend_adapter.py", Content: "adapter"},
			{Path: "src/generated_work_item/services/search_service/app.py", Content: "generated search app"},
			{Path: "src/generated_work_item/services/write_service/app.py", Content: "generated write app"},
			{Path: "src/custom_work_item/services/write_service/app.py", Content: "custom write app"},
		},
	}

	copied := EnsurePythonCustomModuleSupport(project)

	if copied != 3 {
		t.Fatalf("expected runtime support plus one missing service to be copied, got %d", copied)
	}
	if content, ok := generatedProjectFileContent(project, "src/custom_work_item/backend_adapter.py"); !ok || content != "adapter" {
		t.Fatalf("expected backend adapter copied into custom module, got ok=%v content=%q", ok, content)
	}
	if content, ok := generatedProjectFileContent(project, "src/custom_work_item/services/search_service/app.py"); !ok || content != "generated search app" {
		t.Fatalf("expected generated service copied into custom module, got ok=%v content=%q", ok, content)
	}
	if content, ok := generatedProjectFileContent(project, "src/custom_work_item/services/write_service/app.py"); !ok || content != "custom write app" {
		t.Fatalf("expected custom service app not to be overwritten, got ok=%v content=%q", ok, content)
	}
}

func TestApplyCustomCodeBundleRejectsSymlink(t *testing.T) {
	project := &GeneratedProject{
		PackageName: "test",
		SystemName:  "test",
		Files: []GeneratedFile{
			{Path: "README.md", Content: "generated"},
		},
	}
	bundleDir := t.TempDir()
	target := filepath.Join(t.TempDir(), "outside.py")
	if err := os.WriteFile(target, []byte("print('outside')"), 0o600); err != nil {
		t.Fatalf("write target: %v", err)
	}
	link := filepath.Join(bundleDir, "outside.py")
	if err := os.Symlink(target, link); err != nil {
		t.Skipf("symlink unavailable: %v", err)
	}

	if _, err := ApplyCustomCodeBundle(project, bundleDir); err == nil || !strings.Contains(err.Error(), "symlinks") {
		t.Fatalf("expected symlink rejection, got %v", err)
	}
}
