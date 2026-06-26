package generate

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"os"
	"strings"

	"github.com/anip-protocol/anip/packages/go/generator"
)

type cliError struct {
	message string
}

var errorWriter io.Writer = os.Stderr

func Run(args []string, stdout io.Writer, stderr io.Writer) (exitCode int) {
	if stdout == nil {
		stdout = os.Stdout
	}
	if stderr == nil {
		stderr = os.Stderr
	}
	errorWriter = stderr
	defer func() {
		if recovered := recover(); recovered != nil {
			if err, ok := recovered.(cliError); ok {
				fmt.Fprintln(stderr, err.message)
				exitCode = 1
				return
			}
			panic(recovered)
		}
	}()

	var definitionPath string
	var packageBundle string
	var registryBase string
	var registryURL string
	var packageID string
	var packageVersion string
	var packageRef string
	var lockFile string
	var writeLock string
	var target string
	var outputPath string
	var force bool
	var customCodeBundle string
	var customCodeBundleRef string
	var fetchCustomCodeBundle bool
	var verifyCustomCodeBundleDigest string
	var includeDockerfile bool
	var includeDockerCompose bool
	var dependencySource string
	var framework string
	var transportList string
	var packageName string
	var port int

	fs := flag.NewFlagSet("anip generate", flag.ContinueOnError)
	if hasHelpFlag(args) {
		fs.SetOutput(stdout)
	} else {
		fs.SetOutput(stderr)
	}
	fs.Usage = func() {
		writer := fs.Output()
		fmt.Fprintln(writer, `Usage:
  anip generate --definition <file> --target <language> --output <dir> [flags]
  anip generate --package-bundle <bundle> --target <language> --output <dir> [flags]
  anip generate --registry-url <url> --package <id@version> --target <language> --output <dir> [flags]
  anip generate --definition <file> --output <resolved-definition.json>

Targets:
  typescript, go, python, java, csharp

Framework variants:
  typescript: hono (default), express, fastify
  java: spring-boot (default), quarkus

Compatibility:
  anip-generate [flags] runs the same command.

Flags:`)
		fs.PrintDefaults()
	}
	fs.StringVar(&definitionPath, "definition", "", "Path to a local anip-service-definition.json")
	fs.StringVar(&packageBundle, "package-bundle", "", "Path to a portable .anip-package.json bundle")
	fs.StringVar(&registryBase, "registry-base", "", "Base URL of the ANIP Registry service")
	fs.StringVar(&registryURL, "registry-url", "", "Base URL of the ANIP Registry service")
	fs.StringVar(&packageID, "package-id", "", "Registry package id")
	fs.StringVar(&packageVersion, "package-version", "", "Registry package version")
	fs.StringVar(&packageRef, "package", "", "Registry package reference as package_id@package_version")
	fs.StringVar(&lockFile, "lock-file", "", "Path to an anip package lock file to enforce during resolution")
	fs.StringVar(&writeLock, "write-lock", "", "Write an anip package lock file for the resolved registry/package bundle")
	fs.StringVar(&target, "target", "", "Generation target language (currently: typescript, go, python, java, csharp)")
	fs.StringVar(&outputPath, "output", "", "Destination file path or generated project directory")
	fs.BoolVar(&force, "force", false, "Overwrite an existing output directory")
	fs.StringVar(&customCodeBundle, "custom-code-bundle", "", "Directory of custom files to overlay onto the generated project")
	fs.StringVar(&customCodeBundleRef, "custom-code-bundle-ref", "", "Immutable custom bundle reference. Validated by default; fetched only with --fetch-custom-code-bundle.")
	fs.BoolVar(&fetchCustomCodeBundle, "fetch-custom-code-bundle", false, "Explicitly fetch and apply --custom-code-bundle-ref. Reserved; remote fetching is not enabled yet.")
	fs.StringVar(&verifyCustomCodeBundleDigest, "verify-custom-code-bundle-digest", "", "Expected sha256 digest for the normalized local custom bundle tree.")
	fs.BoolVar(&includeDockerfile, "dockerfile", false, "Include a target-specific Dockerfile when generating a project")
	fs.BoolVar(&includeDockerCompose, "docker-compose", false, "Include a local single-service docker-compose.yml when generating a project")
	fs.StringVar(&dependencySource, "dependency-source", string(generator.DependencySourceRegistry), "Dependency source for generated projects: registry or local")
	fs.StringVar(&framework, "framework", "", "Target framework variant. For typescript: hono, express, fastify. For java: spring-boot or quarkus.")
	fs.StringVar(&transportList, "transport", string(generator.TransportHTTP), "Generated transport runner(s). HTTP host is included by default; use stdio or http,stdio to add a local stdio runner.")
	fs.StringVar(&packageName, "package-name", "", "Override generated package name")
	fs.IntVar(&port, "port", 4100, "HTTP port for generated hosts")
	if err := fs.Parse(args); err != nil {
		if err == flag.ErrHelp {
			return 0
		}
		return 2
	}

	if outputPath == "" {
		fail("output path is required")
	}
	if registryURL != "" {
		registryBase = registryURL
	}
	loadedLock, err := generator.LoadPackageLock(lockFile)
	if err != nil {
		fail(err.Error())
	}
	resolveOptions := generator.ResolveServiceDefinitionOptions{
		DefinitionPath: definitionPath,
		PackageBundle:  packageBundle,
		RegistryBase:   registryBase,
		PackageID:      packageID,
		PackageVersion: packageVersion,
		PackageRef:     packageRef,
	}
	generator.ApplyPackageLockToResolveOptions(&resolveOptions, loadedLock)
	userCustomBundleRef := strings.TrimSpace(customCodeBundleRef)
	if userCustomBundleRef != "" {
		if _, err := generator.ValidateCustomCodeBundleRef(userCustomBundleRef); err != nil {
			fail(fmt.Sprintf("invalid --custom-code-bundle-ref: %v", err))
		}
	}
	if fetchCustomCodeBundle {
		if userCustomBundleRef == "" {
			fail("--fetch-custom-code-bundle requires --custom-code-bundle-ref")
		}
		if strings.TrimSpace(customCodeBundle) != "" {
			fail("--fetch-custom-code-bundle cannot be combined with --custom-code-bundle")
		}
		fail("--custom-code-bundle-ref passed immutable reference validation, but remote bundle fetching is not enabled yet; use --custom-code-bundle for a local filesystem bundle.")
	}
	if strings.TrimSpace(verifyCustomCodeBundleDigest) != "" && !generator.IsSHA256Digest(verifyCustomCodeBundleDigest) {
		fail("--verify-custom-code-bundle-digest must be sha256:<64 hex chars>")
	}
	if strings.TrimSpace(verifyCustomCodeBundleDigest) != "" && strings.TrimSpace(customCodeBundle) == "" {
		fail("--verify-custom-code-bundle-digest requires --custom-code-bundle")
	}
	transports, err := generator.ParseTransportList(transportList)
	if err != nil {
		fail(err.Error())
	}

	resolved, err := generator.ResolveServiceDefinition(context.Background(), nil, resolveOptions)
	if err != nil {
		fail(err.Error())
	}
	if err := generator.ValidateResolvedPackageLock(resolved, loadedLock); err != nil {
		fail(err.Error())
	}
	registryTrusted := resolved.SourceKind == "registry" && len(resolved.RegistryTrustChecks) > 0
	if _, err := generator.CustomCodeBundleMaterialsFromMetadata(resolved.Manifest, resolved.RecommendedLock); err != nil {
		fail(err.Error())
	}

	if target != "" {
		switch target {
		case "typescript":
			definition, err := generator.ParseServiceDefinition(resolved.DefinitionBytes)
			if err != nil {
				fail(err.Error())
			}
			project, err := generator.BuildTypeScriptProject(definition, generator.BuildTypeScriptProjectOptions{
				DependencySource: generator.DependencySource(dependencySource),
				HttpRuntime:      generator.HttpRuntime(framework),
				Transports:       transports,
				PackageName:      packageName,
				Port:             port,
			})
			if err != nil {
				fail(err.Error())
			}
			result := writeGeneratedProjectResult(resolved, registryTrusted, target, outputPath, project, force, customCodeBundle, userCustomBundleRef, verifyCustomCodeBundleDigest, includeDockerfile, includeDockerCompose, port, generator.DependencySource(dependencySource))
			writtenLock := writeLockOrFail(writeLock, resolved)
			addLockResultMetadata(result, lockFile, writeLock, writtenLock)
			encoder := json.NewEncoder(stdout)
			encoder.SetIndent("", "  ")
			_ = encoder.Encode(result)
			return
		case "go":
			definition, err := generator.ParseServiceDefinition(resolved.DefinitionBytes)
			if err != nil {
				fail(err.Error())
			}
			project, err := generator.BuildGoProject(definition, generator.BuildGoProjectOptions{
				DependencySource: generator.DependencySource(dependencySource),
				Transports:       transports,
				ModulePath:       packageName,
				Port:             port,
			})
			if err != nil {
				fail(err.Error())
			}
			result := writeGeneratedProjectResult(resolved, registryTrusted, target, outputPath, project, force, customCodeBundle, userCustomBundleRef, verifyCustomCodeBundleDigest, includeDockerfile, includeDockerCompose, port, generator.DependencySource(dependencySource))
			writtenLock := writeLockOrFail(writeLock, resolved)
			addLockResultMetadata(result, lockFile, writeLock, writtenLock)
			encoder := json.NewEncoder(stdout)
			encoder.SetIndent("", "  ")
			_ = encoder.Encode(result)
			return
		case "python":
			definition, err := generator.ParseServiceDefinition(resolved.DefinitionBytes)
			if err != nil {
				fail(err.Error())
			}
			pythonPackageName := packageName
			if strings.TrimSpace(pythonPackageName) == "" && strings.TrimSpace(resolved.PackageID) != "" {
				pythonPackageName = generator.PythonModuleNameForPackageID(resolved.PackageID)
			}
			pythonProjectName := packageName
			if strings.TrimSpace(pythonProjectName) == "" && strings.TrimSpace(resolved.PackageID) != "" {
				pythonProjectName = resolved.PackageID
			}
			project, err := generator.BuildPythonProject(definition, generator.BuildPythonProjectOptions{
				DependencySource: generator.DependencySource(dependencySource),
				Transports:       transports,
				ProjectName:      pythonProjectName,
				PackageName:      pythonPackageName,
				Port:             port,
			})
			if err != nil {
				fail(err.Error())
			}
			result := writeGeneratedProjectResult(resolved, registryTrusted, target, outputPath, project, force, customCodeBundle, userCustomBundleRef, verifyCustomCodeBundleDigest, includeDockerfile, includeDockerCompose, port, generator.DependencySource(dependencySource))
			writtenLock := writeLockOrFail(writeLock, resolved)
			addLockResultMetadata(result, lockFile, writeLock, writtenLock)
			encoder := json.NewEncoder(stdout)
			encoder.SetIndent("", "  ")
			_ = encoder.Encode(result)
			return
		case "java":
			definition, err := generator.ParseServiceDefinition(resolved.DefinitionBytes)
			if err != nil {
				fail(err.Error())
			}
			project, err := generator.BuildJavaProject(definition, generator.BuildJavaProjectOptions{
				DependencySource: generator.DependencySource(dependencySource),
				Framework:        generator.JavaFramework(framework),
				Transports:       transports,
				ArtifactID:       packageName,
				PackageName:      packageName,
				Port:             port,
			})
			if err != nil {
				fail(err.Error())
			}
			result := writeGeneratedProjectResult(resolved, registryTrusted, target, outputPath, project, force, customCodeBundle, userCustomBundleRef, verifyCustomCodeBundleDigest, includeDockerfile, includeDockerCompose, port, generator.DependencySource(dependencySource))
			writtenLock := writeLockOrFail(writeLock, resolved)
			addLockResultMetadata(result, lockFile, writeLock, writtenLock)
			encoder := json.NewEncoder(stdout)
			encoder.SetIndent("", "  ")
			_ = encoder.Encode(result)
			return
		case "csharp":
			definition, err := generator.ParseServiceDefinition(resolved.DefinitionBytes)
			if err != nil {
				fail(err.Error())
			}
			project, err := generator.BuildCSharpProject(definition, generator.BuildCSharpProjectOptions{
				DependencySource: generator.DependencySource(dependencySource),
				Transports:       transports,
				ProjectName:      packageName,
				RootNamespace:    packageName,
				Port:             port,
			})
			if err != nil {
				fail(err.Error())
			}
			result := writeGeneratedProjectResult(resolved, registryTrusted, target, outputPath, project, force, customCodeBundle, userCustomBundleRef, verifyCustomCodeBundleDigest, includeDockerfile, includeDockerCompose, port, generator.DependencySource(dependencySource))
			writtenLock := writeLockOrFail(writeLock, resolved)
			addLockResultMetadata(result, lockFile, writeLock, writtenLock)
			encoder := json.NewEncoder(stdout)
			encoder.SetIndent("", "  ")
			_ = encoder.Encode(result)
			return
		default:
			fail(fmt.Sprintf("unsupported target %q", target))
		}
	}

	if err := os.WriteFile(outputPath, resolved.DefinitionBytes, 0o600); err != nil {
		fail(fmt.Sprintf("write output definition: %v", err))
	}
	writtenLock := writeLockOrFail(writeLock, resolved)

	result := buildGenerateResult(resolved, registryTrusted, map[string]any{
		"output": outputPath,
	})
	addCustomCodeBundleMetadata(result, resolved, userCustomBundleRef, nil)
	addLockResultMetadata(result, lockFile, writeLock, writtenLock)
	encoder := json.NewEncoder(stdout)
	encoder.SetIndent("", "  ")
	_ = encoder.Encode(result)
	return 0
}

func writeLockOrFail(writeLock string, resolved *generator.ResolvedServiceDefinition) *generator.PackageLock {
	writtenLock, err := generator.WritePackageLock(writeLock, resolved)
	if err != nil {
		fail(err.Error())
	}
	return writtenLock
}

func addLockResultMetadata(result map[string]any, lockFile string, writeLock string, writtenLock *generator.PackageLock) {
	if strings.TrimSpace(lockFile) != "" {
		result["lock_file"] = lockFile
	}
	if strings.TrimSpace(writeLock) != "" {
		result["written_lock_file"] = writeLock
	}
	if writtenLock != nil {
		result["written_lock_digest"] = writtenLock.LockDigest
	}
}

func writeGeneratedProjectResult(
	resolved *generator.ResolvedServiceDefinition,
	registryTrusted bool,
	target string,
	outputPath string,
	project *generator.GeneratedProject,
	force bool,
	customCodeBundle string,
	customCodeBundleRef string,
	verifyCustomCodeBundleDigest string,
	includeDockerfile bool,
	includeDockerCompose bool,
	port int,
	dependencySource generator.DependencySource,
) map[string]any {
	customBundleReport, err := generator.ApplyCustomCodeBundleWithReport(project, customCodeBundle)
	if err != nil {
		fail(err.Error())
	}
	if customCodeBundle != "" {
		expectedDigest := strings.TrimSpace(verifyCustomCodeBundleDigest)
		if expectedDigest == "" {
			expectedDigest = firstDeclaredBundleTreeDigest(resolved)
		}
		if expectedDigest != "" && !strings.EqualFold(customBundleReport.BundleSHA256, expectedDigest) {
			fail(fmt.Sprintf("custom code bundle digest mismatch: expected %s got %s", expectedDigest, customBundleReport.BundleSHA256))
		}
	}
	if target == "python" {
		generator.EnsurePythonCustomModuleSupport(project)
	}
	if err := generator.ReconcileDependencyManifests(project, target, dependencySource); err != nil {
		fail(err.Error())
	}
	containerFiles, err := generator.BuildContainerArtifacts(target, project, generator.ContainerArtifactOptions{
		Dockerfile:    includeDockerfile,
		DockerCompose: includeDockerCompose,
		Port:          port,
	})
	if err != nil {
		fail(err.Error())
	}
	project.Files = append(project.Files, containerFiles...)

	agentKitFiles, err := generator.BuildAgentConsumptionKit(resolved)
	if err != nil {
		fail(err.Error())
	}
	project.Files = append(project.Files, agentKitFiles...)
	if customCodeBundle != "" {
		reportBytes, err := json.MarshalIndent(customBundleReport, "", "  ")
		if err != nil {
			fail(fmt.Sprintf("encode custom code bundle report: %v", err))
		}
		project.Files = append(project.Files, generator.GeneratedFile{
			Path:    "custom-code-bundle-report.json",
			Content: string(append(reportBytes, '\n')),
		})
	}
	if err := generator.WriteGeneratedProject(project, outputPath, force); err != nil {
		fail(err.Error())
	}
	extra := map[string]any{
		"target":                      target,
		"output":                      outputPath,
		"package_name":                project.PackageName,
		"system_name":                 project.SystemName,
		"transports":                  project.Transports,
		"file_count":                  len(project.Files),
		"agent_consumption_kit_files": len(agentKitFiles),
	}
	if project.Framework != "" {
		extra["framework"] = project.Framework
	}
	if customCodeBundle != "" {
		extra["custom_code_bundle"] = customCodeBundle
		extra["custom_files_applied"] = len(customBundleReport.Files)
		extra["custom_code_bundle_report"] = customBundleReport
	}
	if includeDockerfile {
		extra["dockerfile"] = true
	}
	if includeDockerCompose {
		extra["docker_compose"] = true
	}
	result := buildGenerateResult(resolved, registryTrusted, extra)
	addCustomCodeBundleMetadata(result, resolved, customCodeBundleRef, &customBundleReport)
	return result
}

func buildGenerateResult(resolved *generator.ResolvedServiceDefinition, registryTrusted bool, extra map[string]any) map[string]any {
	result := map[string]any{
		"status":             "ok",
		"source_kind":        resolved.SourceKind,
		"package_id":         resolved.PackageID,
		"package_version":    resolved.PackageVersion,
		"definition_digest":  resolved.DefinitionDigest,
		"lock_digest":        resolved.LockDigest,
		"contract_signature": resolved.ContractSignature,
		"schema_version":     resolved.SchemaVersion,
		"registry_trusted":   registryTrusted,
	}
	if resolved.ReceiptAuthority != "" {
		result["receipt_authority"] = resolved.ReceiptAuthority
	}
	if resolved.ReceiptSignature != "" {
		result["receipt_signature"] = resolved.ReceiptSignature
	}
	if resolved.ReceiptKeyID != "" {
		result["receipt_key_id"] = resolved.ReceiptKeyID
	}
	if resolved.ReceiptAlgorithm != "" {
		result["receipt_algorithm"] = resolved.ReceiptAlgorithm
	}
	if len(resolved.Lineage) > 0 {
		result["lineage"] = resolved.Lineage
		if productRevision, ok := resolved.Lineage["product_revision"]; ok {
			result["product_revision"] = productRevision
		}
		if developerRevision, ok := resolved.Lineage["developer_revision"]; ok {
			result["developer_revision"] = developerRevision
		}
	}
	if len(resolved.AgentReadiness) > 0 {
		result["agent_consumption_readiness"] = resolved.AgentReadiness
		if summary, ok := resolved.AgentReadiness["summary"].(map[string]any); ok {
			result["agent_readiness_summary"] = summary
		}
	}
	if len(resolved.AgentConsumability) > 0 {
		result["agent_consumability"] = resolved.AgentConsumability
		if capabilities, ok := resolved.AgentConsumability["capabilities"].(map[string]any); ok {
			result["agent_consumability_summary"] = map[string]any{
				"capability_count": len(capabilities),
				"schema_version":   resolved.AgentConsumability["schema_version"],
			}
		}
	}
	for key, value := range extra {
		result[key] = value
	}
	return result
}

func addCustomCodeBundleMetadata(result map[string]any, resolved *generator.ResolvedServiceDefinition, userRef string, localReport *generator.CustomCodeBundleReport) {
	materials, err := generator.CustomCodeBundleMaterialsFromMetadata(resolved.Manifest, resolved.RecommendedLock)
	if err != nil {
		fail(err.Error())
	}
	if strings.TrimSpace(userRef) != "" {
		parsed, err := generator.ValidateCustomCodeBundleRef(userRef)
		if err != nil {
			fail(fmt.Sprintf("invalid --custom-code-bundle-ref: %v", err))
		}
		materials = append(materials, generator.CustomCodeBundleMaterial{
			Ref:       userRef,
			Kind:      parsed.Kind,
			Locator:   parsed.Locator,
			Immutable: parsed.Immutable,
			Digest:    parsed.Digest,
			Source:    "cli.custom_code_bundle_ref",
		})
	}
	if len(materials) > 0 {
		result["custom_code_bundle_refs"] = materials
	}
	warnings := customCodeBundleWarnings(materials, localReport)
	if len(warnings) > 0 {
		result["custom_code_bundle_warnings"] = warnings
	}
}

func customCodeBundleWarnings(materials []generator.CustomCodeBundleMaterial, localReport *generator.CustomCodeBundleReport) []string {
	if len(materials) == 0 {
		return nil
	}
	localApplied := localReport != nil && localReport.BundlePath != "" && len(localReport.Files) > 0
	warnings := []string{}
	if !localApplied {
		warnings = append(warnings, "Custom implementation material is declared but was not fetched or applied. Use --custom-code-bundle for reviewed local material, or explicitly opt into remote fetching when that feature is enabled.")
	}
	for _, material := range materials {
		if localApplied && material.BundleTreeSHA256 == "" {
			warnings = append(warnings, fmt.Sprintf("Custom bundle ref %s pins remote artifact bytes; no normalized local tree digest was declared for automatic local bundle comparison.", material.Ref))
		}
	}
	return warnings
}

func firstDeclaredBundleTreeDigest(resolved *generator.ResolvedServiceDefinition) string {
	materials, err := generator.CustomCodeBundleMaterialsFromMetadata(resolved.Manifest, resolved.RecommendedLock)
	if err != nil {
		fail(err.Error())
	}
	for _, material := range materials {
		if material.BundleTreeSHA256 != "" {
			return material.BundleTreeSHA256
		}
	}
	return ""
}

func fail(message string) {
	panic(cliError{message: message})
}

func hasHelpFlag(args []string) bool {
	for _, arg := range args {
		if arg == "-h" || arg == "--help" {
			return true
		}
	}
	return false
}
