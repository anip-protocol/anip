package generator

import (
	"fmt"
	"path/filepath"
	"regexp"
	"strings"
)

type ContainerArtifactOptions struct {
	Dockerfile    bool
	DockerCompose bool
	Port          int
}

func BuildContainerArtifacts(target string, project *GeneratedProject, options ContainerArtifactOptions) ([]GeneratedFile, error) {
	if !options.Dockerfile && !options.DockerCompose {
		return nil, nil
	}
	if project == nil {
		return nil, fmt.Errorf("generated project is required")
	}
	if options.Port == 0 {
		options.Port = defaultGeneratorPort
	}
	if err := validateGeneratedPort(options.Port); err != nil {
		return nil, err
	}
	switch target {
	case "python":
		moduleName := generatedPythonModuleName(project)
		if err := validatePythonModuleName(moduleName); err != nil {
			return nil, err
		}
		if len(project.Services) > 1 {
			return buildGeneratedPythonMultiServiceContainerArtifacts(project, moduleName, options), nil
		}
		files := []GeneratedFile{}
		if options.Dockerfile {
			files = append(files, GeneratedFile{Path: "Dockerfile", Content: buildGeneratedPythonDockerfile(moduleName+".app", options.Port)})
		}
		if options.DockerCompose {
			files = append(files, GeneratedFile{Path: "docker-compose.yml", Content: buildGeneratedSingleServiceCompose(options.Port)})
		}
		return files, nil
	default:
		return nil, fmt.Errorf("container artifact generation is not implemented for target %q", target)
	}
}

func generatedPythonModuleName(project *GeneratedProject) string {
	if moduleName := pythonProjectModuleName(project); moduleName != "" && generatedProjectHasFile(project, filepath.ToSlash(filepath.Join("src", moduleName, "app.py"))) {
		return moduleName
	}
	for _, file := range project.Files {
		path := filepath.ToSlash(filepath.Clean(file.Path))
		if strings.HasPrefix(path, "src/") && strings.HasSuffix(path, "/app.py") {
			parts := strings.Split(path, "/")
			if len(parts) >= 3 && strings.TrimSpace(parts[1]) != "" {
				return parts[1]
			}
		}
	}
	return pythonModuleName(project.SystemName)
}

func pythonProjectModuleName(project *GeneratedProject) string {
	if project == nil {
		return ""
	}
	projectNamePattern := regexp.MustCompile(`(?m)^name\s*=\s*"([^"]+)"`)
	for _, file := range project.Files {
		if filepath.ToSlash(filepath.Clean(file.Path)) != "pyproject.toml" {
			continue
		}
		match := projectNamePattern.FindStringSubmatch(file.Content)
		if len(match) == 2 {
			return pythonModuleName(match[1])
		}
	}
	return ""
}

func generatedProjectHasFile(project *GeneratedProject, path string) bool {
	normalized := filepath.ToSlash(filepath.Clean(path))
	for _, file := range project.Files {
		if filepath.ToSlash(filepath.Clean(file.Path)) == normalized {
			return true
		}
	}
	return false
}

// EnsurePythonCustomModuleSupport lets a custom Python bundle provide the app
// entrypoint while still consuming generated contract/runtime support modules.
func EnsurePythonCustomModuleSupport(project *GeneratedProject) int {
	if project == nil {
		return 0
	}
	customModule := pythonProjectModuleName(project)
	if customModule == "" {
		return 0
	}
	sourceModule := ""
	for _, file := range project.Files {
		path := filepath.ToSlash(filepath.Clean(file.Path))
		if !strings.HasPrefix(path, "src/") || !strings.HasSuffix(path, "/runtime_target.py") {
			continue
		}
		parts := strings.Split(path, "/")
		if len(parts) >= 3 && parts[1] != customModule {
			sourceModule = parts[1]
			break
		}
	}
	if sourceModule == "" {
		return 0
	}
	copied := 0
	for _, filename := range []string{"__init__.py", "runtime_target.py", "backend_adapter.py", "policy.py", "capabilities.py"} {
		sourcePath := filepath.ToSlash(filepath.Join("src", sourceModule, filename))
		targetPath := filepath.ToSlash(filepath.Join("src", customModule, filename))
		if generatedProjectHasFile(project, targetPath) {
			continue
		}
		if content, ok := generatedProjectFileContent(project, sourcePath); ok {
			upsertGeneratedFile(project, GeneratedFile{Path: targetPath, Content: content})
			copied++
		}
	}
	for _, file := range append([]GeneratedFile(nil), project.Files...) {
		sourcePath := filepath.ToSlash(filepath.Clean(file.Path))
		sourcePrefix := filepath.ToSlash(filepath.Join("src", sourceModule, "services")) + "/"
		if !strings.HasPrefix(sourcePath, sourcePrefix) {
			continue
		}
		targetPath := filepath.ToSlash(filepath.Join("src", customModule, "services", strings.TrimPrefix(sourcePath, sourcePrefix)))
		if generatedProjectHasFile(project, targetPath) {
			continue
		}
		upsertGeneratedFile(project, GeneratedFile{Path: targetPath, Content: file.Content})
		copied++
	}
	return copied
}

func generatedProjectFileContent(project *GeneratedProject, path string) (string, bool) {
	normalized := filepath.ToSlash(filepath.Clean(path))
	for _, file := range project.Files {
		if filepath.ToSlash(filepath.Clean(file.Path)) == normalized {
			return file.Content, true
		}
	}
	return "", false
}

func buildGeneratedPythonDockerfile(moduleName string, port int) string {
	if port == 0 {
		port = defaultGeneratorPort
	}
	return strings.Join([]string{
		"FROM python:3.12-slim",
		"",
		"ENV PYTHONDONTWRITEBYTECODE=1",
		"ENV PYTHONUNBUFFERED=1",
		"ENV PYTHONPATH=/app/src",
		fmt.Sprintf("ENV PORT=%d", port),
		"",
		"WORKDIR /app",
		"COPY . /app",
		"RUN python -m pip install --no-cache-dir --upgrade pip && python -m pip install --no-cache-dir .",
		"",
		fmt.Sprintf("EXPOSE %d", port),
		fmt.Sprintf("CMD [\"python\", \"-m\", \"%s\"]", moduleName),
		"",
	}, "\n")
}

func buildGeneratedPythonMultiServiceContainerArtifacts(project *GeneratedProject, rootModuleName string, options ContainerArtifactOptions) []GeneratedFile {
	files := []GeneratedFile{}
	if options.Dockerfile {
		for index, service := range project.Services {
			moduleName := pythonServiceEntrypointModule(rootModuleName, service.ServiceID, index)
			dockerfilePath := filepath.ToSlash(filepath.Join("services", pythonModuleName(service.ServiceID), "Dockerfile"))
			files = append(files, GeneratedFile{Path: dockerfilePath, Content: buildGeneratedPythonDockerfile(moduleName, options.Port)})
		}
	}
	if options.DockerCompose {
		files = append(files, GeneratedFile{Path: "docker-compose.yml", Content: buildGeneratedPythonMultiServiceCompose(project, rootModuleName, options.Port)})
	}
	return files
}

func pythonServiceEntrypointModule(rootModuleName, serviceID string, index int) string {
	if index == 0 {
		return rootModuleName + ".app"
	}
	serviceModule := pythonModuleName(serviceID)
	if err := validatePythonModuleName(serviceModule); err != nil {
		serviceModule = "service_" + fmt.Sprintf("%d", index)
	}
	return rootModuleName + ".services." + serviceModule + ".app"
}

func buildGeneratedPythonMultiServiceCompose(project *GeneratedProject, rootModuleName string, port int) string {
	if port == 0 {
		port = defaultGeneratorPort
	}
	lines := []string{"services:"}
	for index, service := range project.Services {
		serviceName := dockerComposeServiceName(service.ServiceID)
		imageName := dockerImageName(project.PackageName + "-" + service.ServiceID)
		dockerfilePath := filepath.ToSlash(filepath.Join("services", pythonModuleName(service.ServiceID), "Dockerfile"))
		hostPort := port + index
		lines = append(lines,
			fmt.Sprintf("  %s:", serviceName),
			"    build:",
			"      context: .",
			fmt.Sprintf("      dockerfile: %s", dockerfilePath),
			fmt.Sprintf("    image: %s", imageName),
			fmt.Sprintf("    ports: [\"%d:%d\"]", hostPort, port),
			"    environment:",
			fmt.Sprintf("      PORT: \"%d\"", port),
			fmt.Sprintf("      ANIP_SERVICE_ID: %q", service.ServiceID),
		)
		if index < len(project.Services)-1 {
			lines = append(lines, "")
		}
	}
	lines = append(lines, "")
	_ = rootModuleName
	return strings.Join(lines, "\n")
}

func dockerComposeServiceName(value string) string {
	name := strings.Trim(strings.ToLower(value), "-_ .")
	name = strings.NewReplacer("_", "-", " ", "-", ".", "-").Replace(name)
	if name == "" {
		return "anip-service"
	}
	var builder strings.Builder
	for _, r := range name {
		if (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9') || r == '-' {
			builder.WriteRune(r)
		}
	}
	result := strings.Trim(builder.String(), "-")
	if result == "" {
		return "anip-service"
	}
	return result
}

func dockerImageName(value string) string {
	name := dockerComposeServiceName(value)
	if name == "" {
		return "generated-anip-service"
	}
	return name
}

func buildGeneratedSingleServiceCompose(port int) string {
	if port == 0 {
		port = defaultGeneratorPort
	}
	return strings.Join([]string{
		"services:",
		"  anip-service:",
		"    build: .",
		fmt.Sprintf("    ports: [\"%d:%d\"]", port, port),
		"    environment:",
		fmt.Sprintf("      PORT: \"%d\"", port),
		"",
	}, "\n")
}
