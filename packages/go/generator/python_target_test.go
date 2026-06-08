package generator

import (
	"strings"
	"testing"
)

func TestBuildPythonProject(t *testing.T) {
	definition := mustReadFixtureDefinition(t)

	project, err := BuildPythonProject(definition, BuildPythonProjectOptions{
		DependencySource: DependencySourceLocal,
		Port:             4100,
	})
	if err != nil {
		t.Fatalf("BuildPythonProject: %v", err)
	}

	assertHasFile(t, project.Files, "pyproject.toml")
	assertHasFile(t, project.Files, "src/work_item_governance_service/app.py")
	assertHasFile(t, project.Files, "src/work_item_governance_service/capabilities.py")
	assertHasFile(t, project.Files, "src/work_item_governance_service/runtime_target.py")
	assertHasFile(t, project.Files, "tests/test_service_smoke.py")
	assertHasFile(t, project.Files, "integration-fronting/adapter-bindings.json")
	assertHasFile(t, project.Files, "integration-fronting/backend-profile.example.json")
	assertHasFile(t, project.Files, "integration-fronting/backend-selection.example.json")
	assertHasFile(t, project.Files, "integration-fronting/backend-templates/native-api.md")

	pyproject := fileContent(project.Files, "pyproject.toml")
	if !strings.Contains(pyproject, "anip-service @ file://") {
		t.Fatalf("pyproject missing local anip-service dependency")
	}
	if !strings.Contains(pyproject, "anip-fastapi @ file://") {
		t.Fatalf("pyproject missing local anip-fastapi dependency")
	}

	runtimeTarget := fileContent(project.Files, "src/work_item_governance_service/runtime_target.py")
	if !strings.Contains(runtimeTarget, "work_item.prepare_update") {
		t.Fatalf("runtime target missing expected capability id")
	}
	if !strings.Contains(runtimeTarget, "GENERATED_RUNTIME_TARGET = RUNTIME_TARGET") {
		t.Fatalf("runtime target missing generated runtime target compatibility alias")
	}
	if !strings.Contains(runtimeTarget, `"backend_input_mode": "hybrid"`) {
		t.Fatalf("runtime target missing hybrid backend input mode")
	}

	app := fileContent(project.Files, "src/work_item_governance_service/app.py")
	if !strings.Contains(app, `raw = os.getenv("ANIP_API_KEYS_JSON")`) {
		t.Fatalf("app module should support ANIP_API_KEYS_JSON auth mapping")
	}
	if !strings.Contains(app, `return _api_keys().get(bearer)`) {
		t.Fatalf("app module should authenticate through the configured API key map")
	}

	policy := fileContent(project.Files, "src/work_item_governance_service/policy.py")
	if !strings.Contains(policy, `"No matching runtime policy binding; continuing."`) {
		t.Fatalf("policy module should treat unmatched actor bindings as sparse override misses")
	}
	capabilities := fileContent(project.Files, "src/work_item_governance_service/capabilities.py")
	if strings.Contains(capabilities, `policy.get("decision") == "no_match"`) {
		t.Fatalf("capability module should not deny sparse policy override misses")
	}
	if !strings.Contains(capabilities, `ANIPError("denied"`) {
		t.Fatalf("capability module should use ANIP denied failures for policy denials")
	}

	backendAdapter := fileContent(project.Files, "src/work_item_governance_service/backend_adapter.py")
	if strings.Contains(backendAdapter, "type BackendInvocationPlan =") {
		t.Fatalf("backend adapter should avoid Python 3.12-only type alias syntax")
	}
	if !strings.Contains(backendAdapter, "BackendInvocationPlan = dict[str, Any]") {
		t.Fatalf("backend adapter missing Python 3.11-compatible type alias")
	}
	frontingBindings := fileContent(project.Files, "integration-fronting/adapter-bindings.json")
	backendProfile := fileContent(project.Files, "integration-fronting/backend-profile.example.json")
	if !strings.Contains(frontingBindings, `"capability_id": "work_item.prepare_update"`) {
		t.Fatalf("fronting binding pack missing prepare update capability")
	}
	if !strings.Contains(frontingBindings, `"raw_operation_refs": [`) {
		t.Fatalf("fronting binding pack missing raw operation refs")
	}
	if !strings.Contains(backendProfile, `"schema_version": "anip-backend-implementation-profile/v0"`) {
		t.Fatalf("backend profile missing schema")
	}
	if !strings.Contains(backendProfile, `"backend_family": "native-api"`) {
		t.Fatalf("backend profile missing native-api family")
	}
}

func TestBuildPythonProjectSplitsContractServices(t *testing.T) {
	definition := mustReadFixtureDefinition(t)
	secondCapability := definition.CapabilityFormalizations[0]
	secondCapability.ServiceID = "work-item-audit-service"
	secondCapability.CapabilityID = "work_item.audit"
	secondCapability.Title = "Audit work item"
	secondCapability.Summary = "Audit work item activity."
	definition.CapabilityFormalizations = append(definition.CapabilityFormalizations, secondCapability)
	definition.ServiceTopologyBindings = append(definition.ServiceTopologyBindings, ServiceTopologyBinding{
		ServiceID:               "work-item-audit-service",
		ServiceName:             "Work Item Audit Service",
		SourceRole:              "application_integration",
		FormalizedCapabilityIDs: []string{"work_item.audit"},
	})

	project, err := BuildPythonProject(definition, BuildPythonProjectOptions{
		DependencySource: DependencySourceLocal,
		Port:             4100,
	})
	if err != nil {
		t.Fatalf("BuildPythonProject: %v", err)
	}

	assertHasFile(t, project.Files, "src/work_item_governance_service/app.py")
	assertHasFile(t, project.Files, "src/work_item_governance_service/services/work_item_audit_service/app.py")
	if len(project.Services) != 2 {
		t.Fatalf("expected 2 services, got %d", len(project.Services))
	}

	capabilities := fileContent(project.Files, "src/work_item_governance_service/capabilities.py")
	if !strings.Contains(capabilities, `DEFAULT_SERVICE_ID = "work-item-governance-service"`) {
		t.Fatalf("capabilities module missing default service id")
	}
	if !strings.Contains(capabilities, "def generated_declaration_for_capability(capability_id: str) -> CapabilityDeclaration:") {
		t.Fatalf("capabilities module missing contract-derived declaration helper")
	}
	if !strings.Contains(capabilities, "def generated_capabilities_for_service(service_id: str, capability_registry: dict[str, Capability] | None = None)") {
		t.Fatalf("capabilities module missing service-scoped capability builder")
	}
	if !strings.Contains(capabilities, "if metadata['capability_id'] in registry:") {
		t.Fatalf("capabilities module should preserve custom handlers in the capability registry")
	}
	if !strings.Contains(capabilities, "async def _execute_generated_composition") {
		t.Fatalf("capabilities module missing generated v0.23 composition executor")
	}
	if !strings.Contains(capabilities, "def _apply_input_defaults") {
		t.Fatalf("capabilities module should apply contract input defaults")
	}
	if !strings.Contains(capabilities, "def _validate_input_behavior") {
		t.Fatalf("capabilities module should validate contract input behavior")
	}
	if !strings.Contains(capabilities, `default=item.get('default_value') or None`) {
		t.Fatalf("capability declarations should preserve input defaults")
	}
	if !strings.Contains(capabilities, `allowed_values=item.get('allowed_values') or []`) {
		t.Fatalf("capability declarations should preserve allowed values")
	}

	serviceApp := fileContent(project.Files, "src/work_item_governance_service/services/work_item_audit_service/app.py")
	if !strings.Contains(serviceApp, `raw = os.getenv("ANIP_API_KEYS_JSON")`) {
		t.Fatalf("secondary service app should support ANIP_API_KEYS_JSON auth mapping")
	}

	tests := fileContent(project.Files, "tests/test_service_smoke.py")
	if !strings.Contains(tests, `"module": "work_item_governance_service.services.work_item_audit_service.app"`) {
		t.Fatalf("smoke test missing secondary service app")
	}
	if !strings.Contains(tests, `assert discovery_names == set(service['capabilities'])`) {
		t.Fatalf("smoke test should assert service-local discovery")
	}
}

func TestBuildPythonMultiServiceContainerArtifacts(t *testing.T) {
	definition := mustReadFixtureDefinition(t)
	secondCapability := definition.CapabilityFormalizations[0]
	secondCapability.ServiceID = "work-item-audit-service"
	secondCapability.CapabilityID = "work_item.audit"
	definition.CapabilityFormalizations = append(definition.CapabilityFormalizations, secondCapability)
	definition.ServiceTopologyBindings = append(definition.ServiceTopologyBindings, ServiceTopologyBinding{
		ServiceID:               "work-item-audit-service",
		ServiceName:             "Work Item Audit Service",
		SourceRole:              "application_integration",
		FormalizedCapabilityIDs: []string{"work_item.audit"},
	})

	project, err := BuildPythonProject(definition, BuildPythonProjectOptions{
		DependencySource: DependencySourceLocal,
		Port:             4100,
	})
	if err != nil {
		t.Fatalf("BuildPythonProject: %v", err)
	}

	files, err := BuildContainerArtifacts("python", project, ContainerArtifactOptions{
		Dockerfile:    true,
		DockerCompose: true,
		Port:          4100,
	})
	if err != nil {
		t.Fatalf("BuildContainerArtifacts: %v", err)
	}

	assertHasFile(t, files, "services/work_item_governance_service/Dockerfile")
	assertHasFile(t, files, "services/work_item_audit_service/Dockerfile")
	compose := fileContent(files, "docker-compose.yml")
	if !strings.Contains(compose, "work-item-governance-service:") {
		t.Fatalf("compose missing first service")
	}
	if !strings.Contains(compose, "work-item-audit-service:") {
		t.Fatalf("compose missing second service")
	}
	if !strings.Contains(compose, `ports: ["4101:4100"]`) {
		t.Fatalf("compose missing incremented host port for second service")
	}
}
