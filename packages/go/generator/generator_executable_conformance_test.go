package generator

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestGeneratorConformanceGeneratedProjectsExecute(t *testing.T) {
	if os.Getenv("ANIP_GENERATOR_EXECUTABLE_CONFORMANCE") != "1" {
		t.Skip("set ANIP_GENERATOR_EXECUTABLE_CONFORMANCE=1 to build and run generated projects for all target toolchains")
	}

	definition := mustReadGeneratorConformanceDefinition(t, "generator-conformance-definition.json")
	repoRoot := mustRepoRoot(t)
	targets := []struct {
		name  string
		build func() (*GeneratedProject, error)
		run   func(t *testing.T, outputDir string)
	}{
		{
			name: "python",
			build: func() (*GeneratedProject, error) {
				return BuildPythonProject(definition, BuildPythonProjectOptions{DependencySource: DependencySourceLocal, Transports: []Transport{TransportStdio}, Port: 4100})
			},
			run: func(t *testing.T, outputDir string) {
				python := pythonExecutable(repoRoot)
				env := append(os.Environ(),
					"PYTHONPATH="+strings.Join([]string{
						filepath.Join(outputDir, "src"),
						filepath.Join(repoRoot, "packages/python/anip-core/src"),
						filepath.Join(repoRoot, "packages/python/anip-service/src"),
						filepath.Join(repoRoot, "packages/python/anip-fastapi/src"),
						filepath.Join(repoRoot, "packages/python/anip-stdio/src"),
					}, string(os.PathListSeparator)),
				)
				runConformanceCommand(t, outputDir, env, python, "-m", "pytest", "tests")
				runGeneratedStdioSmoke(t, "python", outputDir, repoRoot)
			},
		},
		{
			name: "typescript",
			build: func() (*GeneratedProject, error) {
				return BuildTypeScriptProject(definition, BuildTypeScriptProjectOptions{DependencySource: DependencySourceLocal, HttpRuntime: HttpRuntimeHono, Transports: []Transport{TransportStdio}, Port: 4100})
			},
			run: func(t *testing.T, outputDir string) {
				env := withBehaviorMatrixActorKeys(os.Environ())
				runConformanceCommand(t, outputDir, env, "npm", "install", "--ignore-scripts", "--prefer-offline")
				runConformanceCommand(t, outputDir, env, "npm", "test")
				runGeneratedStdioSmoke(t, "typescript", outputDir, repoRoot)
			},
		},
		{
			name: "go",
			build: func() (*GeneratedProject, error) {
				return BuildGoProject(definition, BuildGoProjectOptions{DependencySource: DependencySourceLocal, Transports: []Transport{TransportStdio}, Port: 4100})
			},
			run: func(t *testing.T, outputDir string) {
				runConformanceCommand(t, outputDir, withBehaviorMatrixActorKeys(os.Environ()), "go", "test", "./...")
				runGeneratedStdioSmoke(t, "go", outputDir, repoRoot)
			},
		},
		{
			name: "java",
			build: func() (*GeneratedProject, error) {
				return BuildJavaProject(definition, BuildJavaProjectOptions{DependencySource: DependencySourceLocal, Transports: []Transport{TransportStdio}, Port: 4100})
			},
			run: func(t *testing.T, outputDir string) {
				runConformanceCommand(t, outputDir, os.Environ(), "mvn", "test")
				runGeneratedStdioSmoke(t, "java", outputDir, repoRoot)
			},
		},
		{
			name: "csharp",
			build: func() (*GeneratedProject, error) {
				return BuildCSharpProject(definition, BuildCSharpProjectOptions{DependencySource: DependencySourceLocal, Transports: []Transport{TransportStdio}, Port: 4100})
			},
			run: func(t *testing.T, outputDir string) {
				projectName := csharpProjectName(definition.Identity.SystemName)
				runConformanceCommand(t, outputDir, os.Environ(), "dotnet", "test", filepath.Join("tests", projectName+".Tests.csproj"))
				runGeneratedStdioSmoke(t, "csharp", outputDir, repoRoot)
			},
		},
	}

	for _, target := range targets {
		t.Run(target.name, func(t *testing.T) {
			if skipTarget := strings.TrimSpace(os.Getenv("ANIP_GENERATOR_EXECUTABLE_CONFORMANCE_SKIP")); skipTarget != "" {
				for _, value := range strings.Split(skipTarget, ",") {
					if strings.EqualFold(strings.TrimSpace(value), target.name) {
						t.Skipf("target %s skipped by ANIP_GENERATOR_EXECUTABLE_CONFORMANCE_SKIP", target.name)
					}
				}
			}
			project, err := target.build()
			if err != nil {
				t.Fatalf("build generated %s project: %v", target.name, err)
			}
			outputDir := filepath.Join(t.TempDir(), target.name)
			if err := WriteGeneratedProject(project, outputDir, true); err != nil {
				t.Fatalf("write generated %s project: %v", target.name, err)
			}
			writeExecutableBehaviorMatrixTest(t, target.name, outputDir)
			target.run(t, outputDir)
		})
	}
}

type generatedStdioCommand struct {
	name string
	args []string
	env  []string
}

type stdioRPCClient struct {
	cmd    *exec.Cmd
	stdin  io.WriteCloser
	lines  chan string
	stderr *bytes.Buffer
}

func runGeneratedStdioSmoke(t *testing.T, targetName string, outputDir string, repoRoot string) {
	t.Helper()
	command := generatedStdioCommandForTarget(t, targetName, outputDir, repoRoot)
	client := startGeneratedStdioProcess(t, outputDir, command)
	defer client.close()

	discovery := client.call(t, 1, "anip.discovery", nil)
	if discovery["anip_discovery"] == nil {
		t.Fatalf("%s stdio discovery did not include anip_discovery: %#v", targetName, discovery)
	}

	issued := client.call(t, 2, "anip.tokens.issue", map[string]any{
		"auth": map[string]any{
			"bearer": "dev-admin-key",
		},
		"subject":    "human:local-developer",
		"scope":      []string{"conformance.read"},
		"capability": "conformance.lookup",
	})
	token, ok := issued["token"].(string)
	if !ok || token == "" {
		t.Fatalf("%s stdio token issue did not return token: %#v", targetName, issued)
	}

	invoked := client.call(t, 3, "anip.invoke", map[string]any{
		"auth": map[string]any{
			"bearer": token,
		},
		"capability": "conformance.lookup",
		"parameters": map[string]any{
			"query": "records",
		},
	})
	if invoked["success"] != true {
		t.Fatalf("%s stdio invoke did not succeed: %#v", targetName, invoked)
	}
}

func generatedStdioCommandForTarget(t *testing.T, targetName string, outputDir string, repoRoot string) generatedStdioCommand {
	t.Helper()
	env := withBehaviorMatrixActorKeys(os.Environ())
	switch targetName {
	case "python":
		env = appendPathEnv(env, "PYTHONPATH", []string{
			filepath.Join(outputDir, "src"),
			filepath.Join(repoRoot, "packages/python/anip-core/src"),
			filepath.Join(repoRoot, "packages/python/anip-service/src"),
			filepath.Join(repoRoot, "packages/python/anip-fastapi/src"),
			filepath.Join(repoRoot, "packages/python/anip-stdio/src"),
		})
		return generatedStdioCommand{name: pythonExecutable(repoRoot), args: []string{"-m", "generator_conformance_service.stdio_app"}, env: env}
	case "typescript":
		return generatedStdioCommand{name: filepath.Join(outputDir, "node_modules", ".bin", "tsx"), args: []string{"src/stdio.ts"}, env: env}
	case "go":
		return generatedStdioCommand{name: "go", args: []string{"run", ".", "--stdio"}, env: env}
	case "java":
		return generatedStdioCommand{
			name: "mvn",
			args: []string{
				"-q",
				"org.codehaus.mojo:exec-maven-plugin:3.5.0:java",
				"-Dexec.mainClass=" + javaPackageName(systemNameToPackageName("generator-conformance-service")) + ".StdioMain",
			},
			env: env,
		}
	case "csharp":
		return generatedStdioCommand{name: "dotnet", args: []string{"run", "--project", csharpProjectName("generator-conformance-service") + ".csproj", "--", "--stdio"}, env: env}
	default:
		t.Fatalf("unsupported stdio smoke target %q", targetName)
		return generatedStdioCommand{}
	}
}

func appendPathEnv(env []string, key string, paths []string) []string {
	filtered := make([]string, 0, len(env)+1)
	prefix := key + "="
	for _, item := range env {
		if !strings.HasPrefix(item, prefix) {
			filtered = append(filtered, item)
		}
	}
	return append(filtered, prefix+strings.Join(paths, string(os.PathListSeparator)))
}

func startGeneratedStdioProcess(t *testing.T, dir string, command generatedStdioCommand) *stdioRPCClient {
	t.Helper()
	if _, err := exec.LookPath(command.name); err != nil {
		if _, statErr := os.Stat(command.name); statErr != nil {
			t.Skipf("%s not available: %v", command.name, err)
		}
	}
	cmd := exec.Command(command.name, command.args...)
	cmd.Dir = dir
	cmd.Env = command.env
	stdin, err := cmd.StdinPipe()
	if err != nil {
		t.Fatalf("create stdin pipe for %s: %v", command.name, err)
	}
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		t.Fatalf("create stdout pipe for %s: %v", command.name, err)
	}
	stderr := &bytes.Buffer{}
	cmd.Stderr = stderr
	if err := cmd.Start(); err != nil {
		t.Fatalf("start generated stdio process %s %s: %v", command.name, strings.Join(command.args, " "), err)
	}
	client := &stdioRPCClient{
		cmd:    cmd,
		stdin:  stdin,
		lines:  make(chan string, 32),
		stderr: stderr,
	}
	go func() {
		scanner := bufio.NewScanner(stdout)
		scanner.Buffer(make([]byte, 0, 64*1024), 4*1024*1024)
		for scanner.Scan() {
			client.lines <- scanner.Text()
		}
		close(client.lines)
	}()
	return client
}

func (client *stdioRPCClient) call(t *testing.T, id int, method string, params map[string]any) map[string]any {
	t.Helper()
	request := map[string]any{
		"jsonrpc": "2.0",
		"id":      id,
		"method":  method,
	}
	if params != nil {
		request["params"] = params
	}
	payload, err := json.Marshal(request)
	if err != nil {
		t.Fatalf("marshal stdio request: %v", err)
	}
	if _, err := client.stdin.Write(append(payload, '\n')); err != nil {
		t.Fatalf("write stdio request %s: %v\nstderr:\n%s", method, err, client.stderr.String())
	}

	timeout := time.After(30 * time.Second)
	for {
		select {
		case line, ok := <-client.lines:
			if !ok {
				t.Fatalf("stdio process exited before response to %s\nstderr:\n%s", method, client.stderr.String())
			}
			response, matched := parseStdioResponseForID(line, id)
			if !matched {
				continue
			}
			if errorValue := response["error"]; errorValue != nil {
				t.Fatalf("stdio method %s returned error: %#v\nstderr:\n%s", method, errorValue, client.stderr.String())
			}
			result, ok := response["result"].(map[string]any)
			if !ok {
				t.Fatalf("stdio method %s returned non-object result: %#v", method, response["result"])
			}
			return result
		case <-timeout:
			t.Fatalf("timed out waiting for stdio response to %s\nstderr:\n%s", method, client.stderr.String())
		}
	}
}

func parseStdioResponseForID(line string, id int) (map[string]any, bool) {
	var response map[string]any
	if err := json.Unmarshal([]byte(line), &response); err != nil {
		return nil, false
	}
	value, ok := response["id"]
	if !ok {
		return nil, false
	}
	switch typed := value.(type) {
	case float64:
		return response, int(typed) == id
	case string:
		return response, typed == fmt.Sprintf("%d", id)
	default:
		return response, false
	}
}

func (client *stdioRPCClient) close() {
	_ = client.stdin.Close()
	if client.cmd.Process != nil {
		_ = client.cmd.Process.Kill()
	}
	_ = client.cmd.Wait()
}

func writeExecutableBehaviorMatrixTest(t *testing.T, targetName string, outputDir string) {
	t.Helper()
	var path string
	var content string
	switch targetName {
	case "python":
		path = filepath.Join(outputDir, "tests", "test_generator_behavior_matrix.py")
		content = pythonExecutableBehaviorMatrixTest()
	case "typescript":
		path = filepath.Join(outputDir, "tests", "generator-behavior-matrix.test.ts")
		content = typeScriptExecutableBehaviorMatrixTest()
	case "go":
		path = filepath.Join(outputDir, "app", "generator_behavior_matrix_test.go")
		content = goExecutableBehaviorMatrixTest()
	case "java":
		path = filepath.Join(outputDir, "src", "test", "java", "dev", "anip", "generated", "generator_conformance_service", "GeneratedBehaviorMatrixTest.java")
		content = javaExecutableBehaviorMatrixTest()
	case "csharp":
		path = filepath.Join(outputDir, "tests", "GeneratedBehaviorMatrixTests.cs")
		content = csharpExecutableBehaviorMatrixTest()
	default:
		t.Fatalf("unsupported executable behavior matrix target %q", targetName)
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatalf("create behavior matrix test directory for %s: %v", targetName, err)
	}
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatalf("write behavior matrix test for %s: %v", targetName, err)
	}
}

func runConformanceCommand(t *testing.T, dir string, env []string, name string, args ...string) {
	t.Helper()
	if _, err := exec.LookPath(name); err != nil {
		t.Skipf("%s not available: %v", name, err)
	}
	cmd := exec.Command(name, args...)
	cmd.Dir = dir
	cmd.Env = env
	var output bytes.Buffer
	cmd.Stdout = &output
	cmd.Stderr = &output

	done := make(chan error, 1)
	if err := cmd.Start(); err != nil {
		t.Fatalf("start %s %s: %v", name, strings.Join(args, " "), err)
	}
	go func() { done <- cmd.Wait() }()

	select {
	case err := <-done:
		if err != nil {
			t.Fatalf("%s %s failed: %v\n%s", name, strings.Join(args, " "), err, output.String())
		}
	case <-time.After(3 * time.Minute):
		_ = cmd.Process.Kill()
		t.Fatalf("%s %s timed out\n%s", name, strings.Join(args, " "), output.String())
	}
}

func mustRepoRoot(t *testing.T) string {
	t.Helper()
	wd, err := os.Getwd()
	if err != nil {
		t.Fatalf("get working directory: %v", err)
	}
	return filepath.Clean(filepath.Join(wd, "..", "..", ".."))
}

func pythonExecutable(repoRoot string) string {
	candidate := filepath.Join(repoRoot, ".venv", "bin", "python")
	if _, err := os.Stat(candidate); err == nil {
		return candidate
	}
	return "python3"
}

func withBehaviorMatrixActorKeys(env []string) []string {
	filtered := make([]string, 0, len(env)+1)
	for _, item := range env {
		if strings.HasPrefix(item, "ANIP_API_KEYS_JSON=") {
			continue
		}
		filtered = append(filtered, item)
	}
	return append(filtered, `ANIP_API_KEYS_JSON={"dev-admin-key":"human:local-developer","analyst-key":"human:analyst|actor_id=analyst","manager-key":"human:manager|actor_id=manager"}`)
}

func pythonExecutableBehaviorMatrixTest() string {
	return strings.TrimLeft(`
import importlib

from fastapi.testclient import TestClient


PRINCIPALS = {
    "dev-admin-key": "human:local-developer",
    "analyst-key": "human:analyst|actor_id=analyst",
    "manager-key": "human:manager|actor_id=manager",
}


def _client() -> TestClient:
    module = importlib.import_module("generator_conformance_service.app")
    module._authenticate = lambda bearer: PRINCIPALS.get(bearer)
    return TestClient(module.create_app())


def _issue_token(client: TestClient, key: str, capability_id: str, scope: list[str]) -> str:
    response = client.post(
        "/anip/tokens",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "capability": capability_id,
            "scope": scope,
            "subject": PRINCIPALS[key],
            "purpose_parameters": {"actor_id": "analyst" if key == "analyst-key" else "manager"},
        },
    )
    assert response.status_code == 200
    return response.json()["token"]


def _invoke(client: TestClient, key: str, capability_id: str, scope: list[str], parameters: dict, requested_effects: list[str] | None = None) -> dict:
    token = _issue_token(client, key, capability_id, scope)
    response = client.post(
        f"/anip/invoke/{capability_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"parameters": parameters, "requested_effects": requested_effects or []},
    )
    assert response.status_code in (200, 400, 403)
    return response.json()


def _assert_failure_type(payload: dict, failure_type: str) -> None:
    assert payload["success"] is False
    assert payload["failure"]["type"] == failure_type


def _assert_resolution_action(payload: dict, action: str) -> None:
    assert payload["failure"]["resolution"]["action"] == action


def _assert_approval_required(payload: dict) -> None:
    _assert_failure_type(payload, "approval_required")
    failure = payload["failure"]
    assert failure["resolution"]["action"] == "request_approval"
    assert failure["approval_required"]["approval_request_id"]
    assert failure["approval_required"]["grant_policy"]["default_grant_type"] in ("one_time", "session_bound")


def test_behavior_matrix_lookup_success() -> None:
    payload = _invoke(_client(), "analyst-key", "conformance.lookup", ["conformance.read"], {"query": "records"})
    assert payload["success"] is True
    assert payload["result"]["execution_status"] == "backend_execution_stub"


def test_behavior_matrix_lookup_filters_unknown_inputs() -> None:
    payload = _invoke(
        _client(),
        "analyst-key",
        "conformance.lookup",
        ["conformance.read"],
        {"query": "records", "limit": 3, "unexpected_extra": "leak"},
    )
    assert payload["success"] is True
    assert payload["result"]["semantic_input"] == {"query": "records", "limit": 3}
    assert payload["result"]["backend_input_contract"] == {"mode": "implicit", "required": ["query"], "optional": ["limit"]}


def test_behavior_matrix_on_missing_defaults_and_omits() -> None:
    payload = _invoke(_client(), "analyst-key", "conformance.lookup", ["conformance.read"], {"query": "records"})
    assert payload["success"] is True
    assert payload["result"]["semantic_input"] == {"query": "records", "limit": "10"}


def test_behavior_matrix_omit_input_passes_when_explicit() -> None:
    payload = _invoke(
        _client(),
        "analyst-key",
        "conformance.lookup",
        ["conformance.read"],
        {"query": "records", "debug_trace": True},
    )
    assert payload["success"] is True
    assert payload["result"]["semantic_input"]["debug_trace"] is True


def test_behavior_matrix_missing_required_input_clarifies() -> None:
    payload = _invoke(_client(), "analyst-key", "conformance.lookup", ["conformance.read"], {})
    _assert_failure_type(payload, "clarification_required")
    _assert_resolution_action(payload, "obtain_binding")


def test_behavior_matrix_requested_forbidden_effect_denies_before_missing_inputs() -> None:
    payload = _invoke(
        _client(),
        "analyst-key",
        "conformance.lookup",
        ["conformance.read"],
        {},
        requested_effects=["raw_data_export"],
    )
    _assert_failure_type(payload, "denied")
    _assert_resolution_action(payload, "request_declared_capability")


def test_behavior_matrix_insufficient_scope_is_denied_before_execution() -> None:
    payload = _invoke(
        _client(),
        "dev-admin-key",
        "conformance.prepare_change",
        ["conformance.read"],
        {"record_ref": "CON-1", "new_status": "done", "change_reason": "conformance test"},
    )
    _assert_failure_type(payload, "scope_insufficient")
    _assert_resolution_action(payload, "request_broader_scope")


def test_behavior_matrix_backend_only_required_input_blocks_stub_execution() -> None:
    payload = _invoke(
        _client(),
        "dev-admin-key",
        "conformance.prepare_change",
        ["conformance.prepare"],
        {"record_ref": "CON-1", "new_status": "done"},
    )
    assert payload["success"] is True
    result = payload["result"]
    assert result["execution_status"] == "backend_input_incomplete"
    assert result["backend_input_contract"]["mode"] == "hybrid"
    assert result["backend_input_contract"]["required"] == ["record_ref", "new_status", "change_reason"]
    assert result["backend_input_contract"]["optional"] == []
    assert result["unresolved_required_backend_inputs"] == ["change_reason"]


def test_behavior_matrix_backend_resolved_input_accepts_open_reference() -> None:
    payload = _invoke(
        _client(),
        "dev-admin-key",
        "conformance.prepare_change",
        ["conformance.prepare"],
        {"record_ref": "Arbitrary Customer 42", "new_status": "done", "change_reason": "conformance test"},
    )
    assert payload["success"] is True
    assert payload["result"]["execution_status"] == "backend_execution_stub"
    assert payload["result"]["semantic_input"]["record_ref"] == "Arbitrary Customer 42"


def test_behavior_matrix_backend_resolved_metadata_is_declared() -> None:
    module = importlib.import_module("generator_conformance_service.capabilities")
    declaration = module.generated_declaration_for_capability("conformance.prepare_change")
    record_ref = next(item for item in declaration.inputs if item.name == "record_ref")
    assert record_ref.entity_reference is True
    assert record_ref.catalog_ref == "conformance.record_catalog"
    assert record_ref.resolution.mode.value == "backend_resolved"
    assert record_ref.resolution.resolver_ref == "conformance.record_catalog"


def test_behavior_matrix_resolution_metadata_is_declared() -> None:
    module = importlib.import_module("generator_conformance_service.capabilities")
    lookup = module.generated_declaration_for_capability("conformance.lookup")
    debug_trace = next(item for item in lookup.inputs if item.name == "debug_trace")
    assert debug_trace.resolution.mode.value == "explicit_only"
    assert debug_trace.resolution.on_missing.value == "omit"

    prepare_change = module.generated_declaration_for_capability("conformance.prepare_change")
    new_status = next(item for item in prepare_change.inputs if item.name == "new_status")
    assert new_status.allowed_values == ["todo", "in_progress", "done"]
    assert new_status.catalog_ref == "conformance.status_catalog"
    assert new_status.resolution.mode.value == "closed_values"
    assert new_status.resolution.on_unresolved.value == "deny"


def test_behavior_matrix_closed_values_deny_unresolved_value() -> None:
    payload = _invoke(
        _client(),
        "dev-admin-key",
        "conformance.prepare_change",
        ["conformance.prepare"],
        {"record_ref": "CON-1", "new_status": "archived", "change_reason": "conformance test"},
    )
    _assert_failure_type(payload, "denied")
    _assert_resolution_action(payload, "contact_service_owner")


def test_behavior_matrix_analyst_change_is_denied() -> None:
    payload = _invoke(
        _client(),
        "analyst-key",
        "conformance.prepare_change",
        ["conformance.prepare"],
        {"record_ref": "CON-1", "new_status": "done", "change_reason": "conformance test"},
    )
    _assert_failure_type(payload, "denied")
    _assert_resolution_action(payload, "contact_service_owner")


def test_behavior_matrix_manager_change_requires_approval() -> None:
    payload = _invoke(
        _client(),
        "manager-key",
        "conformance.prepare_change",
        ["conformance.prepare"],
        {"record_ref": "CON-1", "new_status": "done", "change_reason": "conformance test"},
    )
    _assert_approval_required(payload)


def test_behavior_matrix_composed_success_returns_mapped_child_output() -> None:
    payload = _invoke(
        _client(),
        "dev-admin-key",
        "conformance.lookup_and_prepare",
        ["conformance.read", "conformance.prepare"],
        {"query": "CON-1", "requested_status": "done", "change_reason": "conformance test"},
    )
    assert payload["success"] is True
    assert payload["result"]["prepared_status"] == "backend_execution_stub"


def test_behavior_matrix_composed_child_denial_propagates() -> None:
    payload = _invoke(
        _client(),
        "dev-admin-key",
        "conformance.lookup_and_prepare",
        ["conformance.read", "conformance.prepare"],
        {"query": "CON-1", "requested_status": "archived", "change_reason": "conformance test"},
    )
    _assert_failure_type(payload, "denied")
    _assert_resolution_action(payload, "contact_service_owner")


def test_behavior_matrix_composed_manager_change_requires_approval() -> None:
    payload = _invoke(
        _client(),
        "manager-key",
        "conformance.lookup_and_prepare",
        ["conformance.read", "conformance.prepare"],
        {"query": "CON-1", "requested_status": "done", "change_reason": "conformance test"},
    )
    _assert_approval_required(payload)
`, "\n")
}

func typeScriptExecutableBehaviorMatrixTest() string {
	return strings.TrimLeft(`
import { describe, expect, it } from "vitest";
import { app } from "../src/app.js";
import { generatedCapabilities } from "../src/generated/capabilities.js";

async function issueToken(key: string, capabilityId: string, scope: string[]) {
  const response = await app.request("/anip/tokens", {
    method: "POST",
    headers: {
      authorization: "Bearer " + key,
      "content-type": "application/json",
    },
    body: JSON.stringify({ capability: capabilityId, scope, subject: key }),
  });
  expect(response.status).toBe(200);
  const body = await response.json() as { token: string };
  return body.token;
}

async function invoke(key: string, capabilityId: string, scope: string[], parameters: Record<string, unknown>) {
  const token = await issueToken(key, capabilityId, scope);
  const response = await app.request("/anip/invoke/" + capabilityId, {
    method: "POST",
    headers: {
      authorization: "Bearer " + token,
      "content-type": "application/json",
    },
    body: JSON.stringify({ parameters }),
  });
  expect([200, 400, 403]).toContain(response.status);
  return await response.json() as {
    success: boolean;
    result?: {
      execution_status?: string;
      semantic_input?: Record<string, unknown>;
      backend_input_contract?: { mode?: string; required?: string[]; optional?: string[] };
      unresolved_required_backend_inputs?: string[];
      prepared_status?: string;
    };
    failure?: {
      type?: string;
      resolution?: { action?: string };
      approval_required?: {
        approval_request_id?: string;
        grant_policy?: { default_grant_type?: string };
      };
    };
  };
}

function expectFailureType(payload: { success: boolean; failure?: { type?: string } }, failureType: string) {
  expect(payload.success).toBe(false);
  expect(payload.failure?.type).toBe(failureType);
}

function expectResolutionAction(payload: Awaited<ReturnType<typeof invoke>>, action: string) {
  expect(payload.failure?.resolution?.action).toBe(action);
}

function expectApprovalRequired(payload: Awaited<ReturnType<typeof invoke>>) {
  expectFailureType(payload, "approval_required");
  expect(payload.failure?.resolution?.action).toBe("request_approval");
  expect(payload.failure?.approval_required?.approval_request_id).toBeTruthy();
  expect(["one_time", "session_bound"]).toContain(payload.failure?.approval_required?.grant_policy?.default_grant_type);
}

describe("generated behavior matrix", () => {
  it("allows bounded analyst lookup", async () => {
    const payload = await invoke("analyst-key", "conformance.lookup", ["conformance.read"], { query: "records" });
    expect(payload.success).toBe(true);
    expect(payload.result?.execution_status).toBe("backend_execution_stub");
  });

  it("filters unknown inputs from semantic input", async () => {
    const payload = await invoke("analyst-key", "conformance.lookup", ["conformance.read"], {
      query: "records",
      limit: 3,
      unexpected_extra: "leak",
    });
    expect(payload.success).toBe(true);
    expect(payload.result?.semantic_input).toEqual({ query: "records", limit: 3 });
    expect(payload.result?.backend_input_contract).toEqual({ mode: "implicit", required: ["query"], optional: ["limit"] });
  });

  it("applies use_default and honors omit for missing inputs", async () => {
    const payload = await invoke("analyst-key", "conformance.lookup", ["conformance.read"], { query: "records" });
    expect(payload.success).toBe(true);
    expect(payload.result?.semantic_input).toEqual({ query: "records", limit: "10" });
  });

  it("passes omitted input when explicitly supplied", async () => {
    const payload = await invoke("analyst-key", "conformance.lookup", ["conformance.read"], {
      query: "records",
      debug_trace: true,
    });
    expect(payload.success).toBe(true);
    expect(payload.result?.semantic_input?.debug_trace).toBe(true);
  });

  it("clarifies missing required semantic input", async () => {
    const payload = await invoke("analyst-key", "conformance.lookup", ["conformance.read"], {});
    expectFailureType(payload, "clarification_required");
    expectResolutionAction(payload, "obtain_binding");
  });

  it("denies insufficient scope before execution", async () => {
    const payload = await invoke("dev-admin-key", "conformance.prepare_change", ["conformance.read"], {
      record_ref: "CON-1",
      new_status: "done",
      change_reason: "conformance test",
    });
    expectFailureType(payload, "scope_insufficient");
    expectResolutionAction(payload, "request_broader_scope");
  });

  it("blocks generated stub execution when backend-only inputs are unresolved", async () => {
    const payload = await invoke("dev-admin-key", "conformance.prepare_change", ["conformance.prepare"], {
      record_ref: "CON-1",
      new_status: "done",
    });
    expect(payload.success).toBe(true);
    expect(payload.result?.execution_status).toBe("backend_input_incomplete");
    expect(payload.result?.backend_input_contract?.mode).toBe("hybrid");
    expect(payload.result?.backend_input_contract?.required).toEqual(["record_ref", "new_status", "change_reason"]);
    expect(payload.result?.backend_input_contract?.optional).toEqual([]);
    expect(payload.result?.unresolved_required_backend_inputs).toEqual(["change_reason"]);
  });

  it("accepts open references for backend-resolved inputs", async () => {
    const payload = await invoke("dev-admin-key", "conformance.prepare_change", ["conformance.prepare"], {
      record_ref: "Arbitrary Customer 42",
      new_status: "done",
      change_reason: "conformance test",
    });
    expect(payload.success).toBe(true);
    expect(payload.result?.execution_status).toBe("backend_execution_stub");
    expect(payload.result?.semantic_input?.record_ref).toBe("Arbitrary Customer 42");
  });

  it("declares backend-resolved resolver metadata", async () => {
    const capability = generatedCapabilities.find((item) => item.declaration.name === "conformance.prepare_change");
    const recordRef = capability?.declaration.inputs.find((item) => item.name === "record_ref");
    expect(recordRef?.entity_reference).toBe(true);
    expect(recordRef?.catalog_ref).toBe("conformance.record_catalog");
    expect(recordRef?.resolution?.mode).toBe("backend_resolved");
    expect(recordRef?.resolution?.resolver_ref).toBe("conformance.record_catalog");
  });

  it("declares input resolution metadata", async () => {
    const lookup = generatedCapabilities.find((item) => item.declaration.name === "conformance.lookup");
    const debugTrace = lookup?.declaration.inputs.find((item) => item.name === "debug_trace");
    expect(debugTrace?.resolution?.mode).toBe("explicit_only");
    expect(debugTrace?.resolution?.on_missing).toBe("omit");

    const prepareChange = generatedCapabilities.find((item) => item.declaration.name === "conformance.prepare_change");
    const newStatus = prepareChange?.declaration.inputs.find((item) => item.name === "new_status");
    expect(newStatus?.allowed_values).toEqual(["todo", "in_progress", "done"]);
    expect(newStatus?.catalog_ref).toBe("conformance.status_catalog");
    expect(newStatus?.resolution?.mode).toBe("closed_values");
    expect(newStatus?.resolution?.on_unresolved).toBe("deny");
  });

  it("denies closed-values inputs when unresolved behavior is deny", async () => {
    const payload = await invoke("dev-admin-key", "conformance.prepare_change", ["conformance.prepare"], {
      record_ref: "CON-1",
      new_status: "archived",
      change_reason: "conformance test",
    });
    expectFailureType(payload, "denied");
    expectResolutionAction(payload, "contact_service_owner");
  });

  it("denies analyst changes", async () => {
    const payload = await invoke("analyst-key", "conformance.prepare_change", ["conformance.prepare"], {
      record_ref: "CON-1",
      new_status: "done",
      change_reason: "conformance test",
    });
    expectFailureType(payload, "denied");
    expectResolutionAction(payload, "contact_service_owner");
  });

  it("requires manager approval for changes", async () => {
    const payload = await invoke("manager-key", "conformance.prepare_change", ["conformance.prepare"], {
      record_ref: "CON-1",
      new_status: "done",
      change_reason: "conformance test",
    });
    expectApprovalRequired(payload);
  });

  it("returns mapped child output for successful composition", async () => {
    const payload = await invoke("dev-admin-key", "conformance.lookup_and_prepare", ["conformance.read", "conformance.prepare"], {
      query: "CON-1",
      requested_status: "done",
      change_reason: "conformance test",
    });
    expect(payload.success).toBe(true);
    expect(payload.result?.prepared_status).toBe("backend_execution_stub");
  });

  it("propagates child denial for composed invalid status", async () => {
    const payload = await invoke("dev-admin-key", "conformance.lookup_and_prepare", ["conformance.read", "conformance.prepare"], {
      query: "CON-1",
      requested_status: "archived",
      change_reason: "conformance test",
    });
    expectFailureType(payload, "denied");
    expectResolutionAction(payload, "contact_service_owner");
  });

  it("propagates approval posture for composed manager changes", async () => {
    const payload = await invoke("manager-key", "conformance.lookup_and_prepare", ["conformance.read", "conformance.prepare"], {
      query: "CON-1",
      requested_status: "done",
      change_reason: "conformance test",
    });
    expectApprovalRequired(payload);
  });
});
`, "\n")
}

func goExecutableBehaviorMatrixTest() string {
	return strings.TrimLeft(`
package app

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	generatedhost "generated/generator-conformance-service/host"
)

func issueBehaviorMatrixToken(t *testing.T, ts *httptest.Server, key string, capabilityID string, scope []string) string {
	t.Helper()
	body := map[string]any{
		"capability": capabilityID,
		"scope":      scope,
		"subject":    key,
	}
	bodyBytes, _ := json.Marshal(body)
	req, _ := http.NewRequest(http.MethodPost, ts.URL+"/anip/tokens", bytes.NewReader(bodyBytes))
	req.Header.Set("Authorization", "Bearer "+key)
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("token request failed: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("expected 200 from token endpoint, got %d", resp.StatusCode)
	}
	var payload map[string]any
	_ = json.NewDecoder(resp.Body).Decode(&payload)
	token, _ := payload["token"].(string)
	if token == "" {
		t.Fatal("expected token in response")
	}
	return token
}

func invokeBehaviorMatrixCapability(t *testing.T, ts *httptest.Server, key string, capabilityID string, scope []string, parameters map[string]any) map[string]any {
	t.Helper()
	token := issueBehaviorMatrixToken(t, ts, key, capabilityID, scope)
	body := map[string]any{"parameters": parameters}
	bodyBytes, _ := json.Marshal(body)
	req, _ := http.NewRequest(http.MethodPost, ts.URL+"/anip/invoke/"+capabilityID, bytes.NewReader(bodyBytes))
	req.Header.Set("Authorization", "Bearer "+token)
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("invoke request failed: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusBadRequest && resp.StatusCode != http.StatusForbidden {
		t.Fatalf("expected 200, 400, or 403 from invoke, got %d", resp.StatusCode)
	}
	var payload map[string]any
	_ = json.NewDecoder(resp.Body).Decode(&payload)
	return payload
}

func assertBehaviorMatrixFailureType(t *testing.T, payload map[string]any, failureType string) {
	t.Helper()
	if payload["success"] != false {
		t.Fatalf("expected failure payload, got %#v", payload)
	}
	failure, ok := payload["failure"].(map[string]any)
	if !ok {
		t.Fatalf("expected failure object, got %#v", payload["failure"])
	}
	if failure["type"] != failureType {
		t.Fatalf("expected failure type %q, got %#v", failureType, failure["type"])
	}
}

func assertBehaviorMatrixResolutionAction(t *testing.T, payload map[string]any, action string) {
	t.Helper()
	failure, _ := payload["failure"].(map[string]any)
	resolution, ok := failure["resolution"].(map[string]any)
	if !ok || resolution["action"] != action {
		t.Fatalf("expected resolution action %q, got %#v", action, failure["resolution"])
	}
}

func assertBehaviorMatrixApprovalRequired(t *testing.T, payload map[string]any) {
	t.Helper()
	assertBehaviorMatrixFailureType(t, payload, "approval_required")
	failure, _ := payload["failure"].(map[string]any)
	resolution, ok := failure["resolution"].(map[string]any)
	if !ok || resolution["action"] != "request_approval" {
		t.Fatalf("expected request_approval resolution, got %#v", failure["resolution"])
	}
	approvalRequired, ok := failure["approval_required"].(map[string]any)
	if !ok || approvalRequired["approval_request_id"] == "" {
		t.Fatalf("expected approval_required metadata, got %#v", failure["approval_required"])
	}
	grantPolicy, ok := approvalRequired["grant_policy"].(map[string]any)
	if !ok || grantPolicy["default_grant_type"] == "" {
		t.Fatalf("expected approval grant policy, got %#v", approvalRequired["grant_policy"])
	}
}

func TestGeneratedBehaviorMatrix(t *testing.T) {
	svc, err := NewService()
	if err != nil {
		t.Fatalf("NewService: %v", err)
	}
	defer svc.Shutdown()
	ts := httptest.NewServer(NewMux(svc))
	defer ts.Close()

	lookup := invokeBehaviorMatrixCapability(t, ts, "analyst-key", "conformance.lookup", []string{"conformance.read"}, map[string]any{"query": "records"})
	if lookup["success"] != true {
		t.Fatalf("expected successful lookup, got %#v", lookup)
	}
	result, ok := lookup["result"].(map[string]any)
	if !ok || result["execution_status"] != "backend_execution_stub" {
		t.Fatalf("expected backend_execution_stub, got %#v", lookup["result"])
	}

	filtered := invokeBehaviorMatrixCapability(t, ts, "analyst-key", "conformance.lookup", []string{"conformance.read"}, map[string]any{
		"query":            "records",
		"limit":            float64(3),
		"unexpected_extra": "leak",
	})
	filteredResult, ok := filtered["result"].(map[string]any)
	if !ok {
		t.Fatalf("expected result object, got %#v", filtered["result"])
	}
	semanticInput, ok := filteredResult["semantic_input"].(map[string]any)
	if !ok {
		t.Fatalf("expected semantic_input object, got %#v", filteredResult["semantic_input"])
	}
	if semanticInput["query"] != "records" || semanticInput["limit"] != float64(3) {
		t.Fatalf("expected semantic input to keep declared values, got %#v", semanticInput)
	}
	if _, ok := semanticInput["unexpected_extra"]; ok {
		t.Fatalf("semantic input leaked unexpected_extra: %#v", semanticInput)
	}
	lookupContract, ok := filteredResult["backend_input_contract"].(map[string]any)
	if !ok || lookupContract["mode"] != "implicit" {
		t.Fatalf("expected implicit lookup backend input contract, got %#v", filteredResult["backend_input_contract"])
	}
	lookupRequired, ok := lookupContract["required"].([]any)
	if !ok || len(lookupRequired) != 1 || lookupRequired[0] != "query" {
		t.Fatalf("expected lookup backend required query, got %#v", lookupContract["required"])
	}
	lookupOptional, ok := lookupContract["optional"].([]any)
	if !ok || len(lookupOptional) != 1 || lookupOptional[0] != "limit" {
		t.Fatalf("expected lookup backend optional limit, got %#v", lookupContract["optional"])
	}

	defaulted := invokeBehaviorMatrixCapability(t, ts, "analyst-key", "conformance.lookup", []string{"conformance.read"}, map[string]any{"query": "records"})
	defaultedResult, ok := defaulted["result"].(map[string]any)
	if !ok {
		t.Fatalf("expected defaulted result object, got %#v", defaulted["result"])
	}
	defaultedSemanticInput, ok := defaultedResult["semantic_input"].(map[string]any)
	if !ok || defaultedSemanticInput["query"] != "records" || defaultedSemanticInput["limit"] != "10" {
		t.Fatalf("expected defaulted limit, got %#v", defaultedResult["semantic_input"])
	}
	if _, ok := defaultedSemanticInput["debug_trace"]; ok {
		t.Fatalf("on_missing=omit input should not be defaulted: %#v", defaultedSemanticInput)
	}

	explicitOmit := invokeBehaviorMatrixCapability(t, ts, "analyst-key", "conformance.lookup", []string{"conformance.read"}, map[string]any{
		"query":       "records",
		"debug_trace": true,
	})
	explicitOmitResult, ok := explicitOmit["result"].(map[string]any)
	if !ok {
		t.Fatalf("expected explicit omit result object, got %#v", explicitOmit["result"])
	}
	explicitOmitSemanticInput, ok := explicitOmitResult["semantic_input"].(map[string]any)
	if !ok || explicitOmitSemanticInput["debug_trace"] != true {
		t.Fatalf("expected explicit omit input to pass through, got %#v", explicitOmitResult["semantic_input"])
	}

	missing := invokeBehaviorMatrixCapability(t, ts, "analyst-key", "conformance.lookup", []string{"conformance.read"}, map[string]any{})
	assertBehaviorMatrixFailureType(t, missing, "clarification_required")
	assertBehaviorMatrixResolutionAction(t, missing, "obtain_binding")

	insufficientScope := invokeBehaviorMatrixCapability(t, ts, "dev-admin-key", "conformance.prepare_change", []string{"conformance.read"}, map[string]any{
		"record_ref":    "CON-1",
		"new_status":    "done",
		"change_reason": "conformance test",
	})
	assertBehaviorMatrixFailureType(t, insufficientScope, "scope_insufficient")
	assertBehaviorMatrixResolutionAction(t, insufficientScope, "request_broader_scope")

	backendIncomplete := invokeBehaviorMatrixCapability(t, ts, "dev-admin-key", "conformance.prepare_change", []string{"conformance.prepare"}, map[string]any{
		"record_ref": "CON-1",
		"new_status": "done",
	})
	if backendIncomplete["success"] != true {
		t.Fatalf("expected backend-incomplete success envelope, got %#v", backendIncomplete)
	}
	backendResult, ok := backendIncomplete["result"].(map[string]any)
	if !ok || backendResult["execution_status"] != "backend_input_incomplete" {
		t.Fatalf("expected backend_input_incomplete, got %#v", backendIncomplete["result"])
	}
	backendContract, ok := backendResult["backend_input_contract"].(map[string]any)
	if !ok || backendContract["mode"] != "hybrid" {
		t.Fatalf("expected hybrid backend input contract, got %#v", backendResult["backend_input_contract"])
	}
	backendRequired, ok := backendContract["required"].([]any)
	if !ok || len(backendRequired) != 3 || backendRequired[0] != "record_ref" || backendRequired[1] != "new_status" || backendRequired[2] != "change_reason" {
		t.Fatalf("expected hybrid required inputs, got %#v", backendContract["required"])
	}
	backendOptional, ok := backendContract["optional"].([]any)
	if !ok || len(backendOptional) != 0 {
		t.Fatalf("expected no hybrid optional inputs, got %#v", backendContract["optional"])
	}
	unresolved, ok := backendResult["unresolved_required_backend_inputs"].([]any)
	if !ok || len(unresolved) != 1 || unresolved[0] != "change_reason" {
		t.Fatalf("expected unresolved change_reason, got %#v", backendResult["unresolved_required_backend_inputs"])
	}

	openReference := invokeBehaviorMatrixCapability(t, ts, "dev-admin-key", "conformance.prepare_change", []string{"conformance.prepare"}, map[string]any{
		"record_ref":    "Arbitrary Customer 42",
		"new_status":    "done",
		"change_reason": "conformance test",
	})
	if openReference["success"] != true {
		t.Fatalf("expected backend-resolved open reference to reach backend plan, got %#v", openReference)
	}
	openReferenceResult, ok := openReference["result"].(map[string]any)
	if !ok || openReferenceResult["execution_status"] != "backend_execution_stub" {
		t.Fatalf("expected backend_execution_stub plan, got %#v", openReference["result"])
	}
	openReferenceSemanticInput, ok := openReferenceResult["semantic_input"].(map[string]any)
	if !ok || openReferenceSemanticInput["record_ref"] != "Arbitrary Customer 42" {
		t.Fatalf("expected open record_ref in semantic input, got %#v", openReferenceResult["semantic_input"])
	}

	var recordRefResolutionMode string
	var recordRefResolverRef string
	for _, capability := range generatedhost.GeneratedCapabilities {
		if capability.Declaration.Name != "conformance.prepare_change" {
			continue
		}
		for _, input := range capability.Declaration.Inputs {
			if input.Name == "record_ref" && input.Resolution != nil {
				recordRefResolutionMode = string(input.Resolution.Mode)
				if input.Resolution.ResolverRef != nil {
					recordRefResolverRef = *input.Resolution.ResolverRef
				}
			}
		}
	}
	if recordRefResolutionMode != "backend_resolved" || recordRefResolverRef != "conformance.record_catalog" {
		t.Fatalf("expected backend-resolved resolver metadata, got mode=%q resolver_ref=%q", recordRefResolutionMode, recordRefResolverRef)
	}

	var debugTraceResolutionMode string
	var debugTraceOnMissing string
	for _, capability := range generatedhost.GeneratedCapabilities {
		if capability.Declaration.Name != "conformance.lookup" {
			continue
		}
		for _, input := range capability.Declaration.Inputs {
			if input.Name == "debug_trace" && input.Resolution != nil {
				debugTraceResolutionMode = string(input.Resolution.Mode)
				if input.Resolution.OnMissing != nil {
					debugTraceOnMissing = string(*input.Resolution.OnMissing)
				}
			}
		}
	}
	if debugTraceResolutionMode != "explicit_only" || debugTraceOnMissing != "omit" {
		t.Fatalf("expected explicit-only omit metadata, got mode=%q on_missing=%q", debugTraceResolutionMode, debugTraceOnMissing)
	}

	var newStatusAllowed []string
	var newStatusCatalogRef string
	var newStatusResolutionMode string
	var newStatusOnUnresolved string
	for _, capability := range generatedhost.GeneratedCapabilities {
		if capability.Declaration.Name != "conformance.prepare_change" {
			continue
		}
		for _, input := range capability.Declaration.Inputs {
			if input.Name == "new_status" {
				newStatusAllowed = input.AllowedValues
				if input.CatalogRef != nil {
					newStatusCatalogRef = *input.CatalogRef
				}
				if input.Resolution != nil {
					newStatusResolutionMode = string(input.Resolution.Mode)
					if input.Resolution.OnUnresolved != nil {
						newStatusOnUnresolved = string(*input.Resolution.OnUnresolved)
					}
				}
			}
		}
	}
	if len(newStatusAllowed) != 3 || newStatusAllowed[0] != "todo" || newStatusAllowed[1] != "in_progress" || newStatusAllowed[2] != "done" {
		t.Fatalf("expected new_status allowed values, got %#v", newStatusAllowed)
	}
	if newStatusCatalogRef != "conformance.status_catalog" || newStatusResolutionMode != "closed_values" || newStatusOnUnresolved != "deny" {
		t.Fatalf("expected closed-values metadata, got catalog=%q mode=%q on_unresolved=%q", newStatusCatalogRef, newStatusResolutionMode, newStatusOnUnresolved)
	}

	invalidStatus := invokeBehaviorMatrixCapability(t, ts, "dev-admin-key", "conformance.prepare_change", []string{"conformance.prepare"}, map[string]any{
		"record_ref":    "CON-1",
		"new_status":    "archived",
		"change_reason": "conformance test",
	})
	assertBehaviorMatrixFailureType(t, invalidStatus, "denied")
	assertBehaviorMatrixResolutionAction(t, invalidStatus, "contact_service_owner")

	denied := invokeBehaviorMatrixCapability(t, ts, "analyst-key", "conformance.prepare_change", []string{"conformance.prepare"}, map[string]any{
		"record_ref":    "CON-1",
		"new_status":    "done",
		"change_reason": "conformance test",
	})
	assertBehaviorMatrixFailureType(t, denied, "denied")
	assertBehaviorMatrixResolutionAction(t, denied, "contact_service_owner")

	approval := invokeBehaviorMatrixCapability(t, ts, "manager-key", "conformance.prepare_change", []string{"conformance.prepare"}, map[string]any{
		"record_ref":    "CON-1",
		"new_status":    "done",
		"change_reason": "conformance test",
	})
	assertBehaviorMatrixApprovalRequired(t, approval)

	composedSuccess := invokeBehaviorMatrixCapability(t, ts, "dev-admin-key", "conformance.lookup_and_prepare", []string{"conformance.read", "conformance.prepare"}, map[string]any{
		"query":            "CON-1",
		"requested_status": "done",
		"change_reason":    "conformance test",
	})
	if composedSuccess["success"] != true {
		t.Fatalf("expected successful composed invocation, got %#v", composedSuccess)
	}
	composedSuccessResult, ok := composedSuccess["result"].(map[string]any)
	if !ok || composedSuccessResult["prepared_status"] != "backend_execution_stub" {
		t.Fatalf("expected composed backend_execution_stub, got %#v", composedSuccess["result"])
	}

	composedDenied := invokeBehaviorMatrixCapability(t, ts, "dev-admin-key", "conformance.lookup_and_prepare", []string{"conformance.read", "conformance.prepare"}, map[string]any{
		"query":            "CON-1",
		"requested_status": "archived",
		"change_reason":    "conformance test",
	})
	assertBehaviorMatrixFailureType(t, composedDenied, "denied")
	assertBehaviorMatrixResolutionAction(t, composedDenied, "contact_service_owner")

	composedApproval := invokeBehaviorMatrixCapability(t, ts, "manager-key", "conformance.lookup_and_prepare", []string{"conformance.read", "conformance.prepare"}, map[string]any{
		"query":            "CON-1",
		"requested_status": "done",
		"change_reason":    "conformance test",
	})
	assertBehaviorMatrixApprovalRequired(t, composedApproval)
}
`, "\n")
}

func javaExecutableBehaviorMatrixTest() string {
	return strings.TrimLeft(`
package dev.anip.generated.generator_conformance_service;

import dev.anip.core.DelegationToken;
import dev.anip.core.ResolutionBehavior;
import dev.anip.core.ResolutionMode;
import dev.anip.core.TokenResponse;
import dev.anip.service.ANIPService;
import dev.anip.service.InvokeOpts;
import dev.anip.service.ServiceConfig;

import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class GeneratedBehaviorMatrixTest {
    private ANIPService newService() throws Exception {
        ANIPService service = new ANIPService(new ServiceConfig()
                .setServiceId("generator-conformance-service")
                .setCapabilities(GeneratedCapabilities.createAll(BackendAdapter.defaultAdapter()))
                .setStorage(":memory:")
                .setTrust("signed")
                .setKeyPath(null));
        service.start();
        return service;
    }

    private DelegationToken issue(ANIPService service, String principal, String capability, List<String> scope) throws Exception {
        TokenResponse response = service.issueCapabilityToken(principal, capability, scope);
        return service.resolveBearerToken(response.getToken());
    }

    private Map<String, Object> invoke(ANIPService service, String principal, String capability, List<String> scope, Map<String, Object> parameters) throws Exception {
        return service.invoke(capability, issue(service, principal, capability, scope), parameters, new InvokeOpts());
    }

    @SuppressWarnings("unchecked")
    private void assertFailureType(Map<String, Object> payload, String failureType) {
        assertFalse((Boolean) payload.get("success"));
        Map<String, Object> failure = (Map<String, Object>) payload.get("failure");
        assertEquals(failureType, failure.get("type"));
    }

    @SuppressWarnings("unchecked")
    private void assertResolutionAction(Map<String, Object> payload, String action) {
        Map<String, Object> failure = (Map<String, Object>) payload.get("failure");
        Map<String, Object> resolution = (Map<String, Object>) failure.get("resolution");
        assertEquals(action, resolution.get("action"));
    }

    @SuppressWarnings("unchecked")
    private void assertApprovalRequired(Map<String, Object> payload) {
        assertFailureType(payload, "approval_required");
        Map<String, Object> failure = (Map<String, Object>) payload.get("failure");
        Map<String, Object> resolution = (Map<String, Object>) failure.get("resolution");
        assertEquals("request_approval", resolution.get("action"));
        Map<String, Object> approvalRequired = (Map<String, Object>) failure.get("approval_required");
        assertTrue(String.valueOf(approvalRequired.get("approval_request_id")).length() > 0);
        Map<String, Object> grantPolicy = (Map<String, Object>) approvalRequired.get("grant_policy");
        assertTrue(String.valueOf(grantPolicy.get("default_grant_type")).length() > 0);
    }

    @Test
    void generatedBehaviorMatrixMatchesContractPolicy() throws Exception {
        ANIPService service = newService();
        try {
            Map<String, Object> lookup = invoke(
                    service,
                    "human:analyst|actor_id=analyst",
                    "conformance.lookup",
                    List.of("conformance.read"),
                    Map.of("query", "records"));
            assertTrue((Boolean) lookup.get("success"));
            @SuppressWarnings("unchecked")
            Map<String, Object> result = (Map<String, Object>) lookup.get("result");
            assertEquals("backend_execution_stub", result.get("execution_status"));

            Map<String, Object> filtered = invoke(
                    service,
                    "human:analyst|actor_id=analyst",
                    "conformance.lookup",
                    List.of("conformance.read"),
                    Map.of("query", "records", "limit", 3, "unexpected_extra", "leak"));
            @SuppressWarnings("unchecked")
            Map<String, Object> filteredResult = (Map<String, Object>) filtered.get("result");
            @SuppressWarnings("unchecked")
            Map<String, Object> semanticInput = (Map<String, Object>) filteredResult.get("semantic_input");
            assertEquals(Map.of("query", "records", "limit", 3), semanticInput);
            @SuppressWarnings("unchecked")
            Map<String, Object> lookupContract = (Map<String, Object>) filteredResult.get("backend_input_contract");
            assertEquals("implicit", lookupContract.get("mode"));
            assertEquals(List.of("query"), lookupContract.get("required"));
            assertEquals(List.of("limit"), lookupContract.get("optional"));

            Map<String, Object> defaulted = invoke(
                    service,
                    "human:analyst|actor_id=analyst",
                    "conformance.lookup",
                    List.of("conformance.read"),
                    Map.of("query", "records"));
            @SuppressWarnings("unchecked")
            Map<String, Object> defaultedResult = (Map<String, Object>) defaulted.get("result");
            @SuppressWarnings("unchecked")
            Map<String, Object> defaultedSemanticInput = (Map<String, Object>) defaultedResult.get("semantic_input");
            assertEquals("records", defaultedSemanticInput.get("query"));
            assertEquals("10", defaultedSemanticInput.get("limit"));
            assertFalse(defaultedSemanticInput.containsKey("debug_trace"));

            Map<String, Object> explicitOmit = invoke(
                    service,
                    "human:analyst|actor_id=analyst",
                    "conformance.lookup",
                    List.of("conformance.read"),
                    Map.of("query", "records", "debug_trace", true));
            @SuppressWarnings("unchecked")
            Map<String, Object> explicitOmitResult = (Map<String, Object>) explicitOmit.get("result");
            @SuppressWarnings("unchecked")
            Map<String, Object> explicitOmitSemanticInput = (Map<String, Object>) explicitOmitResult.get("semantic_input");
            assertEquals(true, explicitOmitSemanticInput.get("debug_trace"));

            Map<String, Object> missing = invoke(
                    service,
                    "human:analyst|actor_id=analyst",
                    "conformance.lookup",
                    List.of("conformance.read"),
                    Map.of());
            assertFailureType(missing, "clarification_required");
            assertResolutionAction(missing, "obtain_binding");

            Map<String, Object> insufficientScope = invoke(
                    service,
                    "human:local-developer",
                    "conformance.prepare_change",
                    List.of("conformance.read"),
                    Map.of("record_ref", "CON-1", "new_status", "done", "change_reason", "conformance test"));
            assertFailureType(insufficientScope, "scope_insufficient");
            assertResolutionAction(insufficientScope, "request_broader_scope");

            Map<String, Object> backendIncomplete = invoke(
                    service,
                    "human:local-developer",
                    "conformance.prepare_change",
                    List.of("conformance.prepare"),
                    Map.of("record_ref", "CON-1", "new_status", "done"));
            assertTrue((Boolean) backendIncomplete.get("success"));
            @SuppressWarnings("unchecked")
            Map<String, Object> backendResult = (Map<String, Object>) backendIncomplete.get("result");
            assertEquals("backend_input_incomplete", backendResult.get("execution_status"));
            @SuppressWarnings("unchecked")
            Map<String, Object> backendContract = (Map<String, Object>) backendResult.get("backend_input_contract");
            assertEquals("hybrid", backendContract.get("mode"));
            assertEquals(List.of("record_ref", "new_status", "change_reason"), backendContract.get("required"));
            assertEquals(List.of(), backendContract.get("optional"));
            assertEquals(List.of("change_reason"), backendResult.get("unresolved_required_backend_inputs"));

            Map<String, Object> openReference = invoke(
                    service,
                    "human:local-developer",
                    "conformance.prepare_change",
                    List.of("conformance.prepare"),
                    Map.of("record_ref", "Arbitrary Customer 42", "new_status", "done", "change_reason", "conformance test"));
            assertTrue((Boolean) openReference.get("success"));
            @SuppressWarnings("unchecked")
            Map<String, Object> openReferenceResult = (Map<String, Object>) openReference.get("result");
            assertEquals("backend_execution_stub", openReferenceResult.get("execution_status"));
            @SuppressWarnings("unchecked")
            Map<String, Object> openReferenceSemanticInput = (Map<String, Object>) openReferenceResult.get("semantic_input");
            assertEquals("Arbitrary Customer 42", openReferenceSemanticInput.get("record_ref"));

            var recordRef = GeneratedCapabilities.createAll(BackendAdapter.defaultAdapter()).stream()
                    .filter(capability -> capability.getDeclaration().getName().equals("conformance.prepare_change"))
                    .findFirst()
                    .orElseThrow()
                    .getDeclaration()
                    .getInputs()
                    .stream()
                    .filter(input -> input.getName().equals("record_ref"))
                    .findFirst()
                    .orElseThrow();
            assertTrue(recordRef.isEntityReference());
            assertEquals("conformance.record_catalog", recordRef.getCatalogRef());
            assertEquals(ResolutionMode.BACKEND_RESOLVED, recordRef.getResolution().mode());
            assertEquals("conformance.record_catalog", recordRef.getResolution().resolverRef());

            var debugTrace = GeneratedCapabilities.createAll(BackendAdapter.defaultAdapter()).stream()
                    .filter(capability -> capability.getDeclaration().getName().equals("conformance.lookup"))
                    .findFirst()
                    .orElseThrow()
                    .getDeclaration()
                    .getInputs()
                    .stream()
                    .filter(input -> input.getName().equals("debug_trace"))
                    .findFirst()
                    .orElseThrow();
            assertEquals(ResolutionMode.EXPLICIT_ONLY, debugTrace.getResolution().mode());
            assertEquals(ResolutionBehavior.OMIT, debugTrace.getResolution().onMissing());

            var newStatus = GeneratedCapabilities.createAll(BackendAdapter.defaultAdapter()).stream()
                    .filter(capability -> capability.getDeclaration().getName().equals("conformance.prepare_change"))
                    .findFirst()
                    .orElseThrow()
                    .getDeclaration()
                    .getInputs()
                    .stream()
                    .filter(input -> input.getName().equals("new_status"))
                    .findFirst()
                    .orElseThrow();
            assertEquals(List.of("todo", "in_progress", "done"), newStatus.getAllowedValues());
            assertEquals("conformance.status_catalog", newStatus.getCatalogRef());
            assertEquals(ResolutionMode.CLOSED_VALUES, newStatus.getResolution().mode());
            assertEquals(ResolutionBehavior.DENY, newStatus.getResolution().onUnresolved());

            Map<String, Object> invalidStatus = invoke(
                    service,
                    "human:local-developer",
                    "conformance.prepare_change",
                    List.of("conformance.prepare"),
                    Map.of("record_ref", "CON-1", "new_status", "archived", "change_reason", "conformance test"));
            assertFailureType(invalidStatus, "denied");
            assertResolutionAction(invalidStatus, "contact_service_owner");

            Map<String, Object> analystDenied = invoke(
                    service,
                    "human:analyst|actor_id=analyst",
                    "conformance.prepare_change",
                    List.of("conformance.prepare"),
                    Map.of("record_ref", "CON-1", "new_status", "done", "change_reason", "conformance test"));
            assertFailureType(analystDenied, "denied");
            assertResolutionAction(analystDenied, "contact_service_owner");

            assertApprovalRequired(invoke(
                    service,
                    "human:manager|actor_id=manager",
                    "conformance.prepare_change",
                    List.of("conformance.prepare"),
                    Map.of("record_ref", "CON-1", "new_status", "done", "change_reason", "conformance test")));

            Map<String, Object> composedSuccess = invoke(
                    service,
                    "human:local-developer",
                    "conformance.lookup_and_prepare",
                    List.of("conformance.read", "conformance.prepare"),
                    Map.of("query", "CON-1", "requested_status", "done", "change_reason", "conformance test"));
            assertTrue((Boolean) composedSuccess.get("success"));
            @SuppressWarnings("unchecked")
            Map<String, Object> composedSuccessResult = (Map<String, Object>) composedSuccess.get("result");
            assertEquals("backend_execution_stub", composedSuccessResult.get("prepared_status"));

            Map<String, Object> composedDenied = invoke(
                    service,
                    "human:local-developer",
                    "conformance.lookup_and_prepare",
                    List.of("conformance.read", "conformance.prepare"),
                    Map.of("query", "CON-1", "requested_status", "archived", "change_reason", "conformance test"));
            assertFailureType(composedDenied, "denied");
            assertResolutionAction(composedDenied, "contact_service_owner");

            assertApprovalRequired(invoke(
                    service,
                    "human:manager|actor_id=manager",
                    "conformance.lookup_and_prepare",
                    List.of("conformance.read", "conformance.prepare"),
                    Map.of("query", "CON-1", "requested_status", "done", "change_reason", "conformance test")));
        } finally {
            service.shutdown();
        }
    }
}
`, "\n")
}

func csharpExecutableBehaviorMatrixTest() string {
	return strings.TrimLeft(`
using Anip.Core;
using Anip.Service;
using Xunit;
using GeneratorConformanceService;

namespace GeneratorConformanceService.Tests;

public class GeneratedBehaviorMatrixTests
{
    private static AnipService NewService()
    {
        var service = new AnipService(new ServiceConfig
        {
            ServiceId = "generator-conformance-service",
            Capabilities = GeneratedCapabilities.CreateAll(BackendAdapter.Default),
            Storage = ":memory:",
            Trust = "signed",
            KeyPath = null,
            RetentionIntervalSeconds = -1,
        });
        service.Start();
        return service;
    }

    private static DelegationToken Issue(AnipService service, string principal, string capability, List<string> scope)
    {
        var response = service.IssueCapabilityToken(principal, capability, scope);
        return service.ResolveBearerToken(response.Token);
    }

    private static Dictionary<string, object?> Invoke(AnipService service, string principal, string capability, List<string> scope, Dictionary<string, object?> parameters)
    {
        return service.Invoke(capability, Issue(service, principal, capability, scope), parameters, new InvokeOpts());
    }

    private static void AssertFailureType(Dictionary<string, object?> payload, string failureType)
    {
        Assert.False((bool)payload["success"]!);
        var failure = Assert.IsType<Dictionary<string, object?>>(payload["failure"]);
        Assert.Equal(failureType, failure["type"]);
    }

    private static void AssertResolutionAction(Dictionary<string, object?> payload, string action)
    {
        var failure = Assert.IsType<Dictionary<string, object?>>(payload["failure"]);
        var resolution = Assert.IsType<Dictionary<string, object?>>(failure["resolution"]);
        Assert.Equal(action, resolution["action"]);
    }

    private static void AssertApprovalRequired(Dictionary<string, object?> payload)
    {
        AssertFailureType(payload, "approval_required");
        var failure = Assert.IsType<Dictionary<string, object?>>(payload["failure"]);
        var resolution = Assert.IsType<Dictionary<string, object?>>(failure["resolution"]);
        Assert.Equal("request_approval", resolution["action"]);
        var approvalRequired = Assert.IsType<Dictionary<string, object?>>(failure["approval_required"]);
        Assert.False(string.IsNullOrWhiteSpace(approvalRequired["approval_request_id"]?.ToString()));
        var grantPolicy = Assert.IsType<Dictionary<string, object?>>(approvalRequired["grant_policy"]);
        Assert.False(string.IsNullOrWhiteSpace(grantPolicy["default_grant_type"]?.ToString()));
    }

    [Fact]
    public void GeneratedBehaviorMatrixMatchesContractPolicy()
    {
        var service = NewService();
        try
        {
            var lookup = Invoke(
                service,
                "human:analyst|actor_id=analyst",
                "conformance.lookup",
                ["conformance.read"],
                new Dictionary<string, object?> { ["query"] = "records" });
            Assert.True((bool)lookup["success"]!);
            var result = Assert.IsType<Dictionary<string, object?>>(lookup["result"]);
            Assert.Equal("backend_execution_stub", result["execution_status"]);

            var filtered = Invoke(
                service,
                "human:analyst|actor_id=analyst",
                "conformance.lookup",
                ["conformance.read"],
                new Dictionary<string, object?>
                {
                    ["query"] = "records",
                    ["limit"] = 3,
                    ["unexpected_extra"] = "leak",
                });
            var filteredResult = Assert.IsType<Dictionary<string, object?>>(filtered["result"]);
            var semanticInput = Assert.IsType<Dictionary<string, object?>>(filteredResult["semantic_input"]);
            Assert.Equal("records", semanticInput["query"]);
            Assert.Equal(3, Convert.ToInt32(semanticInput["limit"]));
            Assert.False(semanticInput.ContainsKey("unexpected_extra"));
            var lookupContract = Assert.IsType<Dictionary<string, object?>>(filteredResult["backend_input_contract"]);
            Assert.Equal("implicit", lookupContract["mode"]);
            Assert.Equal(["query"], Assert.IsType<List<string>>(lookupContract["required"]));
            Assert.Equal(["limit"], Assert.IsType<List<string>>(lookupContract["optional"]));

            var defaulted = Invoke(
                service,
                "human:analyst|actor_id=analyst",
                "conformance.lookup",
                ["conformance.read"],
                new Dictionary<string, object?> { ["query"] = "records" });
            var defaultedResult = Assert.IsType<Dictionary<string, object?>>(defaulted["result"]);
            var defaultedSemanticInput = Assert.IsType<Dictionary<string, object?>>(defaultedResult["semantic_input"]);
            Assert.Equal("records", defaultedSemanticInput["query"]);
            Assert.Equal("10", defaultedSemanticInput["limit"]);
            Assert.False(defaultedSemanticInput.ContainsKey("debug_trace"));

            var explicitOmit = Invoke(
                service,
                "human:analyst|actor_id=analyst",
                "conformance.lookup",
                ["conformance.read"],
                new Dictionary<string, object?>
                {
                    ["query"] = "records",
                    ["debug_trace"] = true,
                });
            var explicitOmitResult = Assert.IsType<Dictionary<string, object?>>(explicitOmit["result"]);
            var explicitOmitSemanticInput = Assert.IsType<Dictionary<string, object?>>(explicitOmitResult["semantic_input"]);
            Assert.Equal(true, explicitOmitSemanticInput["debug_trace"]);

            var missing = Invoke(
                service,
                "human:analyst|actor_id=analyst",
                "conformance.lookup",
                ["conformance.read"],
                []);
            AssertFailureType(missing, "clarification_required");
            AssertResolutionAction(missing, "obtain_binding");

            var insufficientScope = Invoke(
                service,
                "human:local-developer",
                "conformance.prepare_change",
                ["conformance.read"],
                new Dictionary<string, object?>
                {
                    ["record_ref"] = "CON-1",
                    ["new_status"] = "done",
                    ["change_reason"] = "conformance test",
                });
            AssertFailureType(insufficientScope, "scope_insufficient");
            AssertResolutionAction(insufficientScope, "request_broader_scope");

            var backendIncomplete = Invoke(
                service,
                "human:local-developer",
                "conformance.prepare_change",
                ["conformance.prepare"],
                new Dictionary<string, object?>
                {
                    ["record_ref"] = "CON-1",
                    ["new_status"] = "done",
                });
            Assert.True((bool)backendIncomplete["success"]!);
            var backendResult = Assert.IsType<Dictionary<string, object?>>(backendIncomplete["result"]);
            Assert.Equal("backend_input_incomplete", backendResult["execution_status"]);
            var backendContract = Assert.IsType<Dictionary<string, object?>>(backendResult["backend_input_contract"]);
            Assert.Equal("hybrid", backendContract["mode"]);
            Assert.Equal(["record_ref", "new_status", "change_reason"], Assert.IsType<List<string>>(backendContract["required"]));
            Assert.Equal([], Assert.IsType<List<string>>(backendContract["optional"]));
            var unresolved = Assert.IsType<List<string>>(backendResult["unresolved_required_backend_inputs"]);
            Assert.Equal(["change_reason"], unresolved);

            var openReference = Invoke(
                service,
                "human:local-developer",
                "conformance.prepare_change",
                ["conformance.prepare"],
                new Dictionary<string, object?>
                {
                    ["record_ref"] = "Arbitrary Customer 42",
                    ["new_status"] = "done",
                    ["change_reason"] = "conformance test",
                });
            Assert.True((bool)openReference["success"]!);
            var openReferenceResult = Assert.IsType<Dictionary<string, object?>>(openReference["result"]);
            Assert.Equal("backend_execution_stub", openReferenceResult["execution_status"]);
            var openReferenceSemanticInput = Assert.IsType<Dictionary<string, object?>>(openReferenceResult["semantic_input"]);
            Assert.Equal("Arbitrary Customer 42", openReferenceSemanticInput["record_ref"]);

            var recordRef = GeneratedCapabilities.CreateAll(BackendAdapter.Default)
                .Single(capability => capability.Declaration.Name == "conformance.prepare_change")
                .Declaration
                .Inputs
                .Single(input => input.Name == "record_ref");
            Assert.True(recordRef.EntityReference);
            Assert.Equal("conformance.record_catalog", recordRef.CatalogRef);
            Assert.Equal(ResolutionMode.BackendResolved, recordRef.Resolution!.Mode);
            Assert.Equal("conformance.record_catalog", recordRef.Resolution.ResolverRef);

            var debugTrace = GeneratedCapabilities.CreateAll(BackendAdapter.Default)
                .Single(capability => capability.Declaration.Name == "conformance.lookup")
                .Declaration
                .Inputs
                .Single(input => input.Name == "debug_trace");
            Assert.Equal(ResolutionMode.ExplicitOnly, debugTrace.Resolution!.Mode);
            Assert.Equal(ResolutionBehavior.Omit, debugTrace.Resolution.OnMissing);

            var newStatus = GeneratedCapabilities.CreateAll(BackendAdapter.Default)
                .Single(capability => capability.Declaration.Name == "conformance.prepare_change")
                .Declaration
                .Inputs
                .Single(input => input.Name == "new_status");
            Assert.Equal(["todo", "in_progress", "done"], newStatus.AllowedValues);
            Assert.Equal("conformance.status_catalog", newStatus.CatalogRef);
            Assert.Equal(ResolutionMode.ClosedValues, newStatus.Resolution!.Mode);
            Assert.Equal(ResolutionBehavior.Deny, newStatus.Resolution.OnUnresolved);

            var invalidStatus = Invoke(
                service,
                "human:local-developer",
                "conformance.prepare_change",
                ["conformance.prepare"],
                new Dictionary<string, object?>
                {
                    ["record_ref"] = "CON-1",
                    ["new_status"] = "archived",
                    ["change_reason"] = "conformance test",
                });
            AssertFailureType(invalidStatus, "denied");
            AssertResolutionAction(invalidStatus, "contact_service_owner");

            var analystDenied = Invoke(
                service,
                "human:analyst|actor_id=analyst",
                "conformance.prepare_change",
                ["conformance.prepare"],
                new Dictionary<string, object?>
                {
                    ["record_ref"] = "CON-1",
                    ["new_status"] = "done",
                    ["change_reason"] = "conformance test",
                });
            AssertFailureType(analystDenied, "denied");
            AssertResolutionAction(analystDenied, "contact_service_owner");

            AssertApprovalRequired(Invoke(
                service,
                "human:manager|actor_id=manager",
                "conformance.prepare_change",
                ["conformance.prepare"],
                new Dictionary<string, object?>
                {
                    ["record_ref"] = "CON-1",
                    ["new_status"] = "done",
                    ["change_reason"] = "conformance test",
                }));

            var composedSuccess = Invoke(
                service,
                "human:local-developer",
                "conformance.lookup_and_prepare",
                ["conformance.read", "conformance.prepare"],
                new Dictionary<string, object?>
                {
                    ["query"] = "CON-1",
                    ["requested_status"] = "done",
                    ["change_reason"] = "conformance test",
                });
            Assert.True((bool)composedSuccess["success"]!);
            var composedSuccessResult = Assert.IsType<Dictionary<string, object?>>(composedSuccess["result"]);
            Assert.Equal("backend_execution_stub", composedSuccessResult["prepared_status"]);

            var composedDenied = Invoke(
                service,
                "human:local-developer",
                "conformance.lookup_and_prepare",
                ["conformance.read", "conformance.prepare"],
                new Dictionary<string, object?>
                {
                    ["query"] = "CON-1",
                    ["requested_status"] = "archived",
                    ["change_reason"] = "conformance test",
                });
            AssertFailureType(composedDenied, "denied");
            AssertResolutionAction(composedDenied, "contact_service_owner");

            AssertApprovalRequired(Invoke(
                service,
                "human:manager|actor_id=manager",
                "conformance.lookup_and_prepare",
                ["conformance.read", "conformance.prepare"],
                new Dictionary<string, object?>
                {
                    ["query"] = "CON-1",
                    ["requested_status"] = "done",
                    ["change_reason"] = "conformance test",
                }));
        }
        finally
        {
            service.Shutdown();
        }
    }
}
`, "\n")
}
