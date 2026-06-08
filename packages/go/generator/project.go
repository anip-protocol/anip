package generator

import (
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
)

var customBundleCapabilityDeclarationPatterns = []*regexp.Regexp{
	regexp.MustCompile(`(?s)CapabilityDeclaration\s*\(\s*name\s*=\s*["']([a-z][a-z0-9]*(?:[._][a-z0-9_]+)+)["']`),
	regexp.MustCompile(`(?s)defineCapability\s*\(\s*\{[^}]*?(?:name|id|capabilityId)\s*:\s*["']([a-z][a-z0-9]*(?:[._][a-z0-9_]+)+)["']`),
	regexp.MustCompile(`(?s)CapabilityDef\s*\{[^}]*?(?:Name|ID|CapabilityID)\s*:\s*["']([a-z][a-z0-9]*(?:[._][a-z0-9_]+)+)["']`),
	regexp.MustCompile(`(?s)new\s+CapabilityDeclaration\s*\([^)]*["']([a-z][a-z0-9]*(?:[._][a-z0-9_]+)+)["']`),
}

var generatedPathSegmentPattern = regexp.MustCompile(`^[A-Za-z0-9._@+-]+$`)

func ParseServiceDefinition(data []byte) (*AnipServiceDefinition, error) {
	var definition AnipServiceDefinition
	if err := json.Unmarshal(data, &definition); err != nil {
		return nil, fmt.Errorf("decode service definition: %w", err)
	}
	return &definition, nil
}

func NormalizeServiceDefinitionBytes(definition *AnipServiceDefinition) ([]byte, error) {
	normalized, err := json.MarshalIndent(definition, "", "  ")
	if err != nil {
		return nil, fmt.Errorf("encode normalized service definition: %w", err)
	}
	return append(normalized, '\n'), nil
}

func WriteGeneratedProject(project *GeneratedProject, outputDir string, force bool) error {
	outputPath := filepath.Clean(outputDir)
	if force {
		if err := os.RemoveAll(outputPath); err != nil {
			return fmt.Errorf("remove existing output directory: %w", err)
		}
	} else {
		if _, err := os.Stat(outputPath); err == nil {
			return fmt.Errorf("output directory already exists: %s", outputPath)
		} else if !os.IsNotExist(err) {
			return fmt.Errorf("stat output directory: %w", err)
		}
	}

	if err := os.MkdirAll(outputPath, 0o755); err != nil {
		return fmt.Errorf("create output directory: %w", err)
	}
	outputAbs, err := filepath.Abs(outputPath)
	if err != nil {
		return fmt.Errorf("resolve output directory: %w", err)
	}

	for _, file := range project.Files {
		normalizedPath, err := validateGeneratedFilePath(file.Path)
		if err != nil {
			return err
		}
		destination := filepath.Join(outputPath, filepath.FromSlash(normalizedPath))
		destinationAbs, err := filepath.Abs(destination)
		if err != nil {
			return fmt.Errorf("resolve generated file %s: %w", normalizedPath, err)
		}
		if destinationAbs != outputAbs && !strings.HasPrefix(destinationAbs, outputAbs+string(os.PathSeparator)) {
			return fmt.Errorf("generated file path escapes output directory: %s", normalizedPath)
		}
		if err := os.MkdirAll(filepath.Dir(destination), 0o755); err != nil {
			return fmt.Errorf("create file parent directory for %s: %w", normalizedPath, err)
		}
		if err := os.WriteFile(destination, []byte(file.Content), 0o600); err != nil {
			return fmt.Errorf("write generated file %s: %w", normalizedPath, err)
		}
	}
	return nil
}

func ApplyCustomCodeBundle(project *GeneratedProject, bundleDir string) (int, error) {
	report, err := ApplyCustomCodeBundleWithReport(project, bundleDir)
	if err != nil {
		return 0, err
	}
	return len(report.Files), nil
}

type CustomCodeBundleReport struct {
	BundlePath   string                 `json:"bundle_path,omitempty"`
	BundleSHA256 string                 `json:"bundle_sha256,omitempty"`
	Files        []CustomCodeBundleFile `json:"files"`
}

type CustomCodeBundleFile struct {
	Path       string `json:"path"`
	SHA256     string `json:"sha256"`
	Seam       string `json:"seam"`
	Mode       string `json:"mode"`
	Bytes      int    `json:"bytes"`
	Overlaid   bool   `json:"overlaid"`
	Substrate  bool   `json:"substrate"`
	Executable bool   `json:"executable,omitempty"`
}

func ApplyCustomCodeBundleWithReport(project *GeneratedProject, bundleDir string) (CustomCodeBundleReport, error) {
	if project == nil {
		return CustomCodeBundleReport{}, fmt.Errorf("generated project is required")
	}
	trimmedBundleDir := strings.TrimSpace(bundleDir)
	if trimmedBundleDir == "" {
		return CustomCodeBundleReport{}, nil
	}
	bundlePath := filepath.Clean(trimmedBundleDir)
	info, err := os.Stat(bundlePath)
	if err != nil {
		return CustomCodeBundleReport{}, fmt.Errorf("stat custom code bundle: %w", err)
	}
	if !info.IsDir() {
		return CustomCodeBundleReport{}, fmt.Errorf("custom code bundle must be a directory: %s", bundlePath)
	}
	if err := validateCustomCodeBundleCapabilities(project, bundlePath); err != nil {
		return CustomCodeBundleReport{}, err
	}

	report := CustomCodeBundleReport{BundlePath: bundlePath}
	err = filepath.WalkDir(bundlePath, func(path string, entry os.DirEntry, walkErr error) error {
		if walkErr != nil {
			return walkErr
		}
		if entry.IsDir() && isIgnoredCustomBundleDir(entry.Name()) {
			return filepath.SkipDir
		}
		if entry.IsDir() {
			return nil
		}
		if !isCustomBundleImplementationFile(path) {
			return nil
		}
		if entry.Type()&os.ModeSymlink != 0 {
			return fmt.Errorf("custom code bundle must not contain symlinks: %s", path)
		}
		relativePath, err := filepath.Rel(bundlePath, path)
		if err != nil {
			return err
		}
		relativePath = applyCustomBundleTemplateValues(relativePath, project.CustomBundleTemplateValues)
		relativePath, err = validateGeneratedFilePath(relativePath)
		if err != nil {
			return fmt.Errorf("invalid custom code bundle path: %w", err)
		}
		bytes, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		content := applyCustomBundleTemplateValues(string(bytes), project.CustomBundleTemplateValues)
		relativePath, err = remapTemplatedCustomBundlePath(project, relativePath, content)
		if err != nil {
			return fmt.Errorf("invalid custom code bundle path: %w", err)
		}
		if err := validateCustomCodeBundleOverlayPath(project, relativePath); err != nil {
			return err
		}
		existing := generatedProjectHasPath(project, relativePath)
		upsertGeneratedFile(project, GeneratedFile{Path: relativePath, Content: content})
		report.Files = append(report.Files, customCodeBundleFileReport(relativePath, []byte(content), existing, entry.Type()))
		return nil
	})
	if err != nil {
		return CustomCodeBundleReport{}, fmt.Errorf("apply custom code bundle: %w", err)
	}
	sort.Slice(report.Files, func(i, j int) bool {
		return report.Files[i].Path < report.Files[j].Path
	})
	report.BundleSHA256 = customCodeBundleTreeDigest(report.Files)
	return report, nil
}

func remapTemplatedCustomBundlePath(project *GeneratedProject, path string, content string) (string, error) {
	if project == nil || len(project.CustomBundleTemplateValues) == 0 {
		return path, nil
	}
	pythonModuleName := strings.TrimSpace(project.CustomBundleTemplateValues["PYTHON_MODULE_NAME"])
	if pythonModuleName != "" && strings.HasPrefix(path, "src/") && strings.HasSuffix(strings.ToLower(path), ".py") {
		parts := strings.Split(path, "/")
		if len(parts) == 3 && strings.EqualFold(parts[2], "app.py") {
			return path, nil
		}
		if len(parts) >= 3 && parts[1] != pythonModuleName && isRemappablePythonCustomPackage(parts[1]) {
			remappedParts := append([]string{"src", pythonModuleName}, parts[2:]...)
			return validateGeneratedFilePath(filepath.ToSlash(filepath.Join(remappedParts...)))
		}
	}
	packageName := strings.TrimSpace(project.CustomBundleTemplateValues["JAVA_PACKAGE_NAME"])
	packagePath := strings.TrimSpace(project.CustomBundleTemplateValues["JAVA_PACKAGE_PATH"])
	lowerPath := strings.ToLower(path)
	if packageName == "" || packagePath == "" || !strings.HasPrefix(lowerPath, "src/main/java/") || !strings.HasSuffix(lowerPath, ".java") {
		return path, nil
	}
	if !strings.Contains(content, "package "+packageName+";") {
		return path, nil
	}
	remapped := filepath.ToSlash(filepath.Join("src", "main", "java", filepath.FromSlash(packagePath), filepath.Base(path)))
	return validateGeneratedFilePath(remapped)
}

func isRemappablePythonCustomPackage(packageName string) bool {
	switch strings.ToLower(strings.TrimSpace(packageName)) {
	case "", "shared", "common", "tests", "test":
		return false
	default:
		return true
	}
}

func applyCustomBundleTemplateValues(content string, values map[string]string) string {
	if len(values) == 0 {
		return content
	}
	for key, value := range values {
		content = strings.ReplaceAll(content, "{{ANIP_"+key+"}}", value)
	}
	return content
}

func ComputeCustomCodeBundleTreeDigest(bundleDir string) (string, error) {
	trimmedBundleDir := strings.TrimSpace(bundleDir)
	if trimmedBundleDir == "" {
		return "", fmt.Errorf("custom code bundle directory is required")
	}
	bundlePath := filepath.Clean(trimmedBundleDir)
	info, err := os.Stat(bundlePath)
	if err != nil {
		return "", fmt.Errorf("stat custom code bundle: %w", err)
	}
	if !info.IsDir() {
		return "", fmt.Errorf("custom code bundle must be a directory: %s", bundlePath)
	}

	files := []CustomCodeBundleFile{}
	err = filepath.WalkDir(bundlePath, func(path string, entry os.DirEntry, walkErr error) error {
		if walkErr != nil {
			return walkErr
		}
		if path == bundlePath {
			return nil
		}
		if entry.IsDir() && isIgnoredCustomBundleDir(entry.Name()) {
			return filepath.SkipDir
		}
		if entry.IsDir() {
			return nil
		}
		if !isCustomBundleImplementationFile(path) {
			return nil
		}
		if entry.Type()&os.ModeSymlink != 0 {
			return fmt.Errorf("custom code bundle must not contain symlinks: %s", path)
		}
		relativePath, err := filepath.Rel(bundlePath, path)
		if err != nil {
			return err
		}
		relativePath = filepath.ToSlash(filepath.Clean(relativePath))
		relativePath, err = validateGeneratedFilePath(relativePath)
		if err != nil {
			return fmt.Errorf("invalid custom code bundle path: %w", err)
		}
		bytes, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		files = append(files, customCodeBundleFileReport(relativePath, bytes, false, entry.Type()))
		return nil
	})
	if err != nil {
		return "", fmt.Errorf("compute custom code bundle digest: %w", err)
	}
	sort.Slice(files, func(i, j int) bool {
		return files[i].Path < files[j].Path
	})
	return customCodeBundleTreeDigest(files), nil
}

func validateCustomCodeBundleCapabilities(project *GeneratedProject, bundlePath string) error {
	contractCapabilityIDs := map[string]struct{}{}
	for _, service := range project.Services {
		for _, capabilityID := range service.FormalizedCapabilityIDs {
			if capabilityID = strings.TrimSpace(capabilityID); capabilityID != "" {
				contractCapabilityIDs[capabilityID] = struct{}{}
			}
		}
	}
	if len(contractCapabilityIDs) == 0 {
		return nil
	}

	missingByID := map[string]string{}
	err := filepath.WalkDir(bundlePath, func(path string, entry os.DirEntry, walkErr error) error {
		if walkErr != nil {
			return walkErr
		}
		if entry.IsDir() || !isCustomBundleSourceFile(path) {
			return nil
		}
		if entry.Type()&os.ModeSymlink != 0 {
			return fmt.Errorf("custom code bundle must not contain symlinks: %s", path)
		}
		bytes, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		relativePath, err := filepath.Rel(bundlePath, path)
		if err != nil {
			return err
		}
		relativePath = filepath.ToSlash(filepath.Clean(relativePath))
		for _, candidate := range declaredCapabilityIDsFromCustomBundleFile(bytes) {
			if !looksLikeCustomBundleCapabilityID(candidate) {
				continue
			}
			if _, ok := contractCapabilityIDs[candidate]; !ok {
				missingByID[candidate] = relativePath
			}
		}
		return nil
	})
	if err != nil {
		return fmt.Errorf("validate custom code bundle capabilities: %w", err)
	}
	if len(missingByID) == 0 {
		return nil
	}
	missing := make([]string, 0, len(missingByID))
	for capabilityID, sourcePath := range missingByID {
		missing = append(missing, fmt.Sprintf("%s in %s", capabilityID, sourcePath))
	}
	sort.Strings(missing)
	return fmt.Errorf(
		"custom code bundle declares capability ids that are not present in the service definition: %s. "+
			"Update the contract IDs, update the custom bundle, or include the correct source-declared IDs before generation.",
		strings.Join(missing, ", "),
	)
}

func declaredCapabilityIDsFromCustomBundleFile(bytes []byte) []string {
	ids := []string{}
	seen := map[string]struct{}{}
	for _, pattern := range customBundleCapabilityDeclarationPatterns {
		for _, match := range pattern.FindAllSubmatch(bytes, -1) {
			if len(match) < 2 {
				continue
			}
			candidate := string(match[1])
			if _, ok := seen[candidate]; ok {
				continue
			}
			seen[candidate] = struct{}{}
			ids = append(ids, candidate)
		}
	}
	return ids
}

func isCustomBundleSourceFile(path string) bool {
	switch strings.ToLower(filepath.Ext(path)) {
	case ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".java", ".cs", ".json", ".yaml", ".yml":
		return true
	default:
		return false
	}
}

func isCustomBundleImplementationFile(path string) bool {
	lower := strings.ToLower(filepath.Base(path))
	if lower == "readme.md" || lower == "pyproject.toml" || lower == "package.json" ||
		lower == "go.mod" || lower == "pom.xml" || strings.HasSuffix(lower, ".csproj") {
		return true
	}
	return isCustomBundleSourceFile(path)
}

func isIgnoredCustomBundleDir(name string) bool {
	switch strings.ToLower(name) {
	case "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox", ".venv", "node_modules", "dist", "build", ".git":
		return true
	default:
		return false
	}
}

func looksLikeCustomBundleCapabilityID(value string) bool {
	if value == "" || !strings.Contains(value, ".") {
		return false
	}
	lower := strings.ToLower(value)
	if strings.Contains(lower, "://") || strings.Contains(lower, "/") {
		return false
	}
	if strings.HasPrefix(lower, "$.") {
		return false
	}
	if strings.HasSuffix(lower, ".py") || strings.HasSuffix(lower, ".ts") || strings.HasSuffix(lower, ".js") ||
		strings.HasSuffix(lower, ".go") || strings.HasSuffix(lower, ".java") || strings.HasSuffix(lower, ".cs") ||
		strings.HasSuffix(lower, ".json") || strings.HasSuffix(lower, ".yaml") || strings.HasSuffix(lower, ".yml") {
		return false
	}
	return true
}

func validateGeneratedFilePath(path string) (string, error) {
	if strings.TrimSpace(path) == "" {
		return "", fmt.Errorf("generated file path is required")
	}
	if strings.Contains(path, "\x00") || strings.Contains(path, "\\") {
		return "", fmt.Errorf("generated file path is invalid: %s", path)
	}
	normalized := filepath.ToSlash(filepath.Clean(path))
	if normalized == "." || strings.HasPrefix(normalized, "../") || strings.HasPrefix(normalized, "/") || filepath.IsAbs(normalized) {
		return "", fmt.Errorf("generated file path escapes output directory: %s", path)
	}
	if len(normalized) > 240 {
		return "", fmt.Errorf("generated file path is too long: %s", normalized)
	}
	for _, segment := range strings.Split(normalized, "/") {
		if segment == "" || segment == "." || segment == ".." || len(segment) > 100 || !generatedPathSegmentPattern.MatchString(segment) {
			return "", fmt.Errorf("generated file path contains unsafe segment: %s", normalized)
		}
	}
	return normalized, nil
}

func validateCustomCodeBundleOverlayPath(project *GeneratedProject, path string) error {
	if isProtectedGeneratedSubstratePath(path) {
		return fmt.Errorf("custom code bundle cannot replace generated substrate file: %s", path)
	}
	if generatedProjectHasPath(project, path) && !isAllowedCustomBundleOverlayPath(path) {
		if isPythonEntrypointOverlay(project, path) {
			return nil
		}
		return fmt.Errorf("custom code bundle can only replace declared extension seam files, not generated substrate: %s", path)
	}
	return nil
}

func isPythonEntrypointOverlay(project *GeneratedProject, path string) bool {
	if project == nil || !strings.HasSuffix(strings.ToLower(path), "/app.py") {
		return false
	}
	pythonModuleName := strings.TrimSpace(project.CustomBundleTemplateValues["PYTHON_MODULE_NAME"])
	if pythonModuleName == "" {
		return false
	}
	return strings.HasPrefix(path, filepath.ToSlash(filepath.Join("src", pythonModuleName))+"/")
}

func generatedProjectHasPath(project *GeneratedProject, path string) bool {
	normalizedPath := filepath.ToSlash(filepath.Clean(path))
	for _, file := range project.Files {
		normalized, err := validateGeneratedFilePath(file.Path)
		if err == nil && strings.EqualFold(normalized, normalizedPath) {
			return true
		}
	}
	return false
}

func isProtectedGeneratedSubstratePath(path string) bool {
	lower := strings.ToLower(path)
	if lower == "anip-service-definition.json" || lower == "dockerfile" || lower == "docker-compose.yml" {
		return true
	}
	if strings.HasPrefix(lower, "agent-consumption/") {
		return true
	}
	protectedSuffixes := []string{
		"/runtime_target.py",
		"/capabilities.py",
		"/runtime-target.ts",
		"/capabilities.ts",
		"/generatedruntime.cs",
		"/generatedcapabilities.cs",
		"/runtimetarget.java",
		"/generatedcapabilities.java",
	}
	for _, suffix := range protectedSuffixes {
		if strings.HasSuffix(lower, suffix) {
			return true
		}
	}
	return false
}

func isAllowedCustomBundleOverlayPath(path string) bool {
	lower := strings.ToLower(path)
	if lower == "pyproject.toml" || lower == "package.json" || lower == "go.mod" || lower == "pom.xml" || strings.HasSuffix(lower, ".csproj") || lower == "readme.md" {
		return true
	}
	if lower == "backendadapter.cs" || lower == "backend_adapter.cs" || lower == "policy.cs" {
		return true
	}
	if strings.HasPrefix(lower, "tests/") || strings.HasPrefix(lower, "test/") {
		return true
	}
	allowedSuffixes := []string{
		"/backend_adapter.py",
		"/policy.py",
		"/backend-adapter.ts",
		"/policy.ts",
		"/backend_adapter.go",
		"/policy.go",
		"/backendadapter.java",
		"/policy.java",
		"/backendadapter.cs",
		"/policy.cs",
	}
	for _, suffix := range allowedSuffixes {
		if strings.HasSuffix(lower, suffix) {
			return true
		}
	}
	return false
}

func customCodeBundleFileReport(path string, content []byte, overlaid bool, mode os.FileMode) CustomCodeBundleFile {
	sum := sha256.Sum256(content)
	seam := customBundleSeamForPath(path)
	return CustomCodeBundleFile{
		Path:       path,
		SHA256:     fmt.Sprintf("sha256:%x", sum[:]),
		Seam:       seam,
		Mode:       customBundleModeForPath(path, seam, overlaid),
		Bytes:      len(content),
		Overlaid:   overlaid,
		Substrate:  false,
		Executable: mode&0o111 != 0,
	}
}

func customCodeBundleTreeDigest(files []CustomCodeBundleFile) string {
	if len(files) == 0 {
		sum := sha256.Sum256(nil)
		return fmt.Sprintf("sha256:%x", sum[:])
	}
	hash := sha256.New()
	for _, file := range files {
		hash.Write([]byte(file.Path))
		hash.Write([]byte{0})
		hash.Write([]byte(file.SHA256))
		hash.Write([]byte{0})
		if file.Executable {
			hash.Write([]byte("x"))
		} else {
			hash.Write([]byte("-"))
		}
		hash.Write([]byte{0})
	}
	return fmt.Sprintf("sha256:%x", hash.Sum(nil))
}

func customBundleModeForPath(path string, seam string, overlaid bool) string {
	if overlaid {
		return "extension_overlay"
	}
	if seam != "custom_file" {
		return "extension_material"
	}
	lower := strings.ToLower(path)
	if lower == "pyproject.toml" || lower == "package.json" || lower == "go.mod" || lower == "pom.xml" || strings.HasSuffix(lower, ".csproj") {
		return "project_metadata"
	}
	return "custom_file"
}

func customBundleSeamForPath(path string) string {
	lower := strings.ToLower(path)
	switch {
	case strings.HasSuffix(lower, "/backend_adapter.py"), strings.HasSuffix(lower, "/backend-adapter.ts"), strings.HasSuffix(lower, "/backend_adapter.go"), strings.HasSuffix(lower, "/backendadapter.java"), strings.HasSuffix(lower, "/backendadapter.cs"):
		return "backend_adapter"
	case strings.HasSuffix(lower, "/policy.py"), strings.HasSuffix(lower, "/policy.ts"), strings.HasSuffix(lower, "/policy.go"), strings.HasSuffix(lower, "/policy.java"), strings.HasSuffix(lower, "/policy.cs"):
		return "policy"
	case strings.HasSuffix(lower, "/app.py"), strings.HasSuffix(lower, "/app.ts"), strings.HasSuffix(lower, "/app.go"), strings.HasSuffix(lower, "/application.java"), strings.HasSuffix(lower, "/program.cs"):
		return "application_entrypoint"
	default:
		return "custom_file"
	}
}

func upsertGeneratedFile(project *GeneratedProject, file GeneratedFile) {
	normalizedPath := filepath.ToSlash(filepath.Clean(file.Path))
	for index := range project.Files {
		if filepath.ToSlash(filepath.Clean(project.Files[index].Path)) == normalizedPath {
			project.Files[index] = GeneratedFile{Path: normalizedPath, Content: file.Content}
			return
		}
	}
	project.Files = append(project.Files, GeneratedFile{Path: normalizedPath, Content: file.Content})
}
