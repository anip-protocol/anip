package generator

import (
	"strings"
	"testing"
)

func TestBuildJavaProject(t *testing.T) {
	definition := mustReadFixtureDefinition(t)

	project, err := BuildJavaProject(definition, BuildJavaProjectOptions{
		DependencySource: DependencySourceLocal,
		Port:             4100,
	})
	if err != nil {
		t.Fatalf("BuildJavaProject: %v", err)
	}

	assertHasFile(t, project.Files, "pom.xml")
	assertHasFile(t, project.Files, "src/main/resources/application.properties")
	assertHasFile(t, project.Files, "src/main/java/dev/anip/generated/work_item_governance_service/Application.java")
	assertHasFile(t, project.Files, "src/main/java/dev/anip/generated/work_item_governance_service/GeneratedCapabilities.java")
	assertHasFile(t, project.Files, "src/main/java/dev/anip/generated/work_item_governance_service/GeneratedRuntimeTarget.java")
	assertHasFile(t, project.Files, "src/test/java/dev/anip/generated/work_item_governance_service/GeneratedCapabilitiesTest.java")

	pom := fileContent(project.Files, "pom.xml")
	if !strings.Contains(pom, "<artifactId>work-item-governance-service</artifactId>") {
		t.Fatalf("pom missing generated artifact id")
	}
	if !strings.Contains(pom, "build-helper-maven-plugin") {
		t.Fatalf("pom missing local Java source root plugin")
	}

	runtimeModule := fileContent(project.Files, "src/main/java/dev/anip/generated/work_item_governance_service/GeneratedRuntimeTarget.java")
	if !strings.Contains(runtimeModule, "work_item.prepare_update") {
		t.Fatalf("generated runtime target missing expected capability id")
	}
	if !containsGeneratedMarker(runtimeModule, `"backend_input_mode": "hybrid"`) {
		t.Fatalf("generated runtime target missing hybrid backend input mode")
	}
	app := fileContent(project.Files, "src/main/java/dev/anip/generated/work_item_governance_service/Application.java")
	if !strings.Contains(app, "ANIP_API_KEYS_JSON") {
		t.Fatalf("generated app should support environment-provided API key mappings")
	}
	if !strings.Contains(app, "ANIP_SERVICE_FILTER") {
		t.Fatalf("generated app should support service-slice capability filtering")
	}
	capabilities := fileContent(project.Files, "src/main/java/dev/anip/generated/work_item_governance_service/GeneratedCapabilities.java")
	if !strings.Contains(capabilities, "createAll(BackendAdapter backendAdapter, String serviceFilter)") {
		t.Fatalf("generated capabilities should expose service-filtered creation")
	}
	if !strings.Contains(capabilities, "declarationKind(capability)") || !strings.Contains(capabilities, "declarationComposition(capability)") {
		t.Fatalf("generated capabilities should preserve composed declarations consistently")
	}
	for _, forbidden := range []string{
		"ANIP_OPTIONAL_INPUT_OVERRIDES_JSON",
		"ANIP_COMPOSED_CAPABILITY_BRIDGE",
		"ANIP_BRIDGE_COMPOSED_CAPABILITIES",
	} {
		if strings.Contains(capabilities, forbidden) {
			t.Fatalf("generated capabilities should not expose declaration mutation hook %q", forbidden)
		}
	}
}

func TestBuildJavaProjectRegistryDependencies(t *testing.T) {
	definition := mustReadFixtureDefinition(t)

	project, err := BuildJavaProject(definition, BuildJavaProjectOptions{
		DependencySource: DependencySourceRegistry,
		Port:             4100,
	})
	if err != nil {
		t.Fatalf("BuildJavaProject: %v", err)
	}

	pom := fileContent(project.Files, "pom.xml")
	for _, expected := range []string{
		"<groupId>dev.anip</groupId>",
		"<artifactId>anip-core</artifactId>",
		"<artifactId>anip-crypto</artifactId>",
		"<artifactId>anip-server</artifactId>",
		"<artifactId>anip-service</artifactId>",
		"<artifactId>anip-spring-boot</artifactId>",
		"<anip.version>0.24.5</anip.version>",
	} {
		if !strings.Contains(pom, expected) {
			t.Fatalf("registry pom missing %q", expected)
		}
	}
	if strings.Contains(pom, "build-helper-maven-plugin") {
		t.Fatalf("registry pom should not add local Java source roots")
	}

	readme := fileContent(project.Files, "README.md")
	if strings.Contains(readme, "after ANIP Java runtime packages are published") {
		t.Fatalf("registry readme still describes Java packages as unpublished")
	}
}

func TestBuildJavaProjectQuarkusFramework(t *testing.T) {
	definition := mustReadFixtureDefinition(t)

	project, err := BuildJavaProject(definition, BuildJavaProjectOptions{
		DependencySource: DependencySourceLocal,
		Framework:        JavaFrameworkQuarkus,
		Port:             4100,
	})
	if err != nil {
		t.Fatalf("BuildJavaProject: %v", err)
	}
	if project.Framework != "quarkus" {
		t.Fatalf("expected quarkus framework metadata, got %q", project.Framework)
	}

	pom := fileContent(project.Files, "pom.xml")
	for _, expected := range []string{
		"packages/java/anip-quarkus/src/main/java",
		"<artifactId>quarkus-rest-jackson</artifactId>",
		"<artifactId>quarkus-maven-plugin</artifactId>",
		"<quarkus.version>3.17.8</quarkus.version>",
	} {
		if !strings.Contains(pom, expected) {
			t.Fatalf("quarkus pom missing %q", expected)
		}
	}
	if strings.Contains(pom, "spring-boot-starter") || strings.Contains(pom, "spring-boot-maven-plugin") {
		t.Fatalf("quarkus pom should not include Spring Boot runtime dependencies")
	}

	properties := fileContent(project.Files, "src/main/resources/application.properties")
	if !strings.Contains(properties, "quarkus.http.port=4100") || strings.Contains(properties, "server.port") {
		t.Fatalf("quarkus application.properties should use quarkus HTTP settings: %s", properties)
	}

	app := fileContent(project.Files, "src/main/java/dev/anip/generated/work_item_governance_service/Application.java")
	for _, expected := range []string{
		"import jakarta.enterprise.context.ApplicationScoped;",
		"import jakarta.enterprise.inject.Produces;",
		"public ANIPService anipService(BackendAdapter backendAdapter)",
		"ANIP_SERVICE_FILTER",
	} {
		if !strings.Contains(app, expected) {
			t.Fatalf("quarkus application module missing %q", expected)
		}
	}
	if strings.Contains(app, "SpringApplication") || strings.Contains(app, "AnipController") {
		t.Fatalf("quarkus application module should not wire Spring Boot classes")
	}

	readme := fileContent(project.Files, "README.md")
	if !strings.Contains(readme, "--framework quarkus") || !strings.Contains(readme, "mvn quarkus:dev") {
		t.Fatalf("quarkus readme missing framework command guidance")
	}
}

func TestJavaStringJoinExpressionEscapesEmbeddedJSON(t *testing.T) {
	expression := javaStringJoinExpression(`{"note":"Studio mapped \"\u003crequires_clarification\u003e\" safely."}`)
	if strings.Contains(expression, `"""`) {
		t.Fatalf("embedded JSON should use escaped string literals, not Java text blocks: %s", expression)
	}
	if !strings.Contains(expression, `\\\"`) {
		t.Fatalf("embedded JSON should preserve escaped JSON quotes: %s", expression)
	}
	if !strings.Contains(expression, `\\u003c`) {
		t.Fatalf("embedded JSON should preserve unicode escapes without Java source preprocessing: %s", expression)
	}
}
