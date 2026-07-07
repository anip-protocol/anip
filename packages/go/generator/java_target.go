package generator

import (
	"fmt"
	"path/filepath"
	"runtime"
	"strings"
)

const (
	anipJavaPackageVersion = "0.24.13"
	springBootVersion      = "3.4.3"
	quarkusVersion         = "3.17.8"
)

func BuildJavaProject(definition *AnipServiceDefinition, options BuildJavaProjectOptions) (*GeneratedProject, error) {
	model, err := BuildGenerationModel(definition)
	if err != nil {
		return nil, err
	}
	if options.DependencySource == "" {
		options.DependencySource = DependencySourceRegistry
	}
	if options.Framework == "" {
		options.Framework = JavaFrameworkSpringBoot
	}
	transports, err := normalizeTransports(options.Transports)
	if err != nil {
		return nil, err
	}
	if options.Port == 0 {
		options.Port = defaultGeneratorPort
	}

	artifactID := strings.TrimSpace(options.ArtifactID)
	if artifactID == "" {
		artifactID = systemNameToPackageName(model.SystemName)
	}
	rawPackageName := strings.TrimSpace(options.PackageName)
	packageName := rawPackageName
	if rawPackageName == "" {
		packageName = javaPackageName(artifactID)
	} else if strings.Contains(rawPackageName, ".") {
		packageName = rawPackageName
	} else {
		if err := validateMavenArtifactID(rawPackageName); err != nil {
			return nil, fmt.Errorf("java package name is invalid")
		}
		packageName = javaPackageName(rawPackageName)
	}
	if err := validateDependencySource(options.DependencySource); err != nil {
		return nil, err
	}
	if err := validateJavaFramework(options.Framework); err != nil {
		return nil, err
	}
	if err := validateGeneratedPort(options.Port); err != nil {
		return nil, err
	}
	if err := validateMavenArtifactID(artifactID); err != nil {
		return nil, err
	}
	if err := validateJavaPackageName(packageName); err != nil {
		return nil, err
	}

	mainJavaBase := filepath.ToSlash(filepath.Join("src", "main", "java", filepath.FromSlash(strings.ReplaceAll(packageName, ".", "/"))))
	testJavaBase := filepath.ToSlash(filepath.Join("src", "test", "java", filepath.FromSlash(strings.ReplaceAll(packageName, ".", "/"))))

	contractVersion := fallbackString(definition.ContractSchemaVersion, "generated-1")

	files := []GeneratedFile{
		{Path: "pom.xml", Content: buildGeneratedJavaAppPom(artifactID, options.DependencySource, options.Framework, transports)},
		{Path: "README.md", Content: buildGeneratedJavaReadme(model.SystemName, options.DependencySource, options.Framework, transports)},
		{Path: "anip-service-definition.json", Content: string(model.DefinitionJSON)},
	}
	appPrefix := ""
	files = append(files,
		GeneratedFile{Path: filepath.ToSlash(filepath.Join(appPrefix, "src", "main", "resources", "application.properties")), Content: buildGeneratedJavaApplicationProperties(options.Port, options.Framework)},
		GeneratedFile{Path: filepath.ToSlash(filepath.Join(appPrefix, mainJavaBase, "Application.java")), Content: buildGeneratedJavaApplicationModule(packageName, model.SystemName, options.Framework)},
		GeneratedFile{Path: filepath.ToSlash(filepath.Join(appPrefix, mainJavaBase, "GeneratedRuntimeTarget.java")), Content: buildGeneratedJavaRuntimeTargetModule(packageName, string(model.RuntimeTargetJSON), string(model.CapabilitiesJSON), contractVersion)},
		GeneratedFile{Path: filepath.ToSlash(filepath.Join(appPrefix, mainJavaBase, "BackendAdapter.java")), Content: buildGeneratedJavaBackendAdapterModule(packageName)},
		GeneratedFile{Path: filepath.ToSlash(filepath.Join(appPrefix, mainJavaBase, "Policy.java")), Content: buildGeneratedJavaPolicyModule(packageName)},
		GeneratedFile{Path: filepath.ToSlash(filepath.Join(appPrefix, mainJavaBase, "GeneratedCapabilities.java")), Content: buildGeneratedJavaCapabilitiesModule(packageName)},
		GeneratedFile{Path: filepath.ToSlash(filepath.Join(appPrefix, testJavaBase, "GeneratedCapabilitiesTest.java")), Content: buildGeneratedJavaSmokeTestModule(packageName, firstGeneratedCapabilityID(model))},
	)
	if hasTransport(transports, TransportStdio) {
		files = append(files, GeneratedFile{Path: filepath.ToSlash(filepath.Join(appPrefix, mainJavaBase, "StdioMain.java")), Content: buildGeneratedJavaStdioMainModule(packageName, model.SystemName)})
	}
	files = append(files, buildIntegrationFrontingArtifacts(model)...)

	project := &GeneratedProject{
		PackageName: artifactID,
		SystemName:  model.SystemName,
		Framework:   string(options.Framework),
		Transports:  TransportNames(transports),
		Files:       files,
		CustomBundleTemplateValues: map[string]string{
			"JAVA_PACKAGE_NAME": packageName,
			"JAVA_PACKAGE_PATH": strings.ReplaceAll(packageName, ".", "/"),
		},
	}
	return project, nil
}

func buildGeneratedJavaAppPom(artifactID string, dependencySource DependencySource, framework JavaFramework, transports []Transport) string {
	if framework == JavaFrameworkQuarkus {
		return buildGeneratedJavaQuarkusAppPom(artifactID, dependencySource, transports)
	}
	return buildGeneratedJavaSpringBootAppPom(artifactID, dependencySource, transports)
}

func buildGeneratedJavaSpringBootAppPom(artifactID string, dependencySource DependencySource, transports []Transport) string {
	lines := []string{
		`<project xmlns="http://maven.apache.org/POM/4.0.0"`,
		`         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"`,
		`         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">`,
		`    <modelVersion>4.0.0</modelVersion>`,
		"",
		`    <parent>`,
		`        <groupId>org.springframework.boot</groupId>`,
		`        <artifactId>spring-boot-starter-parent</artifactId>`,
		`        <version>` + springBootVersion + `</version>`,
		`        <relativePath/>`,
		`    </parent>`,
		"",
		`    <groupId>dev.anip.generated</groupId>`,
		`    <artifactId>` + artifactID + `</artifactId>`,
		`    <version>0.1.0</version>`,
		`    <name>` + titleCase(strings.NewReplacer("-", " ", "_", " ").Replace(artifactID)) + `</name>`,
		`    <description>Generated ANIP Java host</description>`,
		"",
		`    <properties>`,
		`        <java.version>17</java.version>`,
		`        <anip.version>` + anipJavaPackageVersion + `</anip.version>`,
		`    </properties>`,
		"",
	}
	lines = append(lines, `    <dependencies>`)
	if dependencySource != DependencySourceLocal {
		lines = append(lines,
			`        <dependency>`,
			`            <groupId>dev.anip</groupId>`,
			`            <artifactId>anip-core</artifactId>`,
			`            <version>${anip.version}</version>`,
			`        </dependency>`,
			`        <dependency>`,
			`            <groupId>dev.anip</groupId>`,
			`            <artifactId>anip-crypto</artifactId>`,
			`            <version>${anip.version}</version>`,
			`        </dependency>`,
			`        <dependency>`,
			`            <groupId>dev.anip</groupId>`,
			`            <artifactId>anip-server</artifactId>`,
			`            <version>${anip.version}</version>`,
			`        </dependency>`,
			`        <dependency>`,
			`            <groupId>dev.anip</groupId>`,
			`            <artifactId>anip-service</artifactId>`,
			`            <version>${anip.version}</version>`,
			`        </dependency>`,
			`        <dependency>`,
			`            <groupId>dev.anip</groupId>`,
			`            <artifactId>anip-spring-boot</artifactId>`,
			`            <version>${anip.version}</version>`,
			`        </dependency>`,
		)
	} else {
		lines = append(lines,
			`        <dependency>`,
			`            <groupId>com.fasterxml.jackson.core</groupId>`,
			`            <artifactId>jackson-databind</artifactId>`,
			`            <version>2.18.2</version>`,
			`        </dependency>`,
			`        <dependency>`,
			`            <groupId>com.fasterxml.jackson.module</groupId>`,
			`            <artifactId>jackson-module-parameter-names</artifactId>`,
			`            <version>2.18.2</version>`,
			`        </dependency>`,
			`        <dependency>`,
			`            <groupId>com.nimbusds</groupId>`,
			`            <artifactId>nimbus-jose-jwt</artifactId>`,
			`            <version>9.47</version>`,
			`        </dependency>`,
			`        <dependency>`,
			`            <groupId>org.xerial</groupId>`,
			`            <artifactId>sqlite-jdbc</artifactId>`,
			`            <version>3.47.2.0</version>`,
			`        </dependency>`,
			`        <dependency>`,
			`            <groupId>com.zaxxer</groupId>`,
			`            <artifactId>HikariCP</artifactId>`,
			`            <version>6.2.1</version>`,
			`        </dependency>`,
			`        <dependency>`,
			`            <groupId>org.postgresql</groupId>`,
			`            <artifactId>postgresql</artifactId>`,
			`            <version>42.7.5</version>`,
			`        </dependency>`,
		)
	}
	if hasTransport(transports, TransportStdio) && dependencySource != DependencySourceLocal {
		lines = append(lines,
			`        <dependency>`,
			`            <groupId>dev.anip</groupId>`,
			`            <artifactId>anip-stdio</artifactId>`,
			`            <version>${anip.version}</version>`,
			`        </dependency>`,
		)
	}
	lines = append(lines,
		`        <dependency>`,
		`            <groupId>org.springframework.boot</groupId>`,
		`            <artifactId>spring-boot-starter-web</artifactId>`,
		`        </dependency>`,
		`        <dependency>`,
		`            <groupId>org.springframework.boot</groupId>`,
		`            <artifactId>spring-boot-starter-test</artifactId>`,
		`            <scope>test</scope>`,
		`        </dependency>`,
		`    </dependencies>`,
		"",
		`    <build>`,
		`        <plugins>`,
	)
	if dependencySource == DependencySourceLocal {
		lines = append(lines,
			`            <plugin>`,
			`                <groupId>org.codehaus.mojo</groupId>`,
			`                <artifactId>build-helper-maven-plugin</artifactId>`,
			`                <version>3.6.0</version>`,
			`                <executions>`,
			`                    <execution>`,
			`                        <id>add-local-anip-sources</id>`,
			`                        <phase>generate-sources</phase>`,
			`                        <goals><goal>add-source</goal></goals>`,
			`                        <configuration>`,
			`                            <sources>`,
		)
		for _, sourcePath := range localJavaSourcePaths(JavaFrameworkSpringBoot) {
			lines = append(lines, `                                <source>`+sourcePath+`</source>`)
		}
		lines = append(lines,
			`                            </sources>`,
			`                        </configuration>`,
			`                    </execution>`,
			`                </executions>`,
			`            </plugin>`,
		)
	}
	lines = append(lines,
		`            <plugin>`,
		`                <groupId>org.springframework.boot</groupId>`,
		`                <artifactId>spring-boot-maven-plugin</artifactId>`,
		`            </plugin>`,
		`        </plugins>`,
		`    </build>`,
		`</project>`,
		"",
	)
	return strings.Join(lines, "\n")
}

func buildGeneratedJavaQuarkusAppPom(artifactID string, dependencySource DependencySource, transports []Transport) string {
	lines := []string{
		`<project xmlns="http://maven.apache.org/POM/4.0.0"`,
		`         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"`,
		`         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">`,
		`    <modelVersion>4.0.0</modelVersion>`,
		"",
		`    <groupId>dev.anip.generated</groupId>`,
		`    <artifactId>` + artifactID + `</artifactId>`,
		`    <version>0.1.0</version>`,
		`    <name>` + titleCase(strings.NewReplacer("-", " ", "_", " ").Replace(artifactID)) + `</name>`,
		`    <description>Generated ANIP Java Quarkus host</description>`,
		"",
		`    <properties>`,
		`        <maven.compiler.release>17</maven.compiler.release>`,
		`        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>`,
		`        <anip.version>` + anipJavaPackageVersion + `</anip.version>`,
		`        <quarkus.version>` + quarkusVersion + `</quarkus.version>`,
		`        <junit.version>5.11.4</junit.version>`,
		`    </properties>`,
		"",
		`    <dependencyManagement>`,
		`        <dependencies>`,
		`            <dependency>`,
		`                <groupId>io.quarkus.platform</groupId>`,
		`                <artifactId>quarkus-bom</artifactId>`,
		`                <version>${quarkus.version}</version>`,
		`                <type>pom</type>`,
		`                <scope>import</scope>`,
		`            </dependency>`,
		`        </dependencies>`,
		`    </dependencyManagement>`,
		"",
		`    <dependencies>`,
	}
	if dependencySource != DependencySourceLocal {
		lines = append(lines,
			`        <dependency>`,
			`            <groupId>dev.anip</groupId>`,
			`            <artifactId>anip-core</artifactId>`,
			`            <version>${anip.version}</version>`,
			`        </dependency>`,
			`        <dependency>`,
			`            <groupId>dev.anip</groupId>`,
			`            <artifactId>anip-crypto</artifactId>`,
			`            <version>${anip.version}</version>`,
			`        </dependency>`,
			`        <dependency>`,
			`            <groupId>dev.anip</groupId>`,
			`            <artifactId>anip-server</artifactId>`,
			`            <version>${anip.version}</version>`,
			`        </dependency>`,
			`        <dependency>`,
			`            <groupId>dev.anip</groupId>`,
			`            <artifactId>anip-service</artifactId>`,
			`            <version>${anip.version}</version>`,
			`        </dependency>`,
			`        <dependency>`,
			`            <groupId>dev.anip</groupId>`,
			`            <artifactId>anip-quarkus</artifactId>`,
			`            <version>${anip.version}</version>`,
			`        </dependency>`,
		)
	} else {
		lines = append(lines,
			`        <dependency>`,
			`            <groupId>com.fasterxml.jackson.core</groupId>`,
			`            <artifactId>jackson-databind</artifactId>`,
			`            <version>2.18.2</version>`,
			`        </dependency>`,
			`        <dependency>`,
			`            <groupId>com.fasterxml.jackson.module</groupId>`,
			`            <artifactId>jackson-module-parameter-names</artifactId>`,
			`            <version>2.18.2</version>`,
			`        </dependency>`,
			`        <dependency>`,
			`            <groupId>com.nimbusds</groupId>`,
			`            <artifactId>nimbus-jose-jwt</artifactId>`,
			`            <version>9.47</version>`,
			`        </dependency>`,
			`        <dependency>`,
			`            <groupId>org.xerial</groupId>`,
			`            <artifactId>sqlite-jdbc</artifactId>`,
			`            <version>3.47.2.0</version>`,
			`        </dependency>`,
			`        <dependency>`,
			`            <groupId>com.zaxxer</groupId>`,
			`            <artifactId>HikariCP</artifactId>`,
			`            <version>6.2.1</version>`,
			`        </dependency>`,
			`        <dependency>`,
			`            <groupId>org.postgresql</groupId>`,
			`            <artifactId>postgresql</artifactId>`,
			`            <version>42.7.5</version>`,
			`        </dependency>`,
		)
	}
	if hasTransport(transports, TransportStdio) && dependencySource != DependencySourceLocal {
		lines = append(lines,
			`        <dependency>`,
			`            <groupId>dev.anip</groupId>`,
			`            <artifactId>anip-stdio</artifactId>`,
			`            <version>${anip.version}</version>`,
			`        </dependency>`,
		)
	}
	lines = append(lines,
		`        <dependency>`,
		`            <groupId>io.quarkus</groupId>`,
		`            <artifactId>quarkus-rest-jackson</artifactId>`,
		`        </dependency>`,
		`        <dependency>`,
		`            <groupId>io.quarkus</groupId>`,
		`            <artifactId>quarkus-arc</artifactId>`,
		`        </dependency>`,
		`        <dependency>`,
		`            <groupId>org.junit.jupiter</groupId>`,
		`            <artifactId>junit-jupiter</artifactId>`,
		`            <version>${junit.version}</version>`,
		`            <scope>test</scope>`,
		`        </dependency>`,
		`        <dependency>`,
		`            <groupId>io.quarkus</groupId>`,
		`            <artifactId>quarkus-junit5</artifactId>`,
		`            <scope>test</scope>`,
		`        </dependency>`,
		`    </dependencies>`,
		"",
		`    <build>`,
		`        <plugins>`,
	)
	if dependencySource == DependencySourceLocal {
		lines = append(lines,
			`            <plugin>`,
			`                <groupId>org.codehaus.mojo</groupId>`,
			`                <artifactId>build-helper-maven-plugin</artifactId>`,
			`                <version>3.6.0</version>`,
			`                <executions>`,
			`                    <execution>`,
			`                        <id>add-local-anip-sources</id>`,
			`                        <phase>generate-sources</phase>`,
			`                        <goals><goal>add-source</goal></goals>`,
			`                        <configuration>`,
			`                            <sources>`,
		)
		for _, sourcePath := range localJavaSourcePaths(JavaFrameworkQuarkus) {
			lines = append(lines, `                                <source>`+sourcePath+`</source>`)
		}
		lines = append(lines,
			`                            </sources>`,
			`                        </configuration>`,
			`                    </execution>`,
			`                </executions>`,
			`            </plugin>`,
		)
	}
	lines = append(lines,
		`            <plugin>`,
		`                <groupId>io.quarkus.platform</groupId>`,
		`                <artifactId>quarkus-maven-plugin</artifactId>`,
		`                <version>${quarkus.version}</version>`,
		`                <extensions>true</extensions>`,
		`            </plugin>`,
		`        </plugins>`,
		`    </build>`,
		`</project>`,
		"",
	)
	return strings.Join(lines, "\n")
}

func buildGeneratedJavaReadme(systemName string, dependencySource DependencySource, framework JavaFramework, transports []Transport) string {
	projectName := systemNameToPackageName(systemName)
	frameworkLabel := "Spring Boot"
	runtimePackage := "anip-spring-boot"
	runCommand := "mvn spring-boot:run"
	if framework == JavaFrameworkQuarkus {
		frameworkLabel = "Quarkus"
		runtimePackage = "anip-quarkus"
		runCommand = "mvn quarkus:dev"
	}
	lines := []string{
		"# " + titleCase(strings.NewReplacer("-", " ", "_", " ").Replace(systemName)),
		"",
		"Generated by `anip generate --target java --framework " + string(framework) + "` from an exported `anip-service-definition.json`.",
		"",
		"## What is generated",
		"",
		"- " + frameworkLabel + " ANIP host using `anip-service` and `" + runtimePackage + "`",
		"- generated capability declarations from the shared Go generation model",
		"- explicit backend adapter and policy seams for handwritten completion",
		"- generated runtime metadata and a smoke test scaffold",
		"",
		"## Commands",
		"",
	}
	if dependencySource == DependencySourceLocal {
		lines = append(lines,
			"- `mvn test`",
			"- `"+runCommand+"`",
		)
		if hasTransport(transports, TransportStdio) {
			lines = append(lines, "- `mvn exec:java -Dexec.mainClass="+javaPackageName(systemNameToPackageName(systemName))+".StdioMain`")
		}
		lines = append(lines,
			"",
			"## Local dependency mode",
			"",
			"`pom.xml` adds the repo's Java runtime source directories as local Maven source roots.",
			"",
		)
		return strings.Join(lines, "\n")
	}
	lines = append(lines,
		"- `mvn test`",
		"- `"+runCommand+"`",
		"Generated app artifact: `"+projectName+"`.",
		"",
	)
	if hasTransport(transports, TransportStdio) {
		lines = append(lines[:len(lines)-2], "- `mvn exec:java -Dexec.mainClass="+javaPackageName(systemNameToPackageName(systemName))+".StdioMain`", lines[len(lines)-2], lines[len(lines)-1])
	}
	return strings.Join(lines, "\n")
}

func buildGeneratedJavaApplicationProperties(port int, framework JavaFramework) string {
	if framework == JavaFrameworkQuarkus {
		return fmt.Sprintf("quarkus.http.host=0.0.0.0\nquarkus.http.port=%d\n", port)
	}
	return fmt.Sprintf("server.port=%d\n", port)
}

func buildGeneratedJavaApplicationModule(packageName, systemName string, framework JavaFramework) string {
	if framework == JavaFrameworkQuarkus {
		return buildGeneratedJavaQuarkusApplicationModule(packageName, systemName)
	}
	return buildGeneratedJavaSpringBootApplicationModule(packageName, systemName)
}

func buildGeneratedJavaStdioMainModule(packageName, systemName string) string {
	return strings.Join([]string{
		"package " + packageName + ";",
		"",
		"import dev.anip.service.ANIPService;",
		"import dev.anip.service.ServiceConfig;",
		"import dev.anip.stdio.AnipStdioServer;",
		"",
		"import java.util.Map;",
		"import java.util.Optional;",
		"",
		"public class StdioMain {",
		"    public static void main(String[] args) throws Exception {",
		"        String serviceId = System.getenv().getOrDefault(\"ANIP_SERVICE_ID\", \"" + systemName + "\");",
		"        String serviceFilter = System.getenv().getOrDefault(\"ANIP_SERVICE_FILTER\", serviceId);",
		"        Map<String, String> apiKeys = Map.of(",
		"                \"demo-human-key\", \"human:generated\",",
		"                \"demo-agent-key\", \"agent:generated-service\",",
		"                \"dev-admin-key\", \"human:local-developer\"",
		"        );",
		"        ANIPService service = new ANIPService(new ServiceConfig()",
		"                .setServiceId(serviceId)",
		"                .setCapabilities(GeneratedCapabilities.createAll(BackendAdapter.defaultAdapter(), serviceFilter))",
		"                .setStorage(System.getenv().getOrDefault(\"ANIP_STORAGE\", \":memory:\"))",
		"                .setTrust(System.getenv().getOrDefault(\"ANIP_TRUST_LEVEL\", \"signed\"))",
		"                .setKeyPath(System.getenv().getOrDefault(\"ANIP_KEY_PATH\", \"./anip-keys\"))",
		"                .setAuthenticate(bearer -> Optional.ofNullable(apiKeys.get(bearer))));",
		"        service.start();",
		"        try {",
		"            new AnipStdioServer(service).serve();",
		"        } finally {",
		"            service.shutdown();",
		"        }",
		"    }",
		"}",
		"",
	}, "\n")
}

func buildGeneratedJavaSpringBootApplicationModule(packageName, systemName string) string {
	return strings.Join([]string{
		"package " + packageName + ";",
		"",
		"import dev.anip.service.ANIPService;",
		"import dev.anip.service.ServiceConfig;",
		"import dev.anip.spring.AnipController;",
		"import dev.anip.spring.AnipLifecycle;",
		"",
		"import com.fasterxml.jackson.core.type.TypeReference;",
		"import com.fasterxml.jackson.databind.ObjectMapper;",
		"",
		"import org.springframework.boot.SpringApplication;",
		"import org.springframework.boot.autoconfigure.SpringBootApplication;",
		"import org.springframework.context.annotation.Bean;",
		"",
		"import java.util.LinkedHashMap;",
		"import java.util.Map;",
		"import java.util.Optional;",
		"",
		"@SpringBootApplication",
		"public class Application {",
		"",
		"    private static final ObjectMapper MAPPER = new ObjectMapper();",
		"",
		"    public static void main(String[] args) {",
		"        SpringApplication.run(Application.class, args);",
		"    }",
		"",
		"    @Bean",
		"    public BackendAdapter backendAdapter() {",
		"        return BackendAdapter.defaultAdapter();",
		"    }",
		"",
		"    @Bean",
		"    public ANIPService anipService(BackendAdapter backendAdapter) {",
		"        Map<String, String> apiKeys = apiKeys();",
		`        String serviceId = System.getenv().getOrDefault("ANIP_SERVICE_ID", "` + systemName + `");`,
		`        String serviceFilter = System.getenv().getOrDefault("ANIP_SERVICE_FILTER", serviceId);`,
		"",
		"        return new ANIPService(new ServiceConfig()",
		"                .setServiceId(serviceId)",
		"                .setCapabilities(GeneratedCapabilities.createAll(backendAdapter, serviceFilter))",
		`                .setStorage(System.getenv().getOrDefault("ANIP_STORAGE", ":memory:"))`,
		`                .setTrust(System.getenv().getOrDefault("ANIP_TRUST_LEVEL", "signed"))`,
		`                .setKeyPath(System.getenv().getOrDefault("ANIP_KEY_PATH", "./anip-keys"))`,
		"                .setAuthenticate(bearer -> Optional.ofNullable(apiKeys.get(bearer))));",
		"    }",
		"",
		"    private static Map<String, String> apiKeys() {",
		`        String raw = System.getenv("ANIP_API_KEYS_JSON");`,
		"        if (raw == null || raw.isBlank()) {",
		"            return Map.of(",
		`                    "demo-human-key", "human:generated",`,
		`                    "demo-agent-key", "agent:generated-service"`,
		"            );",
		"        }",
		"        try {",
		"            Map<String, Object> decoded = MAPPER.readValue(raw, new TypeReference<Map<String, Object>>() {});",
		"            Map<String, String> result = new LinkedHashMap<>();",
		"            for (Map.Entry<String, Object> entry : decoded.entrySet()) {",
		"                if (entry.getKey() != null && entry.getValue() != null) {",
		"                    result.put(entry.getKey(), String.valueOf(entry.getValue()));",
		"                }",
		"            }",
		`            return result.isEmpty() ? Map.of("demo-agent-key", "agent:generated-service") : result;`,
		"        } catch (Exception ignored) {",
		`            return Map.of("demo-agent-key", "agent:generated-service");`,
		"        }",
		"    }",
		"",
		"    @Bean",
		"    public AnipController anipController(ANIPService service) {",
		"        return new AnipController(service);",
		"    }",
		"",
		"    @Bean",
		"    public AnipLifecycle anipLifecycle(ANIPService service) {",
		"        return new AnipLifecycle(service);",
		"    }",
		"}",
		"",
	}, "\n")
}

func buildGeneratedJavaQuarkusApplicationModule(packageName, systemName string) string {
	return strings.Join([]string{
		"package " + packageName + ";",
		"",
		"import dev.anip.service.ANIPService;",
		"import dev.anip.service.ServiceConfig;",
		"",
		"import com.fasterxml.jackson.core.type.TypeReference;",
		"import com.fasterxml.jackson.databind.ObjectMapper;",
		"",
		"import jakarta.enterprise.context.ApplicationScoped;",
		"import jakarta.enterprise.inject.Produces;",
		"",
		"import java.util.LinkedHashMap;",
		"import java.util.Map;",
		"import java.util.Optional;",
		"",
		"@ApplicationScoped",
		"public class Application {",
		"",
		"    private static final ObjectMapper MAPPER = new ObjectMapper();",
		"",
		"    @Produces",
		"    @ApplicationScoped",
		"    public BackendAdapter backendAdapter() {",
		"        return BackendAdapter.defaultAdapter();",
		"    }",
		"",
		"    @Produces",
		"    @ApplicationScoped",
		"    public ANIPService anipService(BackendAdapter backendAdapter) {",
		"        Map<String, String> apiKeys = apiKeys();",
		`        String serviceId = System.getenv().getOrDefault("ANIP_SERVICE_ID", "` + systemName + `");`,
		`        String serviceFilter = System.getenv().getOrDefault("ANIP_SERVICE_FILTER", serviceId);`,
		"",
		"        return new ANIPService(new ServiceConfig()",
		"                .setServiceId(serviceId)",
		"                .setCapabilities(GeneratedCapabilities.createAll(backendAdapter, serviceFilter))",
		`                .setStorage(System.getenv().getOrDefault("ANIP_STORAGE", ":memory:"))`,
		`                .setTrust(System.getenv().getOrDefault("ANIP_TRUST_LEVEL", "signed"))`,
		`                .setKeyPath(System.getenv().getOrDefault("ANIP_KEY_PATH", "./anip-keys"))`,
		"                .setAuthenticate(bearer -> Optional.ofNullable(apiKeys.get(bearer))));",
		"    }",
		"",
		"    private static Map<String, String> apiKeys() {",
		`        String raw = System.getenv("ANIP_API_KEYS_JSON");`,
		"        if (raw == null || raw.isBlank()) {",
		"            return Map.of(",
		`                    "demo-human-key", "human:generated",`,
		`                    "demo-agent-key", "agent:generated-service"`,
		"            );",
		"        }",
		"        try {",
		"            Map<String, Object> decoded = MAPPER.readValue(raw, new TypeReference<Map<String, Object>>() {});",
		"            Map<String, String> result = new LinkedHashMap<>();",
		"            for (Map.Entry<String, Object> entry : decoded.entrySet()) {",
		"                if (entry.getKey() != null && entry.getValue() != null) {",
		"                    result.put(entry.getKey(), String.valueOf(entry.getValue()));",
		"                }",
		"            }",
		`            return result.isEmpty() ? Map.of("demo-agent-key", "agent:generated-service") : result;`,
		"        } catch (Exception ignored) {",
		`            return Map.of("demo-agent-key", "agent:generated-service");`,
		"        }",
		"    }",
		"}",
		"",
	}, "\n")
}

func buildGeneratedJavaRuntimeTargetModule(packageName, runtimeTargetJSON, capabilityMetadataJSON, contractVersion string) string {
	return strings.Join([]string{
		"package " + packageName + ";",
		"",
		"import com.fasterxml.jackson.core.type.TypeReference;",
		"import com.fasterxml.jackson.databind.ObjectMapper;",
		"",
		"import java.util.List;",
		"import java.util.Map;",
		"",
		"public final class GeneratedRuntimeTarget {",
		"",
		"    private static final ObjectMapper MAPPER = new ObjectMapper();",
		"    private static final String CONTRACT_VERSION = " + javaQuoted(contractVersion) + ";",
		"    private static final String RUNTIME_TARGET_JSON = " + javaStringJoinExpression(runtimeTargetJSON) + ";",
		"    private static final String CAPABILITY_METADATA_JSON = " + javaStringJoinExpression(capabilityMetadataJSON) + ";",
		"",
		"    private static final Map<String, Object> RUNTIME_TARGET = readRuntimeTarget();",
		"    private static final List<Map<String, Object>> CAPABILITIES = readCapabilities();",
		"",
		"    private GeneratedRuntimeTarget() {}",
		"",
		"    public static String contractVersion() {",
		"        return CONTRACT_VERSION;",
		"    }",
		"",
		"    public static Map<String, Object> runtimeTarget() {",
		"        return RUNTIME_TARGET;",
		"    }",
		"",
		"    public static List<Map<String, Object>> capabilities() {",
		"        return CAPABILITIES;",
		"    }",
		"",
		"    private static Map<String, Object> readRuntimeTarget() {",
		"        try {",
		"            return MAPPER.readValue(RUNTIME_TARGET_JSON, new TypeReference<Map<String, Object>>() {});",
		"        } catch (Exception error) {",
		`            throw new IllegalStateException("decode runtime target", error);`,
		"        }",
		"    }",
		"",
		"    private static List<Map<String, Object>> readCapabilities() {",
		"        try {",
		"            return MAPPER.readValue(CAPABILITY_METADATA_JSON, new TypeReference<List<Map<String, Object>>>() {});",
		"        } catch (Exception error) {",
		`            throw new IllegalStateException("decode capability metadata", error);`,
		"        }",
		"    }",
		"}",
		"",
	}, "\n")
}

func buildGeneratedJavaBackendAdapterModule(packageName string) string {
	return strings.Join([]string{
		"package " + packageName + ";",
		"",
		"import dev.anip.service.InvocationContext;",
		"",
		"import java.util.LinkedHashMap;",
		"import java.util.List;",
		"import java.util.Map;",
		"",
		"@FunctionalInterface",
		"public interface BackendAdapter {",
		"",
		"    Map<String, Object> execute(Map<String, Object> capability, Map<String, Object> plan, Map<String, Object> adapterInput, InvocationContext context);",
		"",
		"    static BackendAdapter defaultAdapter() {",
		"        return (capability, plan, _adapterInput, _context) -> {",
		"            Map<String, Object> result = new LinkedHashMap<>();",
		`            result.put("capability_id", capability.get("capability_id"));`,
		`            result.put("selected_backend", plan.get("selected_binding"));`,
		`            result.put("semantic_input", plan.get("semantic_input"));`,
		`            result.put("backend_input_contract", plan.get("backend_input_contract"));`,
		"            @SuppressWarnings(\"unchecked\")",
		`            List<String> unresolved = (List<String>) plan.getOrDefault("unresolved_required_backend_inputs", List.of());`,
		"            if (!unresolved.isEmpty()) {",
		`                result.put("execution_status", "backend_input_incomplete");`,
		`                result.put("unresolved_required_backend_inputs", unresolved);`,
		`                result.put("note", "Generated host is runnable, but backend-only inputs still require extension completion.");`,
		"                return result;",
		"            }",
		`            String executionPosture = (String) capability.get("execution_posture");`,
		`            if ("approval_gated".equals(executionPosture)) {`,
		`                result.put("execution_status", "approval_required");`,
		`                result.put("title", capability.get("title"));`,
		`                result.put("summary", capability.get("summary"));`,
		`                result.put("approval_rule_refs", List.of());`,
		`                result.put("note", "Generated host requires approval before backend execution.");`,
		"                return result;",
		"            }",
		`            if ("prepare_only".equals(executionPosture)) {`,
		`                result.put("execution_status", "prepared");`,
		`                result.put("note", "Generated host prepared a governed preview and did not execute the backend.");`,
		"                return result;",
		"            }",
		`            result.put("execution_status", "backend_execution_stub");`,
		`            result.put("note", "Replace BackendAdapter.defaultAdapter() with provider-specific backend execution.");`,
		"            return result;",
		"        };",
		"    }",
		"}",
		"",
	}, "\n")
}

func buildGeneratedJavaPolicyModule(packageName string) string {
	return strings.Join([]string{
		"package " + packageName + ";",
		"",
		"import java.util.ArrayList;",
		"import java.util.LinkedHashMap;",
		"import java.util.List;",
		"import java.util.Map;",
		"",
		"public final class Policy {",
		"",
		"    private Policy() {}",
		"",
		"    public static PolicyDecision evaluate(Map<String, Object> capability, Map<String, Object> params, String rootPrincipal) {",
		"        String capabilityId = stringValue(capability, \"capability_id\");",
		"        List<Map<String, Object>> bindings = bindingsFor(capabilityId);",
		"        if (bindings.isEmpty()) return new PolicyDecision(\"allow\", null);",
		"        Map<String, String> claims = principalClaims(rootPrincipal);",
		"        if (claims.isEmpty()) return new PolicyDecision(\"allow\", null);",
		"        List<Map<String, Object>> matching = new ArrayList<>();",
		"        for (Map<String, Object> binding : bindings) {",
		"            if (!matchesPrincipal(binding, claims)) continue;",
		"            matching.add(binding);",
		"        }",
		"        if (requiresGovernedStop(capability)) {",
		"            for (Map<String, Object> binding : matching) {",
		"                if (\"deny\".equals(stringValue(binding, \"decision\"))) return decisionFor(binding);",
		"            }",
		"            for (Map<String, Object> binding : matching) {",
		"                if (\"approval_required\".equals(stringValue(binding, \"decision\"))) return decisionFor(binding);",
		"            }",
		"            for (Map<String, Object> binding : matching) {",
		"                if (\"clarify\".equals(stringValue(binding, \"decision\"))) return decisionFor(binding);",
		"            }",
		"        }",
		"        for (Map<String, Object> binding : matching) {",
		"            String decision = stringValue(binding, \"decision\");",
		"            if (!\"deny\".equals(decision) && !\"clarify\".equals(decision) && !\"approval_required\".equals(decision)) return decisionFor(binding);",
		"        }",
		"        return new PolicyDecision(\"allow\", \"No matching runtime policy binding; continuing.\");",
		"    }",
		"",
		"    private static boolean requiresGovernedStop(Map<String, Object> capability) {",
		"        return !objectMap(capability.get(\"grant_policy\")).isEmpty()",
		"            || \"approval_required\".equals(stringValue(capability, \"side_effect_level\"))",
		"            || \"approval_required\".equals(stringValue(capability, \"execution_posture\"))",
		"            || \"approval_gated\".equals(stringValue(capability, \"operation_type\"));",
		"    }",
		"",
		"    private static PolicyDecision decisionFor(Map<String, Object> binding) {",
		"        String decision = firstNonEmpty(stringValue(binding, \"decision\"), \"allow\");",
		"        String detail = firstNonEmpty(stringValue(binding, \"business_rule\"), stringValue(binding, \"enforcement_notes\"));",
		"        if (\"deny\".equals(decision) || \"clarify\".equals(decision) || \"approval_required\".equals(decision)) {",
		"            return new PolicyDecision(decision, detail);",
		"        }",
		"        return new PolicyDecision(\"allow\", detail);",
		"    }",
		"",
		"    @SuppressWarnings(\"unchecked\")",
		"    private static List<Map<String, Object>> bindingsFor(String capabilityId) {",
		"        Object raw = GeneratedRuntimeTarget.runtimeTarget().get(\"policy_bindings\");",
		"        if (!(raw instanceof List<?> list)) return List.of();",
		"        List<Map<String, Object>> result = new ArrayList<>();",
		"        for (Object item : list) {",
		"            if (!(item instanceof Map<?, ?> map)) continue;",
		"            Map<String, Object> binding = (Map<String, Object>) map;",
		"            if (stringList(binding.get(\"capability_ids\")).contains(capabilityId)) result.add(binding);",
		"        }",
		"        return result;",
		"    }",
		"",
		"    private static Map<String, String> principalClaims(String rootPrincipal) {",
		"        String raw = rootPrincipal == null ? \"\" : rootPrincipal.trim();",
		"        if (raw.isEmpty()) return Map.of();",
		"        String[] pieces = raw.split(\"\\\\|\");",
		"        Map<String, String> claims = new LinkedHashMap<>();",
		"        claims.put(\"principal\", pieces.length > 0 ? pieces[0] : \"\");",
		"        for (int index = 1; index < pieces.length; index++) {",
		"            String piece = pieces[index];",
		"            int separator = piece.indexOf('=');",
		"            if (separator < 0) continue;",
		"            claims.put(piece.substring(0, separator).trim(), piece.substring(separator + 1).trim());",
		"        }",
		"        return claims;",
		"    }",
		"",
		"    private static boolean matchesPrincipal(Map<String, Object> binding, Map<String, String> claims) {",
		"        Map<String, Object> selector = objectMap(binding.get(\"principal_selector\"));",
		"        String claim = firstNonEmpty(stringValue(selector, \"claim\"), \"actor_id\");",
		"        String expected = firstNonEmpty(stringValue(selector, \"equals\"), stringValue(binding, \"actor_id\"));",
		"        if (expected.isBlank()) return true;",
		"        if (!claims.containsKey(claim)) return false;",
		"        return expected.equals(claims.get(claim));",
		"    }",
		"",
		"    @SuppressWarnings(\"unchecked\")",
		"    private static Map<String, Object> objectMap(Object value) {",
		"        if (value instanceof Map<?, ?> map) return (Map<String, Object>) map;",
		"        return Map.of();",
		"    }",
		"",
		"    private static List<String> stringList(Object value) {",
		"        if (!(value instanceof List<?> list)) return List.of();",
		"        return list.stream().filter(item -> item != null).map(String::valueOf).toList();",
		"    }",
		"",
		"    private static String stringValue(Map<String, Object> object, String key) {",
		"        Object value = object == null ? null : object.get(key);",
		"        return value == null ? \"\" : String.valueOf(value);",
		"    }",
		"",
		"    private static String firstNonEmpty(String... values) {",
		"        for (String value : values) {",
		"            if (value != null && !value.isBlank()) return value;",
		"        }",
		"        return \"\";",
		"    }",
		"",
		"    public record PolicyDecision(String decision, String detail) {}",
		"}",
		"",
	}, "\n")
}

func buildGeneratedJavaCapabilitiesModule(packageName string) string {
	return strings.Join([]string{
		"package " + packageName + ";",
		"",
		"import dev.anip.core.ANIPError;",
		"import dev.anip.core.AuditPolicy;",
		"import dev.anip.core.CapabilityDeclaration;",
		"import dev.anip.core.CapabilityInput;",
		"import dev.anip.core.CapabilityOutput;",
		"import dev.anip.core.Composition;",
		"import dev.anip.core.CompositionStep;",
		"import dev.anip.core.FailurePolicy;",
		"import dev.anip.core.GrantPolicy;",
		"import dev.anip.core.InputMeaning;",
		"import dev.anip.core.InputResolution;",
		"import dev.anip.core.Constants;",
		"import dev.anip.core.Resolution;",
		"import dev.anip.core.ResolutionBehavior;",
		"import dev.anip.core.ResolutionMode;",
		"import dev.anip.core.SideEffect;",
		"import dev.anip.service.CapabilityDef;",
		"import dev.anip.service.InvocationContext;",
		"",
		"import java.util.ArrayList;",
		"import java.util.LinkedHashMap;",
		"import java.util.LinkedHashSet;",
		"import java.util.List;",
		"import java.util.Map;",
		"import java.util.Set;",
		"",
		"public final class GeneratedCapabilities {",
		"",
		"    private GeneratedCapabilities() {}",
		"",
		"    public static List<CapabilityDef> createAll(BackendAdapter backendAdapter) {",
		"        return createAll(backendAdapter, \"\");",
		"    }",
		"",
		"    public static List<CapabilityDef> createAll(BackendAdapter backendAdapter, String serviceFilter) {",
		"        String normalizedServiceFilter = serviceFilter == null ? \"\" : serviceFilter.trim();",
		"        return GeneratedRuntimeTarget.capabilities().stream()",
		"                .filter(capability -> normalizedServiceFilter.isBlank() || normalizedServiceFilter.equals(stringValue(capability, \"service_id\")))",
		"                .map(capability -> createCapability(capability, backendAdapter))",
		"                .toList();",
		"    }",
		"",
		"    private static CapabilityDef createCapability(Map<String, Object> capability, BackendAdapter backendAdapter) {",
		"        CapabilityDeclaration declaration = new CapabilityDeclaration(",
		`                stringValue(capability, "capability_id"),`,
		`                firstNonEmpty(stringValue(capability, "summary"), stringValue(capability, "title"), stringValue(capability, "capability_id")),`,
		"                GeneratedRuntimeTarget.contractVersion(),",
		"                buildInputs(capability),",
		`                new CapabilityOutput(firstNonEmpty(stringValue(capability, "output_shape"), "governed_result"), List.of("execution_status", "capability_id", "semantic_input", "backend_input_contract", "note")),`,
		`                new SideEffect(sideEffectType(stringValue(capability, "side_effect_level")), rollbackWindowFor(stringValue(capability, "side_effect_level"))),`,
		`                stringList(capability.get("minimum_scope")),`,
		"                null,",
		"                null,",
		`                List.of("unary"),`,
		"                null,",
		"                null,",
		`                List.of(),`,
		`                List.of()`,
		"        )",
		`                .setKind(declarationKind(capability))`,
		`                .setComposition(declarationComposition(capability))`,
		`                .setGrantPolicy(readGrantPolicy(capability.get("grant_policy")));`,
		"        return new CapabilityDef(declaration, (ctx, params) -> handle(capability, ctx, params, backendAdapter));",
		"    }",
		"",
		"    private static String declarationKind(Map<String, Object> capability) {",
		`        String kind = firstNonEmpty(stringValue(capability, "kind"), "atomic");`,
		"        return kind;",
		"    }",
		"",
		"    private static Composition declarationComposition(Map<String, Object> capability) {",
		`        return readComposition(capability.get("composition"));`,
		"    }",
		"",
		"    private static Composition readComposition(Object value) {",
		"        Map<String, Object> map = objectMap(value);",
		"        if (map == null || map.isEmpty()) return null;",
		"        List<CompositionStep> steps = new ArrayList<>();",
		`        for (Map<String, Object> step : mapList(map.get("steps"))) {`,
		`            steps.add(new CompositionStep(stringValue(step, "id"), stringValue(step, "capability"))`,
		`                    .setEmptyResultSource(booleanValue(step.get("empty_result_source")))`,
		`                    .setEmptyResultPath(stringValue(step, "empty_result_path")));`,
		"        }",
		`        Map<String, Object> failure = objectMap(map.get("failure_policy"));`,
		`        Map<String, Object> audit = objectMap(map.get("audit_policy"));`,
		"        Composition composition = new Composition(",
		`                firstNonEmpty(stringValue(map, "authority_boundary"), "same_service"),`,
		"                steps,",
		`                nestedStringMap(map.get("input_mapping")),`,
		`                stringMap(map.get("output_mapping")),`,
		"                new FailurePolicy(",
		`                        firstNonEmpty(stringValue(failure, "child_clarification"), "propagate"),`,
		`                        firstNonEmpty(stringValue(failure, "child_denial"), "propagate"),`,
		`                        firstNonEmpty(stringValue(failure, "child_approval_required"), "propagate"),`,
		`                        firstNonEmpty(stringValue(failure, "child_error"), "fail_parent")),`,
		`                new AuditPolicy(booleanValue(value(audit, "record_child_invocations")), booleanValue(value(audit, "parent_task_lineage"))));`,
		`        String emptyResultPolicy = stringValue(map, "empty_result_policy");`,
		"        if (!emptyResultPolicy.isBlank()) composition.setEmptyResultPolicy(emptyResultPolicy);",
		`        Map<String, Object> emptyResultOutput = objectMap(map.get("empty_result_output"));`,
		"        if (emptyResultOutput != null) composition.setEmptyResultOutput(emptyResultOutput);",
		"        return composition;",
		"    }",
		"",
		"    private static GrantPolicy readGrantPolicy(Object value) {",
		"        Map<String, Object> map = objectMap(value);",
		"        if (map == null || map.isEmpty()) return null;",
		"        return new GrantPolicy(",
		`                stringList(map.get("allowed_grant_types")),`,
		`                stringValue(map, "default_grant_type"),`,
		`                intValue(map.get("expires_in_seconds")),`,
		`                intValue(map.get("max_uses")));`,
		"    }",
		"",
		"    private static Map<String, Object> handle(Map<String, Object> capability, InvocationContext ctx, Map<String, Object> params, BackendAdapter backendAdapter) {",
		"        assertRequestedEffectsAllowed(capability, ctx);",
		"        params = applyInputDefaults(capability, params);",
		"        assertRequiredSemanticInputs(capability, params);",
		"        validateInputBehavior(capability, params);",
		"        Policy.PolicyDecision policy = Policy.evaluate(capability, params, ctx.getRootPrincipal());",
		`        if ("deny".equals(policy.decision())) {`,
		`            throw new ANIPError("denied", firstNonEmpty(policy.detail(), "Request denied for " + stringValue(capability, "capability_id") + ".")).withResolution("contact_service_owner");`,
		"        }",
		`        if ("clarify".equals(policy.decision())) {`,
		`            throw new ANIPError("clarification_required", firstNonEmpty(policy.detail(), "Clarification required for " + stringValue(capability, "capability_id") + ".")).withResolution("obtain_binding");`,
		"        }",
		"",
		"        Map<String, Object> plan = buildBackendInvocationPlan(capability, params);",
		`        if ("approval_required".equals(policy.decision()) && (ctx.getApprovalGrant() == null || ctx.getApprovalGrant().isBlank())) {`,
		`            throw new ANIPError("approval_required", firstNonEmpty(policy.detail(), "Approval required for " + stringValue(capability, "capability_id") + ".")).withResolution("request_approval");`,
		"        }",
		`        return backendAdapter.execute(capability, plan, objectMap(plan.get("adapter_input")), ctx);`,
		"    }",
		"",
		"    private static List<CapabilityInput> buildInputs(Map<String, Object> capability) {",
		"        List<CapabilityInput> inputs = new ArrayList<>();",
		`        for (Map<String, Object> input : inputList(capability, "required_inputs")) {`,
		"            inputs.add(new CapabilityInput(",
		`                    stringValue(input, "input_name"),`,
		`                    firstNonEmpty(stringValue(input, "input_type"), "string"),`,
		"                    true,",
		`                    defaultValue(input),`,
		`                    firstNonEmpty(stringValue(input, "summary"), stringValue(input, "input_name")),`,
		`                    optionalString(input, "semantic_type"),`,
		`                    booleanValue(input.get("entity_reference")),`,
		`                    stringList(input.get("allowed_values")),`,
		`                    optionalString(input, "catalog_ref"),`,
		`                    inputMeanings(input.get("input_meanings")),`,
		`                    inputResolution(input.get("resolution"))`,
		"            ));",
		"        }",
		`        for (Map<String, Object> input : inputList(capability, "optional_inputs")) {`,
		"            inputs.add(new CapabilityInput(",
		`                    stringValue(input, "input_name"),`,
		`                    firstNonEmpty(stringValue(input, "input_type"), "string"),`,
		"                    false,",
		`                    defaultValue(input),`,
		`                    firstNonEmpty(stringValue(input, "summary"), stringValue(input, "input_name")),`,
		`                    optionalString(input, "semantic_type"),`,
		`                    booleanValue(input.get("entity_reference")),`,
		`                    stringList(input.get("allowed_values")),`,
		`                    optionalString(input, "catalog_ref"),`,
		`                    inputMeanings(input.get("input_meanings")),`,
		`                    inputResolution(input.get("resolution"))`,
		"            ));",
		"        }",
		"        return inputs;",
		"    }",
		"",
		"    private static InputResolution inputResolution(Object value) {",
		"        Map<String, Object> map = objectMap(value);",
		"        if (map == null || map.isEmpty()) return null;",
		"        return new InputResolution(",
		`                resolutionMode(stringValue(map, "mode")),`,
		`                optionalString(map, "resolver_ref"),`,
		`                resolutionBehavior(stringValue(map, "on_missing")),`,
		`                resolutionBehavior(stringValue(map, "on_ambiguous")),`,
		`                resolutionBehavior(stringValue(map, "on_unresolved")));`,
		"    }",
		"",
		"    private static ResolutionMode resolutionMode(String value) {",
		"        return value.isBlank() ? null : ResolutionMode.fromWire(value);",
		"    }",
		"",
		"    private static ResolutionBehavior resolutionBehavior(String value) {",
		"        return value.isBlank() ? null : ResolutionBehavior.fromWire(value);",
		"    }",
		"",
		"    private static List<InputMeaning> inputMeanings(Object value) {",
		"        List<InputMeaning> result = new ArrayList<>();",
		"        for (Map<String, Object> item : mapList(value)) {",
		"            result.add(new InputMeaning(",
		`                    stringValue(item, "label"),`,
		`                    stringValue(item, "value"),`,
		`                    stringValue(item, "description")));`,
		"        }",
		"        return result;",
		"    }",
		"",
		"    private static void assertRequiredSemanticInputs(Map<String, Object> capability, Map<String, Object> params) {",
		"        List<String> missing = new ArrayList<>();",
		`        for (Map<String, Object> input : inputList(capability, "required_inputs")) {`,
		`            if (!stringValue(input, "default_value").isBlank()) continue;`,
		`            String inputName = stringValue(input, "input_name");`,
		"            Object value = params.get(inputName);",
		"            if (value == null) {",
		"                missing.add(inputName);",
		"                continue;",
		"            }",
		"            if (value instanceof String text && text.isBlank()) {",
		"                missing.add(inputName);",
		"            }",
		"        }",
		"        if (!missing.isEmpty()) {",
		`            throw new ANIPError("clarification_required", "Required semantic inputs are missing for " + stringValue(capability, "capability_id") + ".")`,
		`                    .withResolution(new Resolution("obtain_binding", Constants.recoveryClassForAction("obtain_binding"), String.join(",", missing), null, null));`,
		"        }",
		"    }",
		"",
		"    private static void validateInputBehavior(Map<String, Object> capability, Map<String, Object> params) {",
		"        List<Map<String, Object>> inputs = new ArrayList<>();",
		`        inputs.addAll(inputList(capability, "required_inputs"));`,
		`        inputs.addAll(inputList(capability, "optional_inputs"));`,
		"        for (Map<String, Object> input : inputs) {",
		`            String inputName = stringValue(input, "input_name");`,
		"            Object value = params.get(inputName);",
		`            if (inputName.isBlank() || value == null || String.valueOf(value).isBlank()) continue;`,
		`            List<String> allowedValues = stringList(input.get("allowed_values"));`,
		"            if (allowedValues.isEmpty() || allowedValues.contains(String.valueOf(value))) continue;",
		`            Map<String, Object> resolution = objectMap(input.get("resolution"));`,
		`            boolean shouldDeny = "closed_values".equals(stringValue(resolution, "mode")) && "deny".equals(stringValue(resolution, "on_unresolved"));`,
		`            String action = shouldDeny ? "contact_service_owner" : "obtain_binding";`,
		`            throw new ANIPError(shouldDeny ? "denied" : "clarification_required", "Input " + inputName + " must use one of the declared allowed values.")`,
		`                    .withResolution(new Resolution(action, Constants.recoveryClassForAction(action), inputName, null, null));`,
		"        }",
		"    }",
		"",
		"    private static Object defaultValue(Map<String, Object> input) {",
		`        String value = stringValue(input, "default_value");`,
		"        return value.isBlank() ? null : value;",
		"    }",
		"",
		"    private static Map<String, Object> applyInputDefaults(Map<String, Object> capability, Map<String, Object> params) {",
		"        Map<String, Object> normalized = new LinkedHashMap<>(params);",
		`        List<Map<String, Object>> inputs = new ArrayList<>();`,
		`        inputs.addAll(inputList(capability, "required_inputs"));`,
		`        inputs.addAll(inputList(capability, "optional_inputs"));`,
		"        for (Map<String, Object> input : inputs) {",
		`            String inputName = stringValue(input, "input_name");`,
		`            String defaultValue = stringValue(input, "default_value");`,
		`            Map<String, Object> resolution = objectMap(input.get("resolution"));`,
		`            if ("omit".equals(stringValue(resolution, "on_missing"))) continue;`,
		"            Object value = normalized.get(inputName);",
		"            if (!inputName.isBlank() && !defaultValue.isBlank() && (value == null || value instanceof String text && text.isBlank())) {",
		"                normalized.put(inputName, defaultValue);",
		"            }",
		"        }",
		"        return normalized;",
		"    }",
		"",
		"    private static Map<String, Object> buildBackendInvocationPlan(Map<String, Object> capability, Map<String, Object> params) {",
		"        Map<String, Object> selectedBinding = selectBackendBinding(capability);",
		"        Map<String, Object> contract = effectiveBackendInputContract(capability, selectedBinding);",
		"        Set<String> semanticKeys = new LinkedHashSet<>();",
		`        for (Map<String, Object> input : inputList(capability, "required_inputs")) {`,
		`            semanticKeys.add(stringValue(input, "input_name"));`,
		"        }",
		`        for (Map<String, Object> input : inputList(capability, "optional_inputs")) {`,
		`            semanticKeys.add(stringValue(input, "input_name"));`,
		"        }",
		"        Map<String, Object> semanticInput = new LinkedHashMap<>();",
		"        for (Map.Entry<String, Object> entry : params.entrySet()) {",
		"            if (semanticKeys.contains(entry.getKey())) {",
		"                semanticInput.put(entry.getKey(), entry.getValue());",
		"            }",
		"        }",
		"        Set<String> adapterKeys = new LinkedHashSet<>(semanticKeys);",
		`        adapterKeys.addAll(stringList(contract.get("required")));`,
		`        adapterKeys.addAll(stringList(contract.get("optional")));`,
		"        Map<String, Object> adapterInput = new LinkedHashMap<>();",
		"        for (Map.Entry<String, Object> entry : params.entrySet()) {",
		"            if (adapterKeys.contains(entry.getKey())) {",
		"                adapterInput.put(entry.getKey(), entry.getValue());",
		"            }",
		"        }",
		"        List<String> unresolved = new ArrayList<>();",
		`        for (String key : stringList(contract.get("required"))) {`,
		"            if (!params.containsKey(key) || params.get(key) == null) {",
		"                unresolved.add(key);",
		"            }",
		"        }",
		"        Map<String, Object> plan = new LinkedHashMap<>();",
		`        plan.put("selected_binding", selectedBinding);`,
		`        plan.put("semantic_input", semanticInput);`,
		`        plan.put("adapter_input", adapterInput);`,
		`        plan.put("backend_input_contract", contract);`,
		`        plan.put("unresolved_required_backend_inputs", unresolved);`,
		"        return plan;",
		"    }",
		"",
		"    private static void assertRequestedEffectsAllowed(Map<String, Object> capability, InvocationContext ctx) {",
		"        List<String> requested = ctx.getRequestedEffects();",
		"        if (requested.isEmpty()) return;",
		`        List<String> forbidden = stringList(value(objectMap(capability.get("business_effects")), "does_not_produce"));`,
		"        if (forbidden.isEmpty()) return;",
		"        List<String> blocked = new ArrayList<>();",
		"        for (String effect : requested) {",
		"            if (forbidden.contains(effect) && !blocked.contains(effect)) blocked.add(effect);",
		"        }",
		"        if (blocked.isEmpty()) return;",
		"        blocked.sort(String::compareTo);",
		`        throw new ANIPError("denied", "Capability " + stringValue(capability, "capability_id") + " does not produce requested effect(s): " + String.join(", ", blocked) + ".").withResolution("request_declared_capability");`,
		"    }",
		"",
		"    private static Map<String, Object> selectBackendBinding(Map<String, Object> capability) {",
		`        List<Map<String, Object>> bindings = mapList(capability.get("backend_bindings"));`,
		"        if (bindings.isEmpty()) {",
		"            return null;",
		"        }",
		"        return bindings.get(0);",
		"    }",
		"",
		"    private static Map<String, Object> effectiveBackendInputContract(Map<String, Object> capability, Map<String, Object> selectedBinding) {",
		`        String mode = firstNonEmpty(stringValue(selectedBinding, "backend_input_mode"), stringValue(capability, "backend_input_mode"), "implicit");`,
		`        List<String> derivedRequired = firstNonEmptyList(stringList(value(selectedBinding, "derived_required_backend_inputs")), stringList(capability.get("derived_required_backend_inputs")));`,
		`        List<String> derivedOptional = firstNonEmptyList(stringList(value(selectedBinding, "derived_optional_backend_inputs")), stringList(capability.get("derived_optional_backend_inputs")));`,
		`        List<String> explicitRequired = firstNonEmptyList(stringList(value(selectedBinding, "explicit_required_backend_inputs")), stringList(capability.get("explicit_required_backend_inputs")));`,
		`        List<String> explicitOptional = firstNonEmptyList(stringList(value(selectedBinding, "explicit_optional_backend_inputs")), stringList(capability.get("explicit_optional_backend_inputs")));`,
		"",
		"        Map<String, Object> result = new LinkedHashMap<>();",
		"        if (\"explicit\".equals(mode)) {",
		"            List<String> required = uniqueStrings(explicitRequired);",
		"            result.put(\"mode\", \"explicit\");",
		"            result.put(\"required\", required);",
		"            result.put(\"optional\", exclude(uniqueStrings(explicitOptional), required));",
		"            return result;",
		"        }",
		"        if (\"hybrid\".equals(mode)) {",
		"            List<String> required = uniqueStrings(concat(derivedRequired, explicitRequired));",
		"            result.put(\"mode\", \"hybrid\");",
		"            result.put(\"required\", required);",
		"            result.put(\"optional\", exclude(uniqueStrings(concat(derivedOptional, explicitOptional)), required));",
		"            return result;",
		"        }",
		"        List<String> required = uniqueStrings(derivedRequired);",
		"        result.put(\"mode\", \"implicit\");",
		"        result.put(\"required\", required);",
		"        result.put(\"optional\", exclude(uniqueStrings(derivedOptional), required));",
		"        return result;",
		"    }",
		"",
		"    private static List<String> governanceList(Map<String, Object> capability, String key) {",
		"        Object governance = capability.get(\"governance\");",
		"        if (governance instanceof Map<?, ?> map) {",
		"            return stringList(map.get(key));",
		"        }",
		"        return List.of();",
		"    }",
		"",
		"    private static Object value(Map<String, Object> object, String key) {",
		"        if (object == null) {",
		"            return null;",
		"        }",
		"        return object.get(key);",
		"    }",
		"",
		"    @SuppressWarnings(\"unchecked\")",
		"    private static Map<String, Object> objectMap(Object value) {",
		"        if (value instanceof Map<?, ?> map) {",
		"            return (Map<String, Object>) map;",
		"        }",
		"        return null;",
		"    }",
		"",
		"    private static Map<String, String> stringMap(Object value) {",
		"        Map<String, Object> map = objectMap(value);",
		"        if (map == null) {",
		"            return Map.of();",
		"        }",
		"        Map<String, String> result = new LinkedHashMap<>();",
		"        for (Map.Entry<String, Object> entry : map.entrySet()) {",
		"            if (entry.getValue() != null) result.put(entry.getKey(), String.valueOf(entry.getValue()));",
		"        }",
		"        return result;",
		"    }",
		"",
		"    private static Map<String, Map<String, String>> nestedStringMap(Object value) {",
		"        Map<String, Object> map = objectMap(value);",
		"        if (map == null) {",
		"            return Map.of();",
		"        }",
		"        Map<String, Map<String, String>> result = new LinkedHashMap<>();",
		"        for (Map.Entry<String, Object> entry : map.entrySet()) {",
		"            result.put(entry.getKey(), stringMap(entry.getValue()));",
		"        }",
		"        return result;",
		"    }",
		"",
		"    private static boolean booleanValue(Object value) {",
		"        return value instanceof Boolean bool && bool;",
		"    }",
		"",
		"    private static int intValue(Object value) {",
		"        if (value instanceof Number number) {",
		"            return number.intValue();",
		"        }",
		"        if (value instanceof String text && !text.isBlank()) {",
		"            return Integer.parseInt(text);",
		"        }",
		"        return 0;",
		"    }",
		"",
		"    private static String stringValue(Map<String, Object> object, String key) {",
		"        Object value = value(object, key);",
		"        if (value == null) {",
		`            return "";`,
		"        }",
		"        return String.valueOf(value);",
		"    }",
		"",
		"    private static String optionalString(Map<String, Object> object, String key) {",
		"        String value = stringValue(object, key);",
		"        return value.isBlank() ? null : value;",
		"    }",
		"",
		"    private static String firstNonEmpty(String... values) {",
		"        for (String value : values) {",
		"            if (value != null && !value.isBlank()) {",
		"                return value;",
		"            }",
		"        }",
		`        return "";`,
		"    }",
		"",
		"    private static List<String> firstNonEmptyList(List<String> primary, List<String> fallback) {",
		"        if (!primary.isEmpty()) {",
		"            return primary;",
		"        }",
		"        return fallback;",
		"    }",
		"",
		"    private static List<String> uniqueStrings(List<String> values) {",
		"        List<String> result = new ArrayList<>();",
		"        for (String value : values) {",
		"            if (value == null || value.isBlank() || result.contains(value)) {",
		"                continue;",
		"            }",
		"            result.add(value);",
		"        }",
		"        return result;",
		"    }",
		"",
		"    private static List<String> concat(List<String> left, List<String> right) {",
		"        List<String> result = new ArrayList<>(left);",
		"        result.addAll(right);",
		"        return result;",
		"    }",
		"",
		"    private static List<String> exclude(List<String> values, List<String> excluded) {",
		"        List<String> result = new ArrayList<>();",
		"        for (String value : values) {",
		"            if (!excluded.contains(value)) {",
		"                result.add(value);",
		"            }",
		"        }",
		"        return result;",
		"    }",
		"",
		"    @SuppressWarnings(\"unchecked\")",
		"    private static List<Map<String, Object>> inputList(Map<String, Object> capability, String key) {",
		"        return mapList(capability.get(key));",
		"    }",
		"",
		"    @SuppressWarnings(\"unchecked\")",
		"    private static List<Map<String, Object>> mapList(Object value) {",
		"        if (value instanceof List<?> list) {",
		"            return (List<Map<String, Object>>) (List<?>) list;",
		"        }",
		"        return List.of();",
		"    }",
		"",
		"    @SuppressWarnings(\"unchecked\")",
		"    private static List<String> stringList(Object value) {",
		"        if (value instanceof List<?> list) {",
		"            return (List<String>) (List<?>) list;",
		"        }",
		"        return List.of();",
		"    }",
		"",
		"    private static String sideEffectType(String sideEffectLevel) {",
		"        String value = sideEffectLevel == null ? \"\" : sideEffectLevel.toLowerCase();",
		"        if (value.contains(\"irreversible\")) {",
		`            return "irreversible";`,
		"        }",
		"        if (value.contains(\"transaction\")) {",
		`            return "transactional";`,
		"        }",
		"        if (value.contains(\"write\")) {",
		`            return "write";`,
		"        }",
		`        return "read";`,
		"    }",
		"",
		"    private static String rollbackWindowFor(String sideEffectLevel) {",
		"        return switch (sideEffectType(sideEffectLevel)) {",
		`            case "read" -> "not_applicable";`,
		`            case "irreversible" -> "none";`,
		`            default -> "PT15M";`,
		"        };",
		"    }",
		"}",
		"",
	}, "\n")
}

func buildGeneratedJavaSmokeTestModule(packageName string, expectedCapabilityID string) string {
	return strings.Join([]string{
		"package " + packageName + ";",
		"",
		"import dev.anip.service.CapabilityDef;",
		"",
		"import org.junit.jupiter.api.Test;",
		"",
		"import java.util.List;",
		"",
		"import static org.junit.jupiter.api.Assertions.assertFalse;",
		"import static org.junit.jupiter.api.Assertions.assertEquals;",
		"",
		"class GeneratedCapabilitiesTest {",
		"",
		"    @Test",
		"    void createsCapabilityDefinitions() {",
		"        List<CapabilityDef> capabilities = GeneratedCapabilities.createAll(BackendAdapter.defaultAdapter());",
		"        assertFalse(capabilities.isEmpty());",
		"        assertEquals(" + javaQuoted(expectedCapabilityID) + ", capabilities.get(0).getDeclaration().getName());",
		"    }",
		"}",
		"",
	}, "\n")
}

func javaStringJoinExpression(value string) string {
	const maxChunkRunes = 12000
	if value == "" {
		return javaQuoted("")
	}
	chunks := chunkStringRunes(value, maxChunkRunes)
	if len(chunks) == 1 {
		return javaQuoted(chunks[0])
	}
	lines := make([]string, 0, len(chunks)+2)
	lines = append(lines, "String.join(\"\",")
	for index, chunk := range chunks {
		suffix := ","
		if index == len(chunks)-1 {
			suffix = ""
		}
		lines = append(lines, "        "+javaQuoted(chunk)+suffix)
	}
	lines = append(lines, "    )")
	return strings.Join(lines, "\n")
}

func chunkStringRunes(value string, maxRunes int) []string {
	if maxRunes <= 0 {
		maxRunes = 12000
	}
	var chunks []string
	var builder strings.Builder
	count := 0
	for _, r := range value {
		if count >= maxRunes {
			chunks = append(chunks, builder.String())
			builder.Reset()
			count = 0
		}
		builder.WriteRune(r)
		count++
	}
	if builder.Len() > 0 {
		chunks = append(chunks, builder.String())
	}
	return chunks
}

func javaPackageName(value string) string {
	base := strings.TrimSpace(value)
	if base == "" {
		base = "generated-anip-service"
	}
	segments := strings.FieldsFunc(base, func(r rune) bool {
		return r == '.'
	})
	if len(segments) == 0 {
		segments = []string{base}
	}
	sanitized := make([]string, 0, len(segments)+3)
	if !strings.Contains(value, ".") {
		sanitized = append(sanitized, "dev", "anip", "generated")
	}
	for _, segment := range segments {
		normalized := javaIdentifier(segment)
		if normalized == "" {
			continue
		}
		sanitized = append(sanitized, normalized)
	}
	if len(sanitized) == 0 {
		return "dev.anip.generated.generated_service"
	}
	return strings.Join(sanitized, ".")
}

func javaIdentifier(value string) string {
	var builder strings.Builder
	for _, r := range strings.ToLower(value) {
		if (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9') {
			builder.WriteRune(r)
			continue
		}
		builder.WriteRune('_')
	}
	result := strings.Trim(builder.String(), "_")
	if result == "" {
		return "generated_service"
	}
	if result[0] >= '0' && result[0] <= '9' {
		return "generated_" + result
	}
	return result
}

func javaQuoted(value string) string {
	return fmt.Sprintf("%q", value)
}

func validateJavaFramework(framework JavaFramework) error {
	switch framework {
	case JavaFrameworkSpringBoot, JavaFrameworkQuarkus:
		return nil
	default:
		return fmt.Errorf("unsupported Java framework %q", framework)
	}
}

func localJavaSourcePaths(framework JavaFramework) []string {
	_, currentFile, _, _ := runtime.Caller(0)
	repoRoot := filepath.Clean(filepath.Join(filepath.Dir(currentFile), "..", "..", ".."))
	paths := make([]string, 0, 5)
	moduleNames := []string{"anip-core", "anip-crypto", "anip-server", "anip-service", "anip-spring-boot", "anip-stdio"}
	if framework == JavaFrameworkQuarkus {
		moduleNames = []string{"anip-core", "anip-crypto", "anip-server", "anip-service", "anip-quarkus", "anip-stdio"}
	}
	for _, moduleName := range moduleNames {
		paths = append(paths, filepath.Join(repoRoot, "packages", "java", moduleName, "src", "main", "java"))
	}
	return paths
}
