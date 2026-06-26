package generator

import (
	"encoding/json"
	"fmt"
	"regexp"
	"sort"
	"strings"
)

// ReconcileDependencyManifests re-asserts generator-owned dependency manifests
// after custom bundle overlay. Custom bundles own implementation seams; the
// generator owns SDK dependency coordinates and local-vs-registry resolution.
func ReconcileDependencyManifests(project *GeneratedProject, target string, dependencySource DependencySource) error {
	if project == nil {
		return nil
	}
	if dependencySource == "" {
		dependencySource = DependencySourceRegistry
	}
	if err := validateDependencySource(dependencySource); err != nil {
		return err
	}
	transports, err := normalizeTransportsFromNames(project.Transports)
	if err != nil {
		return err
	}
	switch target {
	case "python":
		packageName := project.CustomBundleTemplateValues["PYTHON_MODULE_NAME"]
		if packageName == "" {
			packageName = pythonModuleName(project.SystemName)
		}
		projectName := project.PackageName
		if projectName == "" {
			projectName = systemNameToPackageName(project.SystemName)
		}
		content := mergePythonPyproject(project, buildGeneratedPythonPyproject(projectName, packageName, dependencySource, transports))
		upsertGeneratedFile(project, GeneratedFile{Path: "pyproject.toml", Content: content})
	case "typescript":
		runtime := HttpRuntime(project.Framework)
		if runtime == "" {
			runtime = HttpRuntimeHono
		}
		if err := validateTypeScriptRuntime(runtime); err != nil {
			return err
		}
		packageName := project.PackageName
		if packageName == "" {
			packageName = systemNameToPackageName(project.SystemName)
		}
		content, err := mergeTypeScriptPackageJSON(project, buildGeneratedPackageJSON(packageName, dependencySource, runtime, transports))
		if err != nil {
			return err
		}
		upsertGeneratedFile(project, GeneratedFile{Path: "package.json", Content: content})
	case "go":
		modulePath := project.CustomBundleTemplateValues["GO_MODULE_PATH"]
		if modulePath == "" {
			modulePath = "generated/" + systemNameToPackageName(project.SystemName)
		}
		content := mergeGoMod(project, buildGeneratedGoMod(modulePath, dependencySource))
		upsertGeneratedFile(project, GeneratedFile{Path: "go.mod", Content: content})
		if dependencySource == DependencySourceLocal {
			upsertGeneratedFile(project, GeneratedFile{Path: "go.work", Content: buildGeneratedGoWorkspace()})
		}
	case "java":
		framework := JavaFramework(project.Framework)
		if framework == "" {
			framework = JavaFrameworkSpringBoot
		}
		if err := validateJavaFramework(framework); err != nil {
			return err
		}
		artifactID := project.PackageName
		if artifactID == "" {
			artifactID = systemNameToPackageName(project.SystemName)
		}
		upsertGeneratedFile(project, GeneratedFile{Path: "pom.xml", Content: buildGeneratedJavaAppPom(artifactID, dependencySource, framework, transports)})
	case "csharp":
		projectName := project.CustomBundleTemplateValues["PACKAGE_NAME"]
		if projectName == "" {
			projectName = project.PackageName
		}
		if projectName == "" {
			projectName = csharpProjectName(project.SystemName)
		}
		upsertGeneratedFile(project, GeneratedFile{Path: projectName + ".csproj", Content: buildGeneratedCSharpProjectFile(dependencySource, transports)})
		upsertGeneratedFile(project, GeneratedFile{Path: "tests/" + projectName + ".Tests.csproj", Content: buildGeneratedCSharpTestsProjectFile(projectName, dependencySource)})
	default:
		return fmt.Errorf("unsupported target %q", target)
	}
	return nil
}

func normalizeTransportsFromNames(names []string) ([]Transport, error) {
	if len(names) == 0 {
		return []Transport{TransportHTTP}, nil
	}
	transports := make([]Transport, 0, len(names))
	for _, name := range names {
		transports = append(transports, Transport(name))
	}
	return normalizeTransports(transports)
}

func mergeTypeScriptPackageJSON(project *GeneratedProject, generated string) (string, error) {
	existingContent, ok := generatedProjectFileContent(project, "package.json")
	if !ok || strings.TrimSpace(existingContent) == "" {
		return generated, nil
	}
	var existing map[string]any
	if err := json.Unmarshal([]byte(existingContent), &existing); err != nil {
		return generated, nil
	}
	var next map[string]any
	if err := json.Unmarshal([]byte(generated), &next); err != nil {
		return "", err
	}

	for key, value := range existing {
		if _, managed := next[key]; !managed {
			next[key] = value
		}
	}
	next["dependencies"] = mergeStringMap(sectionAsStringMap(existing["dependencies"]), sectionAsStringMap(next["dependencies"]), true)
	next["devDependencies"] = mergeStringMap(sectionAsStringMap(existing["devDependencies"]), sectionAsStringMap(next["devDependencies"]), true)
	next["scripts"] = mergeStringMap(sectionAsStringMap(next["scripts"]), sectionAsStringMap(existing["scripts"]), true)

	data, err := json.MarshalIndent(next, "", "  ")
	if err != nil {
		return "", err
	}
	return string(data) + "\n", nil
}

func sectionAsStringMap(value any) map[string]string {
	result := map[string]string{}
	section, ok := value.(map[string]any)
	if !ok {
		return result
	}
	for key, raw := range section {
		if text, ok := raw.(string); ok {
			result[key] = text
		}
	}
	return result
}

func mergeStringMap(base map[string]string, overlay map[string]string, sortKeys bool) map[string]string {
	result := map[string]string{}
	for key, value := range base {
		result[key] = value
	}
	for key, value := range overlay {
		result[key] = value
	}
	if !sortKeys {
		return result
	}
	// Rebuild through sorted iteration for stable JSON encoder insertion order.
	keys := make([]string, 0, len(result))
	for key := range result {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	stable := map[string]string{}
	for _, key := range keys {
		stable[key] = result[key]
	}
	return stable
}

func mergePythonPyproject(project *GeneratedProject, generated string) string {
	existingContent, ok := generatedProjectFileContent(project, "pyproject.toml")
	if !ok || strings.TrimSpace(existingContent) == "" {
		return generated
	}
	if existingName := extractPythonProjectField(existingContent, "name"); existingName != "" {
		generated = replacePythonProjectField(generated, "name", existingName)
	}
	if existingVersion := extractPythonProjectField(existingContent, "version"); existingVersion != "" {
		generated = replacePythonProjectField(generated, "version", existingVersion)
	}
	generatedDeps := extractPythonDependencies(generated)
	seen := map[string]bool{}
	for _, dep := range generatedDeps {
		seen[pythonDependencyKey(dep)] = true
	}
	customDeps := []string{}
	for _, dep := range extractPythonDependencies(existingContent) {
		if isManagedPythonDependency(dep) {
			continue
		}
		key := pythonDependencyKey(dep)
		if key == "" || seen[key] {
			continue
		}
		seen[key] = true
		customDeps = append(customDeps, dep)
	}
	if len(customDeps) == 0 {
		return generated
	}
	return appendPythonDependencies(generated, customDeps)
}

func extractPythonProjectField(content, field string) string {
	pattern := regexp.MustCompile(`(?m)^` + regexp.QuoteMeta(field) + `\s*=\s*"([^"]+)"\s*$`)
	match := pattern.FindStringSubmatch(content)
	if len(match) != 2 {
		return ""
	}
	return strings.TrimSpace(match[1])
}

func replacePythonProjectField(content, field, value string) string {
	pattern := regexp.MustCompile(`(?m)^` + regexp.QuoteMeta(field) + `\s*=\s*"[^"]*"\s*$`)
	replacement := fmt.Sprintf(`%s = "%s"`, field, strings.ReplaceAll(value, `"`, `\"`))
	if pattern.MatchString(content) {
		return pattern.ReplaceAllString(content, replacement)
	}
	return content
}

var pythonDependencyRE = regexp.MustCompile(`"([^"]+)"`)

func extractPythonDependencies(content string) []string {
	lines := strings.Split(content, "\n")
	inDeps := false
	deps := []string{}
	for _, line := range lines {
		trimmed := strings.TrimSpace(line)
		if strings.HasPrefix(trimmed, "dependencies = [") {
			inDeps = true
			matches := pythonDependencyRE.FindAllStringSubmatch(line, -1)
			for _, match := range matches {
				deps = append(deps, match[1])
			}
			continue
		}
		if !inDeps {
			continue
		}
		if trimmed == "]" {
			break
		}
		matches := pythonDependencyRE.FindAllStringSubmatch(line, -1)
		for _, match := range matches {
			deps = append(deps, match[1])
		}
	}
	return deps
}

func isManagedPythonDependency(dep string) bool {
	key := pythonDependencyKey(dep)
	return key == "anip-core" || key == "anip-service" || key == "anip-fastapi"
}

func pythonDependencyKey(dep string) string {
	text := strings.TrimSpace(strings.ToLower(dep))
	if text == "" {
		return ""
	}
	for _, separator := range []string{" @ ", "==", ">=", "<=", "~=", "!=", ">", "<", "["} {
		if idx := strings.Index(text, separator); idx >= 0 {
			return strings.TrimSpace(text[:idx])
		}
	}
	return text
}

func appendPythonDependencies(content string, deps []string) string {
	lines := strings.Split(content, "\n")
	inDeps := false
	for idx, line := range lines {
		trimmed := strings.TrimSpace(line)
		if strings.HasPrefix(trimmed, "dependencies = [") {
			inDeps = true
			continue
		}
		if inDeps && trimmed == "]" {
			insert := make([]string, 0, len(deps))
			for _, dep := range deps {
				insert = append(insert, fmt.Sprintf(`    "%s",`, dep))
			}
			next := append([]string{}, lines[:idx]...)
			next = append(next, insert...)
			next = append(next, lines[idx:]...)
			return strings.Join(next, "\n")
		}
	}
	return content
}

func mergeGoMod(project *GeneratedProject, generated string) string {
	existingContent, ok := generatedProjectFileContent(project, "go.mod")
	if !ok || strings.TrimSpace(existingContent) == "" {
		return generated
	}
	customRequires := extractGoRequireLines(existingContent)
	filtered := make([]string, 0, len(customRequires))
	seen := map[string]bool{
		"github.com/anip-protocol/anip/packages/go": true,
	}
	for _, line := range customRequires {
		module := goRequireModule(line)
		if module == "" || seen[module] {
			continue
		}
		seen[module] = true
		filtered = append(filtered, line)
	}
	if len(filtered) == 0 {
		return generated
	}
	return appendGoRequireLines(generated, filtered)
}

func extractGoRequireLines(content string) []string {
	lines := strings.Split(content, "\n")
	requires := []string{}
	inBlock := false
	for _, line := range lines {
		trimmed := strings.TrimSpace(line)
		if strings.HasPrefix(trimmed, "require (") {
			inBlock = true
			continue
		}
		if inBlock {
			if trimmed == ")" {
				inBlock = false
				continue
			}
			if trimmed != "" {
				requires = append(requires, trimmed)
			}
			continue
		}
		if strings.HasPrefix(trimmed, "require ") {
			requires = append(requires, strings.TrimSpace(strings.TrimPrefix(trimmed, "require ")))
		}
	}
	return requires
}

func goRequireModule(line string) string {
	fields := strings.Fields(line)
	if len(fields) < 2 {
		return ""
	}
	return fields[0]
}

func appendGoRequireLines(content string, requires []string) string {
	lines := strings.Split(content, "\n")
	for idx, line := range lines {
		trimmed := strings.TrimSpace(line)
		if strings.HasPrefix(trimmed, "require ") && !strings.HasPrefix(trimmed, "require (") {
			existing := strings.TrimSpace(strings.TrimPrefix(trimmed, "require "))
			block := []string{"require ("}
			block = append(block, "\t"+existing)
			for _, req := range requires {
				block = append(block, "\t"+req)
			}
			block = append(block, ")")
			next := append([]string{}, lines[:idx]...)
			next = append(next, block...)
			next = append(next, lines[idx+1:]...)
			return strings.Join(next, "\n")
		}
		if strings.HasPrefix(trimmed, "require (") {
			insertIdx := idx + 1
			for insertIdx < len(lines) && strings.TrimSpace(lines[insertIdx]) != ")" {
				insertIdx++
			}
			insert := make([]string, 0, len(requires))
			for _, req := range requires {
				insert = append(insert, "\t"+req)
			}
			next := append([]string{}, lines[:insertIdx]...)
			next = append(next, insert...)
			next = append(next, lines[insertIdx:]...)
			return strings.Join(next, "\n")
		}
	}
	return content
}
