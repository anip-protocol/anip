package generator

import (
	"strings"
	"testing"
)

func TestBuildProjectsRejectUnsafeNamesAndPorts(t *testing.T) {
	definition := mustReadFixtureDefinition(t)
	cases := []struct {
		name    string
		build   func() (*GeneratedProject, error)
		message string
	}{
		{
			name: "typescript package script injection",
			build: func() (*GeneratedProject, error) {
				return BuildTypeScriptProject(definition, BuildTypeScriptProjectOptions{
					DependencySource: DependencySourceLocal,
					HttpRuntime:      HttpRuntimeHono,
					PackageName:      "ok;rm-rf",
					Port:             4100,
				})
			},
			message: "package name is invalid",
		},
		{
			name: "go module path traversal",
			build: func() (*GeneratedProject, error) {
				return BuildGoProject(definition, BuildGoProjectOptions{
					DependencySource: DependencySourceLocal,
					ModulePath:       "../escape",
					Port:             4100,
				})
			},
			message: "go module path is invalid",
		},
		{
			name: "python module path injection",
			build: func() (*GeneratedProject, error) {
				return BuildPythonProject(definition, BuildPythonProjectOptions{
					DependencySource: DependencySourceLocal,
					PackageName:      "bad/module",
					Port:             4100,
				})
			},
			message: "python module name is invalid",
		},
		{
			name: "java package shell injection",
			build: func() (*GeneratedProject, error) {
				return BuildJavaProject(definition, BuildJavaProjectOptions{
					DependencySource: DependencySourceLocal,
					ArtifactID:       "safe-artifact",
					PackageName:      "dev.anip.generated;rm",
					Port:             4100,
				})
			},
			message: "java package name is invalid",
		},
		{
			name: "java simple package shell injection",
			build: func() (*GeneratedProject, error) {
				return BuildJavaProject(definition, BuildJavaProjectOptions{
					DependencySource: DependencySourceLocal,
					ArtifactID:       "safe-artifact",
					PackageName:      "bad;rm",
					Port:             4100,
				})
			},
			message: "java package name is invalid",
		},
		{
			name: "csharp project generated filename injection",
			build: func() (*GeneratedProject, error) {
				return BuildCSharpProject(definition, BuildCSharpProjectOptions{
					DependencySource: DependencySourceLocal,
					ProjectName:      "../Escape",
					Port:             4100,
				})
			},
			message: "csharp project name is invalid",
		},
		{
			name: "invalid port",
			build: func() (*GeneratedProject, error) {
				return BuildPythonProject(definition, BuildPythonProjectOptions{
					DependencySource: DependencySourceLocal,
					Port:             70000,
				})
			},
			message: "port must be between",
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			_, err := tc.build()
			if err == nil || !strings.Contains(err.Error(), tc.message) {
				t.Fatalf("expected %q, got %v", tc.message, err)
			}
		})
	}
}

func TestBuildContainerArtifactsRejectsUnsafePort(t *testing.T) {
	project := &GeneratedProject{
		PackageName: "safe",
		SystemName:  "safe",
		Files: []GeneratedFile{
			{Path: "src/safe/app.py", Content: ""},
		},
	}

	if _, err := BuildContainerArtifacts("python", project, ContainerArtifactOptions{Dockerfile: true, Port: -1}); err == nil || !strings.Contains(err.Error(), "port must be between") {
		t.Fatalf("expected invalid port rejection, got %v", err)
	}
}

func TestValidateCustomCodeBundleRefAcceptsPinnedImmutableRefs(t *testing.T) {
	digest := "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
	cases := []struct {
		name string
		ref  string
		kind string
	}{
		{
			name: "git commit",
			ref:  "git+https://github.com/acme/anip-glue.git@0123456789abcdef0123456789abcdef01234567#sha256:" + digest,
			kind: "git",
		},
		{
			name: "registry artifact",
			ref:  "registry://acme/gtm-agent-glue@1.2.3#sha256:" + digest,
			kind: "registry",
		},
		{
			name: "https object",
			ref:  "object+https://artifacts.example.com/anip/gtm-agent-glue-1.2.3.tgz#sha256:" + digest,
			kind: "object+https",
		},
		{
			name: "s3 object",
			ref:  "object+s3://anip-artifacts/gtm/agent-glue-1.2.3.tgz#sha256:" + digest,
			kind: "object+s3",
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			parsed, err := ValidateCustomCodeBundleRef(tc.ref)
			if err != nil {
				t.Fatalf("ValidateCustomCodeBundleRef: %v", err)
			}
			if parsed.Kind != tc.kind || parsed.Digest != "sha256:"+digest {
				t.Fatalf("unexpected parsed ref: %+v", parsed)
			}
		})
	}
}

func TestValidateCustomCodeBundleRefRejectsUnsafeOrFloatingRefs(t *testing.T) {
	digest := "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
	cases := []struct {
		name    string
		ref     string
		message string
	}{
		{
			name:    "missing digest",
			ref:     "git+https://github.com/acme/anip-glue.git@0123456789abcdef0123456789abcdef01234567",
			message: "sha256 digest",
		},
		{
			name:    "git branch",
			ref:     "git+https://github.com/acme/anip-glue.git@main#sha256:" + digest,
			message: "commit hash",
		},
		{
			name:    "git credentials",
			ref:     "git+https://token@github.com/acme/anip-glue.git@0123456789abcdef0123456789abcdef01234567#sha256:" + digest,
			message: "credentials",
		},
		{
			name:    "registry latest",
			ref:     "registry://acme/gtm-agent-glue@latest#sha256:" + digest,
			message: "immutable version",
		},
		{
			name:    "path traversal",
			ref:     "object+https://artifacts.example.com/anip/../secret.tgz#sha256:" + digest,
			message: "path traversal",
		},
		{
			name:    "object query",
			ref:     "object+https://artifacts.example.com/anip/glue.tgz?token=secret#sha256:" + digest,
			message: "query",
		},
		{
			name:    "unsupported scheme",
			ref:     "https://artifacts.example.com/anip/glue.tgz#sha256:" + digest,
			message: "scheme",
		},
		{
			name:    "unsafe character",
			ref:     "registry://acme/glue;rm@1.2.3#sha256:" + digest,
			message: "invalid",
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			_, err := ValidateCustomCodeBundleRef(tc.ref)
			if err == nil || !strings.Contains(err.Error(), tc.message) {
				t.Fatalf("expected %q, got %v", tc.message, err)
			}
		})
	}
}

func TestCustomCodeBundleMaterialsFromMetadataValidatesPackageRefs(t *testing.T) {
	digest := "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
	treeDigest := "sha256:abcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcd"
	manifest := map[string]any{
		"implementation_material": map[string]any{
			"custom_code_bundles": []any{
				map[string]any{
					"title":              "Reviewed app glue",
					"ref":                "registry://acme/gtm-agent-glue@1.2.3#sha256:" + digest,
					"bundle_tree_sha256": treeDigest,
				},
			},
		},
	}

	materials, err := CustomCodeBundleMaterialsFromMetadata(manifest, nil)
	if err != nil {
		t.Fatalf("CustomCodeBundleMaterialsFromMetadata: %v", err)
	}
	if len(materials) != 1 {
		t.Fatalf("expected one material ref, got %+v", materials)
	}
	if materials[0].Kind != "registry" || materials[0].BundleTreeSHA256 != treeDigest || materials[0].Source == "" {
		t.Fatalf("unexpected material: %+v", materials[0])
	}
}

func TestCustomCodeBundleMaterialsFromMetadataRejectsUnsafeRefs(t *testing.T) {
	manifest := map[string]any{
		"custom_code_bundle_refs": []any{
			"git+https://github.com/acme/anip-glue.git@main#sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
		},
	}

	_, err := CustomCodeBundleMaterialsFromMetadata(manifest, nil)
	if err == nil || !strings.Contains(err.Error(), "invalid custom code bundle metadata") {
		t.Fatalf("expected invalid package metadata rejection, got %v", err)
	}
}
