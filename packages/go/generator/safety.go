package generator

import (
	"fmt"
	"regexp"
	"strings"
)

var (
	npmPackageNamePattern     = regexp.MustCompile(`^(?:@[a-z0-9][a-z0-9._-]{0,213}/)?[a-z0-9][a-z0-9._-]{0,213}$`)
	pythonDistributionPattern = regexp.MustCompile(`^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,126}[A-Za-z0-9])?$`)
	pythonModulePattern       = regexp.MustCompile(`^[A-Za-z_][A-Za-z0-9_]{0,127}$`)
	goModulePathPattern       = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9._~-]*(?:/[A-Za-z0-9][A-Za-z0-9._~-]*)+$`)
	mavenArtifactPattern      = regexp.MustCompile(`^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,126}[A-Za-z0-9])?$`)
	javaPackagePattern        = regexp.MustCompile(`^[a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)+$`)
	csharpProjectPattern      = regexp.MustCompile(`^[A-Za-z][A-Za-z0-9_.-]{0,127}$`)
	csharpNamespacePattern    = regexp.MustCompile(`^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$`)
)

func validateDependencySource(value DependencySource) error {
	switch value {
	case DependencySourceRegistry, DependencySourceLocal:
		return nil
	default:
		return fmt.Errorf("unsupported dependency source %q", value)
	}
}

func validateGeneratedPort(port int) error {
	if port < 1 || port > 65535 {
		return fmt.Errorf("port must be between 1 and 65535")
	}
	return nil
}

func validateNpmPackageName(name string) error {
	if !npmPackageNamePattern.MatchString(name) || strings.Contains(name, "..") {
		return fmt.Errorf("package name is invalid")
	}
	return nil
}

func validatePythonProjectName(name string) error {
	if !pythonDistributionPattern.MatchString(name) || strings.Contains(name, "..") {
		return fmt.Errorf("python project name is invalid")
	}
	return nil
}

func validatePythonModuleName(name string) error {
	if !pythonModulePattern.MatchString(name) {
		return fmt.Errorf("python module name is invalid")
	}
	return nil
}

func validateGoModulePath(modulePath string) error {
	if !goModulePathPattern.MatchString(modulePath) || strings.Contains(modulePath, "..") {
		return fmt.Errorf("go module path is invalid")
	}
	return nil
}

func validateMavenArtifactID(artifactID string) error {
	if !mavenArtifactPattern.MatchString(artifactID) || strings.Contains(artifactID, "..") {
		return fmt.Errorf("java artifact id is invalid")
	}
	return nil
}

func validateJavaPackageName(packageName string) error {
	if !javaPackagePattern.MatchString(packageName) {
		return fmt.Errorf("java package name is invalid")
	}
	return nil
}

func validateCSharpProjectName(projectName string) error {
	if !csharpProjectPattern.MatchString(projectName) || strings.Contains(projectName, "..") {
		return fmt.Errorf("csharp project name is invalid")
	}
	return nil
}

func validateCSharpNamespace(rootNamespace string) error {
	if !csharpNamespacePattern.MatchString(rootNamespace) {
		return fmt.Errorf("csharp root namespace is invalid")
	}
	return nil
}
