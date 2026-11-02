package generator

import (
	"go/parser"
	"go/token"
	"reflect"
	"strings"
	"testing"
)

// Exercise the same public protocol against every generated target. Missing
// backend input blocks the stub, but is not an ANIP failure in this contract.
func runGeneratedBackendOnlyStdio(t *testing.T, target, outputDir, repoRoot string) {
	t.Helper()
	client := startGeneratedStdioProcess(t, outputDir, generatedStdioCommandForTarget(t, target, outputDir, repoRoot))
	defer client.close()
	manifest := client.call(t, 1, "anip.manifest", nil)["manifest"].(map[string]any)
	capability := manifest["capabilities"].(map[string]any)["conformance.prepare_change"].(map[string]any)
	var names []string
	for _, raw := range capability["inputs"].([]any) {
		names = append(names, raw.(map[string]any)["name"].(string))
	}
	if !reflect.DeepEqual(names, []string{"record_ref", "new_status"}) {
		t.Fatalf("public child inputs changed or leaked backend-only input: %#v", names)
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
		if payload["success"] != true {
			t.Fatalf("expected successful ANIP envelope: %#v", payload)
		}
		return payload["result"].(map[string]any)
	}
	missing := invoke("conformance.prepare_change", map[string]any{"record_ref": "CON-1", "new_status": "done"})
	if missing["execution_status"] != "backend_input_incomplete" || !reflect.DeepEqual(missing["unresolved_required_backend_inputs"], []any{"change_reason"}) {
		t.Fatalf("missing backend requirement did not block stub: %#v", missing)
	}
	wantContract := map[string]any{"mode": "hybrid", "required": []any{"record_ref", "new_status", "change_reason"}, "optional": []any{}}
	if !reflect.DeepEqual(missing["backend_input_contract"], wantContract) {
		t.Fatalf("backend-only contract changed: %#v", missing)
	}
	valid := invoke("conformance.prepare_change", map[string]any{"record_ref": "CON-1", "new_status": "done", "change_reason": "backend-only-reason", "unrelated_sentinel": "must-not-reach-adapter"})
	if valid["execution_status"] != "backend_execution_stub" || !reflect.DeepEqual(valid["semantic_input"], map[string]any{"record_ref": "CON-1", "new_status": "done"}) || !reflect.DeepEqual(valid["backend_input_contract"], wantContract) {
		t.Fatalf("valid backend-only request changed semantic input or contract: %#v", valid)
	}
	parent := invoke("conformance.lookup_and_prepare", map[string]any{"query": "CON-1", "requested_status": "done", "change_reason": "not-mapped-to-child"})
	if parent["prepared_status"] != "backend_input_incomplete" {
		t.Fatalf("parent supplied an unmapped backend-only input: %#v", parent)
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
    payload = _invoke(_client(), "dev-admin-key", "conformance.prepare_change", ["conformance.prepare"],
                      {"record_ref": "CON-1", "new_status": "done", "change_reason": "backend-only-reason", "unrelated_sentinel": "must-not-reach-adapter"})
    assert payload["success"] is True
    assert payload["result"]["execution_status"] == "backend_execution_stub"
    assert captured == [({"record_ref": "CON-1", "new_status": "done", "change_reason": "backend-only-reason"},
                         {"record_ref": "CON-1", "new_status": "done"})]
`
	case "typescript":
		return prefix + `import { vi } from "vitest";
import { backendAdapter } from "../src/runtime/backend-adapter.js";

it("preserves backend-only adapter input without semantic or unrelated keys", async () => {
  const original = backendAdapter.execute.bind(backendAdapter);
  const captured: unknown[] = [];
  const spy = vi.spyOn(backendAdapter, "execute").mockImplementation(async (capability, plan, adapterInput, context) => {
    captured.push([{ ...adapterInput }, { ...plan.semantic_input }]);
    return original(capability, plan, adapterInput, context);
  });
  try {
    const payload = await invoke("dev-admin-key", "conformance.prepare_change", ["conformance.prepare"],
      { record_ref: "CON-1", new_status: "done", change_reason: "backend-only-reason", unrelated_sentinel: "must-not-reach-adapter" });
    expect(payload.success).toBe(true);
    expect(payload.result?.execution_status).toBe("backend_execution_stub");
    expect(captured).toEqual([[{ record_ref: "CON-1", new_status: "done", change_reason: "backend-only-reason" },
      { record_ref: "CON-1", new_status: "done" }]]);
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
    payload := invokeBehaviorMatrixCapability(t, ts, "dev-admin-key", "conformance.prepare_change", []string{"conformance.prepare"},
        map[string]any{"record_ref": "CON-1", "new_status": "done", "change_reason": "backend-only-reason", "unrelated_sentinel": "must-not-reach-adapter"})
    if payload["success"] != true || payload["result"].(map[string]any)["execution_status"] != "backend_execution_stub" { t.Fatal(payload) }
    select {
    case got := <-captured:
        want := [2]map[string]any{{"record_ref": "CON-1", "new_status": "done", "change_reason": "backend-only-reason"}, {"record_ref": "CON-1", "new_status": "done"}}
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
            var payload = invoke(service, "human:local-developer", "conformance.prepare_change", List.of("conformance.prepare"),
                    Map.of("record_ref", "CON-1", "new_status", "done", "change_reason", "backend-only-reason", "unrelated_sentinel", "must-not-reach-adapter"));
            assertEquals(true, payload.get("success"));
            assertEquals("backend_execution_stub", ((Map<?, ?>) payload.get("result")).get("execution_status"));
            assertEquals(List.of(List.of(Map.of("record_ref", "CON-1", "new_status", "done", "change_reason", "backend-only-reason"),
                    Map.of("record_ref", "CON-1", "new_status", "done"))), captured);
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
            var payload = Invoke(service, "human:local-developer", "conformance.prepare_change", ["conformance.prepare"],
                new() { ["record_ref"] = "CON-1", ["new_status"] = "done", ["change_reason"] = "backend-only-reason", ["unrelated_sentinel"] = "must-not-reach-adapter" });
            Assert.True((bool)payload["success"]!);
            Assert.Equal("backend_execution_stub", Assert.IsType<Dictionary<string, object?>>(payload["result"])["execution_status"]);
            var call = Assert.Single(captured);
            Assert.Equal(3, call.Adapter.Count);
            Assert.Equal("CON-1", call.Adapter["record_ref"]);
            Assert.Equal("done", call.Adapter["new_status"]);
            Assert.Equal("backend-only-reason", call.Adapter["change_reason"]);
            Assert.Equal(2, call.Semantic.Count);
            Assert.Equal("CON-1", call.Semantic["record_ref"]);
            Assert.Equal("done", call.Semantic["new_status"]);
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
			for _, required := range []string{"backend-only-reason", "unrelated_sentinel", "backend_execution_stub"} {
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
