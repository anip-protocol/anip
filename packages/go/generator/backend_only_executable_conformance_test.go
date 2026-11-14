package generator

import (
	"go/parser"
	"go/token"
	"reflect"
	"strings"
	"testing"
)

// Exercise the same public protocol against every generated target over
// stdio. The child declares the explicit backend input change_reason that the
// definition left out of its inputs, so a call without it, or with a key the
// capability does not declare, is refused before the adapter runs. The parent
// does not declare change_reason and supplies the child's from an earlier
// step, so parent parameters reach the child only through input_mapping.
func runGeneratedBackendOnlyStdio(t *testing.T, target, outputDir, repoRoot string) {
	t.Helper()
	client := startGeneratedStdioProcess(t, outputDir, generatedStdioCommandForTarget(t, target, outputDir, repoRoot))
	defer client.close()
	manifest := client.call(t, 1, "anip.manifest", nil)["manifest"].(map[string]any)
	declaredInputs := func(capabilityID string) []string {
		t.Helper()
		capability := manifest["capabilities"].(map[string]any)[capabilityID].(map[string]any)
		var names []string
		for _, raw := range capability["inputs"].([]any) {
			input := raw.(map[string]any)
			name := input["name"].(string)
			if input["required"] == false {
				name += "?"
			}
			names = append(names, name)
		}
		return names
	}
	if got := declaredInputs("conformance.prepare_change"); !reflect.DeepEqual(got, []string{"record_ref", "new_status", "change_reason"}) {
		t.Fatalf("child must declare its explicit backend input as required: %#v", got)
	}
	if got := declaredInputs("conformance.lookup_and_prepare"); !reflect.DeepEqual(got, []string{"query", "requested_status"}) {
		t.Fatalf("parent must not declare change_reason: %#v", got)
	}
	nextID := 2
	invoke := func(capability string, parameters map[string]any) map[string]any {
		t.Helper()
		issued := client.call(t, nextID, "anip.tokens.issue", map[string]any{
			"auth":    map[string]any{"bearer": "dev-admin-key"},
			"subject": "human:local-developer", "scope": []string{"conformance.prepare", "conformance.read"}, "capability": capability,
		})
		token, ok := issued["token"].(string)
		if !ok || token == "" {
			t.Fatal("missing invocation token")
		}
		nextID++
		payload := client.call(t, nextID, "anip.invoke", map[string]any{
			"auth": map[string]any{"bearer": token}, "capability": capability, "parameters": parameters,
		})
		nextID++
		return payload
	}
	refused := func(payload map[string]any, name string) {
		t.Helper()
		failure, _ := payload["failure"].(map[string]any)
		detail, _ := failure["detail"].(string)
		if payload["success"] != false || failure["type"] != "invalid_parameters" || !strings.Contains(detail, name) {
			t.Fatalf("expected invalid_parameters naming %s: %#v", name, payload)
		}
	}
	succeeded := func(payload map[string]any) map[string]any {
		t.Helper()
		result, ok := payload["result"].(map[string]any)
		if payload["success"] != true || !ok {
			t.Fatalf("expected a successful ANIP envelope: %#v", payload)
		}
		return result
	}
	refused(invoke("conformance.prepare_change", map[string]any{"record_ref": "CON-1", "new_status": "done"}), "change_reason")
	refused(invoke("conformance.prepare_change", map[string]any{"record_ref": "CON-1", "new_status": "done", "change_reason": "backend-reason", "unrelated_sentinel": "must-not-reach-adapter"}), "unrelated_sentinel")
	valid := succeeded(invoke("conformance.prepare_change", map[string]any{"record_ref": "CON-1", "new_status": "done", "change_reason": "backend-reason"}))
	wantContract := map[string]any{"mode": "hybrid", "required": []any{"record_ref", "new_status", "change_reason"}, "optional": []any{}}
	wantInput := map[string]any{"record_ref": "CON-1", "new_status": "done", "change_reason": "backend-reason"}
	if valid["execution_status"] != "backend_execution_stub" || !reflect.DeepEqual(valid["semantic_input"], wantInput) || !reflect.DeepEqual(valid["backend_input_contract"], wantContract) {
		t.Fatalf("valid request changed semantic input or contract: %#v", valid)
	}
	refused(invoke("conformance.lookup_and_prepare", map[string]any{"query": "CON-1", "requested_status": "done", "change_reason": "not-mapped-to-child"}), "change_reason")
	parent := succeeded(invoke("conformance.lookup_and_prepare", map[string]any{"query": "CON-1", "requested_status": "done"}))
	if parent["prepared_status"] != "backend_execution_stub" {
		t.Fatalf("parent did not supply the child's change_reason from the lookup step: %#v", parent)
	}
}

// Reuse the existing language-specific invocation helpers, not a new runtime
// harness. Fail closed if a template no longer has its explicit test boundary.
func backendOnlyAdapterTest(t *testing.T, target, matrix string) string {
	t.Helper()
	markers := map[string]string{
		"python": "def test_behavior_matrix_lookup_success", "typescript": "describe(\"generated behavior matrix\"",
		"go": "func TestGeneratedBehaviorMatrix", "java": "    @Test\n", "csharp": "    [Fact]\n",
	}
	prefix, _, ok := strings.Cut(matrix, markers[target])
	if markers[target] == "" || !ok {
		t.Fatalf("missing %s behavior-matrix helper boundary", target)
	}
	switch target {
	case "python":
		return prefix + `def test_backend_only_adapter_input(monkeypatch) -> None:
    module = importlib.import_module("generator_conformance_service.capabilities")
    original = module.backend_adapter
    captured = []

    class Spy:
        async def execute(self, capability, plan, adapter_input, context):
            captured.append((dict(adapter_input), dict(plan["semantic_input"])))
            return await original.execute(capability, plan, adapter_input, context)

    monkeypatch.setattr(module, "backend_adapter", Spy())
    refused = _invoke(_client(), "dev-admin-key", "conformance.prepare_change", ["conformance.prepare"],
                      {"record_ref": "CON-1", "new_status": "done", "change_reason": "backend-reason", "unrelated_sentinel": "must-not-reach-adapter"})
    _assert_failure_type(refused, "invalid_parameters")
    assert "unrelated_sentinel" in refused["failure"]["detail"]
    payload = _invoke(_client(), "dev-admin-key", "conformance.prepare_change", ["conformance.prepare"],
                      {"record_ref": "CON-1", "new_status": "done", "change_reason": "backend-reason"})
    assert payload["success"] is True
    assert payload["result"]["execution_status"] == "backend_execution_stub"
    declared = {"record_ref": "CON-1", "new_status": "done", "change_reason": "backend-reason"}
    assert captured == [(declared, declared)]
`
	case "typescript":
		return prefix + `import { vi } from "vitest";
import { backendAdapter } from "../src/runtime/backend-adapter.js";

it("passes the declared backend input to the adapter and refuses undeclared keys", async () => {
  const original = backendAdapter.execute.bind(backendAdapter);
  const captured: unknown[] = [];
  const spy = vi.spyOn(backendAdapter, "execute").mockImplementation(async (capability, plan, adapterInput, context) => {
    captured.push([{ ...adapterInput }, { ...plan.semantic_input }]);
    return original(capability, plan, adapterInput, context);
  });
  try {
    const refused = await invoke("dev-admin-key", "conformance.prepare_change", ["conformance.prepare"],
      { record_ref: "CON-1", new_status: "done", change_reason: "backend-reason", unrelated_sentinel: "must-not-reach-adapter" });
    expectFailureType(refused, "invalid_parameters");
    expect((refused as any).failure?.detail).toContain("unrelated_sentinel");
    const payload = await invoke("dev-admin-key", "conformance.prepare_change", ["conformance.prepare"],
      { record_ref: "CON-1", new_status: "done", change_reason: "backend-reason" });
    expect(payload.success).toBe(true);
    expect(payload.result?.execution_status).toBe("backend_execution_stub");
    const declared = { record_ref: "CON-1", new_status: "done", change_reason: "backend-reason" };
    expect(captured).toEqual([[declared, declared]]);
  } finally {
    spy.mockRestore();
  }
});
`
	case "go":
		prefix = strings.Replace(prefix, `generatedhost "generated/generator-conformance-service/host"`, `"reflect"
    "fmt"
    "generated/generator-conformance-service/generated"
    "generated/generator-conformance-service/extensions"`, 1)
		return prefix + `type backendOnlySpy struct {
    original extensions.BackendAdapter
    captured chan [2]map[string]any
}

func (spy backendOnlySpy) Execute(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, input map[string]any, context extensions.BackendInvocationContext) (map[string]any, error) {
    copyMap := func(src map[string]any) map[string]any {
        out := map[string]any{}
        for k, v := range src { out[k] = v }
        return out
    }
    select {
    case spy.captured <- [2]map[string]any{copyMap(input), copyMap(plan.SemanticInput)}:
    default:
        return nil, fmt.Errorf("adapter invoked more than once")
    }
    return spy.original.Execute(capability, plan, input, context)
}

func TestBackendOnlyAdapterInput(t *testing.T) {
    original := extensions.BackendAdapterInstance
    captured := make(chan [2]map[string]any, 1)
    extensions.BackendAdapterInstance = backendOnlySpy{original, captured}
    defer func() { extensions.BackendAdapterInstance = original }()
    svc, err := NewService()
    if err != nil { t.Fatal(err) }
    defer svc.Shutdown()
    ts := httptest.NewServer(NewMux(svc))
    defer ts.Close()
    refused := invokeBehaviorMatrixCapability(t, ts, "dev-admin-key", "conformance.prepare_change", []string{"conformance.prepare"},
        map[string]any{"record_ref": "CON-1", "new_status": "done", "change_reason": "backend-reason", "unrelated_sentinel": "must-not-reach-adapter"})
    assertBehaviorMatrixFailureType(t, refused, "invalid_parameters")
    if detail, _ := refused["failure"].(map[string]any)["detail"].(string); !bytes.Contains([]byte(detail), []byte("unrelated_sentinel")) { t.Fatal(refused) }
    payload := invokeBehaviorMatrixCapability(t, ts, "dev-admin-key", "conformance.prepare_change", []string{"conformance.prepare"},
        map[string]any{"record_ref": "CON-1", "new_status": "done", "change_reason": "backend-reason"})
    if payload["success"] != true || payload["result"].(map[string]any)["execution_status"] != "backend_execution_stub" { t.Fatal(payload) }
    select {
    case got := <-captured:
        declared := map[string]any{"record_ref": "CON-1", "new_status": "done", "change_reason": "backend-reason"}
        want := [2]map[string]any{declared, declared}
        if !reflect.DeepEqual(got, want) { t.Fatalf("adapter/semantic inputs: %#v", got) }
    default:
        t.Fatal("adapter was not invoked")
    }
}
`
	case "java":
		return prefix + `    @Test
    void backendOnlyAdapterInput() throws Exception {
        var captured = new java.util.ArrayList<List<Map<String, Object>>>();
        BackendAdapter original = BackendAdapter.defaultAdapter();
        BackendAdapter spy = (capability, plan, input, context) -> {
            @SuppressWarnings("unchecked")
            var semantic = (Map<String, Object>) plan.get("semantic_input");
            captured.add(List.of(new java.util.LinkedHashMap<>(input), new java.util.LinkedHashMap<>(semantic)));
            return original.execute(capability, plan, input, context);
        };
        ANIPService service = new ANIPService(new ServiceConfig()
                .setServiceId("generator-conformance-service")
                .setCapabilities(GeneratedCapabilities.createAll(spy))
                .setStorage(":memory:").setTrust("signed").setKeyPath(null));
        service.start();
        try {
            var refused = invoke(service, "human:local-developer", "conformance.prepare_change", List.of("conformance.prepare"),
                    Map.of("record_ref", "CON-1", "new_status", "done", "change_reason", "backend-reason", "unrelated_sentinel", "must-not-reach-adapter"));
            assertFailureType(refused, "invalid_parameters");
            assertTrue(String.valueOf(((Map<?, ?>) refused.get("failure")).get("detail")).contains("unrelated_sentinel"));
            var payload = invoke(service, "human:local-developer", "conformance.prepare_change", List.of("conformance.prepare"),
                    Map.of("record_ref", "CON-1", "new_status", "done", "change_reason", "backend-reason"));
            assertEquals(true, payload.get("success"));
            assertEquals("backend_execution_stub", ((Map<?, ?>) payload.get("result")).get("execution_status"));
            var declared = Map.of("record_ref", "CON-1", "new_status", "done", "change_reason", "backend-reason");
            assertEquals(List.of(List.of(declared, declared)), captured);
        } finally { service.shutdown(); }
    }
}
`
	case "csharp":
		return prefix + `    [Fact]
    public void BackendOnlyAdapterInput()
    {
        var captured = new List<(Dictionary<string, object?> Adapter, Dictionary<string, object?> Semantic)>();
        var original = BackendAdapter.Default;
        BackendAdapterHandler spy = (capability, plan, input, context) => {
            captured.Add((new(input), new((Dictionary<string, object?>)plan["semantic_input"]!)));
            return original(capability, plan, input, context);
        };
        var service = new AnipService(new ServiceConfig {
            ServiceId = "generator-conformance-service", Capabilities = GeneratedCapabilities.CreateAll(spy),
            Storage = ":memory:", Trust = "signed", KeyPath = null, RetentionIntervalSeconds = -1,
        });
        service.Start();
        try {
            var refused = Invoke(service, "human:local-developer", "conformance.prepare_change", ["conformance.prepare"],
                new() { ["record_ref"] = "CON-1", ["new_status"] = "done", ["change_reason"] = "backend-reason", ["unrelated_sentinel"] = "must-not-reach-adapter" });
            AssertFailureType(refused, "invalid_parameters");
            Assert.Contains("unrelated_sentinel", (string)Assert.IsType<Dictionary<string, object?>>(refused["failure"])["detail"]!);
            var payload = Invoke(service, "human:local-developer", "conformance.prepare_change", ["conformance.prepare"],
                new() { ["record_ref"] = "CON-1", ["new_status"] = "done", ["change_reason"] = "backend-reason" });
            Assert.True((bool)payload["success"]!);
            Assert.Equal("backend_execution_stub", Assert.IsType<Dictionary<string, object?>>(payload["result"])["execution_status"]);
            var call = Assert.Single(captured);
            foreach (var input in new[] { call.Adapter, call.Semantic })
            {
                Assert.Equal(3, input.Count);
                Assert.Equal("CON-1", input["record_ref"]);
                Assert.Equal("done", input["new_status"]);
                Assert.Equal("backend-reason", input["change_reason"]);
            }
        } finally { service.Shutdown(); }
    }
}
`
	default:
		t.Fatalf("unknown target %s", target)
		return ""
	}
}

func TestBackendOnlyExecutableTemplates(t *testing.T) {
	for target, matrix := range map[string]string{
		"python": pythonExecutableBehaviorMatrixTest(), "typescript": typeScriptExecutableBehaviorMatrixTest(),
		"go": goExecutableBehaviorMatrixTest(), "java": javaExecutableBehaviorMatrixTest(), "csharp": csharpExecutableBehaviorMatrixTest(),
	} {
		t.Run(target, func(t *testing.T) {
			content := backendOnlyAdapterTest(t, target, matrix)
			for _, required := range []string{"backend-reason", "unrelated_sentinel", "invalid_parameters", "backend_execution_stub"} {
				if !strings.Contains(content, required) {
					t.Fatalf("missing %s", required)
				}
			}
			if target == "go" {
				if _, err := parser.ParseFile(token.NewFileSet(), "generated_test.go", content, parser.AllErrors); err != nil {
					t.Fatal(err)
				}
			}
		})
	}
}
