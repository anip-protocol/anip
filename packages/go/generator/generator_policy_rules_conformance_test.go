package generator

import (
	"go/parser"
	"go/token"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// The policy rules every generated target enforces, exercised against the
// conformance fixture (see its runtime_policy_bindings):
//
//  1. A matching deny binding refuses, whatever the capability posture.
//     A binding whose decision the host does not recognise refuses too.
//  2. When a capability has bindings and none matches the actor, the request
//     is refused. A principal without actor claims matches none.
//  3. A capability without bindings is allowed.
//  4. An approval-gated capability stops before the backend adapter runs,
//     unless the runtime validated an approval grant for this invocation.
//
// Each target gets the same scenarios in its own test framework, so a target
// that drifts fails on its own toolchain.
func writeExecutablePolicyRulesTest(t *testing.T, targetName string, outputDir string) {
	t.Helper()
	var path, content string
	switch targetName {
	case "python":
		path = filepath.Join(outputDir, "tests", "test_generator_policy_rules.py")
		content = pythonExecutablePolicyRulesTest()
	case "typescript":
		path = filepath.Join(outputDir, "tests", "generator-policy-rules.test.ts")
		content = typeScriptExecutablePolicyRulesTest()
	case "go":
		path = filepath.Join(outputDir, "app", "generator_policy_rules_test.go")
		content = goExecutablePolicyRulesTest()
	case "java":
		path = filepath.Join(outputDir, "src", "test", "java", "dev", "anip", "generated", "generator_conformance_service", "GeneratedPolicyRulesTest.java")
		content = javaExecutablePolicyRulesTest()
	case "csharp":
		path = filepath.Join(outputDir, "tests", "GeneratedPolicyRulesTests.cs")
		content = csharpExecutablePolicyRulesTest()
	default:
		t.Fatalf("unsupported executable policy rules target %q", targetName)
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatalf("create policy rules test directory for %s: %v", targetName, err)
	}
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatalf("write policy rules test for %s: %v", targetName, err)
	}
}

// runGeneratedStdioPolicyRefusal shows a policy refusal over stdio carries the
// same type, detail and resolution as over HTTP.
func runGeneratedStdioPolicyRefusal(t *testing.T, targetName string, outputDir string, repoRoot string) {
	t.Helper()
	client := startGeneratedStdioProcess(t, outputDir, generatedStdioCommandForTarget(t, targetName, outputDir, repoRoot))
	defer client.close()
	nextID := 1
	subjects := map[string]string{
		"dev-admin-key":  "human:local-developer",
		"visitor-key":    "human:visitor|actor_id=visitor",
		"contractor-key": "human:contractor|actor_id=contractor",
		"intern-key":     "human:intern|actor_id=intern",
	}
	invoke := func(key, capability string, scope []string, parameters map[string]any) map[string]any {
		t.Helper()
		issued := client.call(t, nextID, "anip.tokens.issue", map[string]any{
			"auth": map[string]any{"bearer": key}, "subject": subjects[key], "scope": scope, "capability": capability,
		})
		nextID++
		token, ok := issued["token"].(string)
		if !ok || token == "" {
			t.Fatalf("%s stdio token issue did not return token: %#v", targetName, issued)
		}
		payload := client.call(t, nextID, "anip.invoke", map[string]any{
			"auth": map[string]any{"bearer": token}, "capability": capability, "parameters": parameters,
		})
		nextID++
		return payload
	}
	refused := func(payload map[string]any, failureType, action, detail string) {
		t.Helper()
		failure, _ := payload["failure"].(map[string]any)
		resolution, _ := failure["resolution"].(map[string]any)
		if payload["success"] != false || failure["type"] != failureType || resolution["action"] != action {
			t.Fatalf("%s stdio: expected %s/%s, got %#v", targetName, failureType, action, payload)
		}
		if detail != "" && failure["detail"] != detail {
			t.Fatalf("%s stdio: expected detail %q, got %#v", targetName, detail, failure["detail"])
		}
	}
	lookup := map[string]any{"query": "records"}
	refused(invoke("dev-admin-key", "conformance.lookup", []string{"conformance.read"}, lookup), "denied", "contact_service_owner", generatedPolicyNoMatchDetail)
	refused(invoke("visitor-key", "conformance.lookup", []string{"conformance.read"}, lookup), "denied", "contact_service_owner", generatedPolicyNoMatchDetail)
	refused(invoke("contractor-key", "conformance.lookup", []string{"conformance.read"}, lookup), "denied", "contact_service_owner", "Contractors cannot read records.")
	refused(invoke("intern-key", "conformance.lookup", []string{"conformance.read"}, lookup), "clarification_required", "obtain_binding", "Interns must say which team they read for.")
	approval := invoke("contractor-key", "conformance.prepare_change", []string{"conformance.prepare"}, map[string]any{"record_ref": "CON-1", "new_status": "done", "change_reason": "policy rules"})
	refused(approval, "approval_required", "request_approval", "")
	if request, _ := approval["failure"].(map[string]any)["approval_required"].(map[string]any); request == nil || request["approval_request_id"] == nil || request["approval_request_id"] == "" {
		t.Fatalf("%s stdio: approval_required without an approval request: %#v", targetName, approval)
	}
}

func TestPolicyRulesExecutableTemplates(t *testing.T) {
	for target, content := range map[string]string{
		"python": pythonExecutablePolicyRulesTest(), "typescript": typeScriptExecutablePolicyRulesTest(),
		"go": goExecutablePolicyRulesTest(), "java": javaExecutablePolicyRulesTest(), "csharp": csharpExecutablePolicyRulesTest(),
	} {
		t.Run(target, func(t *testing.T) {
			for _, required := range []string{generatedPolicyNoMatchDetail, "contractor", "intern", "visitor", "auditor", "conformance.unbound", "executed_by_test", "approver"} {
				if !strings.Contains(content, required) {
					t.Fatalf("%s policy rules test is missing %q", target, required)
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

func pythonExecutablePolicyRulesTest() string {
	return strings.ReplaceAll(strings.TrimLeft(`
import asyncio
import importlib

from fastapi.testclient import TestClient


PRINCIPALS = {
    "dev-admin-key": "human:local-developer",
    "analyst-key": "human:analyst|actor_id=analyst",
    "manager-key": "human:manager|actor_id=manager",
    "contractor-key": "human:contractor|actor_id=contractor",
    "intern-key": "human:intern|actor_id=intern",
    "visitor-key": "human:visitor|actor_id=visitor",
    "auditor-key": "human:auditor|actor_id=auditor",
    "approver-key": "human:approver",
}
NO_MATCH = "__NO_MATCH__"
CHANGE = {"record_ref": "CON-1", "new_status": "done", "change_reason": "policy rules"}


def _client() -> TestClient:
    module = importlib.import_module("generator_conformance_service.app")
    original = module._authenticate
    module._authenticate = lambda bearer: PRINCIPALS.get(bearer)
    try:
        return TestClient(module.create_app())
    finally:
        module._authenticate = original


def _token(client: TestClient, key: str, capability_id: str, scope: list[str]) -> str:
    response = client.post(
        "/anip/tokens",
        headers={"Authorization": f"Bearer {key}"},
        json={"capability": capability_id, "scope": scope, "subject": PRINCIPALS[key]},
    )
    assert response.status_code == 200, response.text
    return response.json()["token"]


def _invoke(client: TestClient, key: str, capability_id: str, scope: list[str], parameters: dict, approval_grant: str | None = None) -> dict:
    body: dict = {"parameters": parameters}
    if approval_grant is not None:
        body["approval_grant"] = approval_grant
    response = client.post(
        f"/anip/invoke/{capability_id}",
        headers={"Authorization": f"Bearer {_token(client, key, capability_id, scope)}"},
        json=body,
    )
    return response.json()


def _approve(client: TestClient, payload: dict) -> str:
    request_id = payload["failure"]["approval_required"]["approval_request_id"]
    token = _token(client, "approver-key", "conformance.prepare_change", ["conformance.prepare", "approver:*"])
    response = client.post(
        "/anip/approval_grants",
        headers={"Authorization": f"Bearer {token}"},
        json={"approval_request_id": request_id, "grant_type": "one_time"},
    )
    assert response.status_code == 200, response.text
    return response.json()["grant_id"]


def _assert_refused(payload: dict, failure_type: str, action: str, detail: str | None = None) -> None:
    assert payload["success"] is False, payload
    assert payload["failure"]["type"] == failure_type, payload
    assert payload["failure"]["resolution"]["action"] == action, payload
    if detail is not None:
        assert payload["failure"]["detail"] == detail, payload


def _assert_approval_required(payload: dict) -> None:
    _assert_refused(payload, "approval_required", "request_approval")
    assert payload["failure"]["approval_required"]["approval_request_id"], payload


def _record_adapter_calls(monkeypatch) -> list[str]:
    module = importlib.import_module("generator_conformance_service.capabilities")
    calls: list[str] = []

    class Recording:
        async def execute(self, capability, plan, adapter_input, context):
            calls.append(capability["capability_id"])
            return {"execution_status": "executed_by_test"}

    monkeypatch.setattr(module, "backend_adapter", Recording())
    return calls


def _evaluate(capability_id: str, principal: str) -> dict:
    module = importlib.import_module("generator_conformance_service.policy")
    return asyncio.run(module.evaluate_policy({"capability": {"capability_id": capability_id}, "params": {}, "root_principal": principal}))


def test_rule1_matching_deny_refuses_a_read_capability() -> None:
    payload = _invoke(_client(), "contractor-key", "conformance.lookup", ["conformance.read"], {"query": "records"})
    _assert_refused(payload, "denied", "contact_service_owner", "Contractors cannot read records.")


def test_rule1_matching_deny_refuses_a_governed_capability() -> None:
    payload = _invoke(_client(), "analyst-key", "conformance.prepare_change", ["conformance.prepare"], CHANGE)
    _assert_refused(payload, "denied", "contact_service_owner", "Analysts cannot prepare changes.")


def test_rule1_child_deny_applies_at_a_composition_step() -> None:
    # The deny binding names only the child; the composition reaches it as a step.
    payload = _invoke(_client(), "analyst-key", "conformance.lookup_and_prepare", ["conformance.read", "conformance.prepare"],
                      {"query": "CON-1", "requested_status": "done", "change_reason": "policy rules"})
    _assert_refused(payload, "denied", "contact_service_owner", "Analysts cannot prepare changes.")


def test_rule1_unrecognised_decision_refuses() -> None:
    payload = _invoke(_client(), "auditor-key", "conformance.lookup", ["conformance.read"], {"query": "records"})
    _assert_refused(payload, "denied", "contact_service_owner")


def test_clarify_binding_applies_to_a_read_capability() -> None:
    payload = _invoke(_client(), "intern-key", "conformance.lookup", ["conformance.read"], {"query": "records"})
    _assert_refused(payload, "clarification_required", "obtain_binding", "Interns must say which team they read for.")


def test_rule2_actor_matching_no_binding_is_refused() -> None:
    payload = _invoke(_client(), "visitor-key", "conformance.lookup", ["conformance.read"], {"query": "records"})
    _assert_refused(payload, "denied", "contact_service_owner", NO_MATCH)


def test_rule2_principal_without_actor_claims_is_refused() -> None:
    payload = _invoke(_client(), "dev-admin-key", "conformance.lookup", ["conformance.read"], {"query": "records"})
    _assert_refused(payload, "denied", "contact_service_owner", NO_MATCH)
    assert _evaluate("conformance.lookup", "")["decision"] == "deny"


def test_rule2_composition_children_are_checked() -> None:
    payload = _invoke(_client(), "dev-admin-key", "conformance.lookup_and_prepare", ["conformance.read", "conformance.prepare"],
                      {"query": "CON-1", "requested_status": "done", "change_reason": "policy rules"})
    assert payload["success"] is False, payload
    assert payload["failure"]["type"] == "denied", payload


def test_rule3_capability_without_bindings_is_allowed() -> None:
    for principal in ("human:visitor|actor_id=visitor", "human:local-developer", ""):
        assert _evaluate("conformance.unbound", principal)["decision"] == "allow", principal


def test_rule4_allowed_actor_stops_before_the_adapter(monkeypatch) -> None:
    calls = _record_adapter_calls(monkeypatch)
    payload = _invoke(_client(), "contractor-key", "conformance.prepare_change", ["conformance.prepare"], CHANGE)
    _assert_approval_required(payload)
    assert calls == []


def test_rule4_validated_grant_reaches_the_adapter(monkeypatch) -> None:
    calls = _record_adapter_calls(monkeypatch)
    client = _client()
    first = _invoke(client, "contractor-key", "conformance.prepare_change", ["conformance.prepare"], CHANGE)
    _assert_approval_required(first)
    grant = _approve(client, first)
    second = _invoke(client, "contractor-key", "conformance.prepare_change", ["conformance.prepare"], CHANGE, approval_grant=grant)
    assert second["success"] is True, second
    assert second["result"]["execution_status"] == "executed_by_test"
    assert calls == ["conformance.prepare_change"]


def test_rule4_grant_satisfies_an_approval_binding(monkeypatch) -> None:
    calls = _record_adapter_calls(monkeypatch)
    client = _client()
    first = _invoke(client, "manager-key", "conformance.prepare_change", ["conformance.prepare"], CHANGE)
    _assert_approval_required(first)
    assert calls == []
    second = _invoke(client, "manager-key", "conformance.prepare_change", ["conformance.prepare"], CHANGE, approval_grant=_approve(client, first))
    assert second["success"] is True, second
    assert calls == ["conformance.prepare_change"]


def test_rule4_composition_stops_at_an_approval_gated_child() -> None:
    payload = _invoke(_client(), "manager-key", "conformance.lookup_and_prepare", ["conformance.read", "conformance.prepare"],
                      {"query": "CON-1", "requested_status": "done", "change_reason": "policy rules"})
    _assert_approval_required(payload)
`, "\n"), "__NO_MATCH__", generatedPolicyNoMatchDetail)
}

func typeScriptExecutablePolicyRulesTest() string {
	return strings.ReplaceAll(strings.TrimLeft(`
import { afterEach, describe, expect, it, vi } from "vitest";
import { app } from "../src/app.js";
import { backendAdapter } from "../src/runtime/backend-adapter.js";
import { evaluatePolicy } from "../src/runtime/policy.js";

const NO_MATCH = "__NO_MATCH__";
const CHANGE = { record_ref: "CON-1", new_status: "done", change_reason: "policy rules" };
type Payload = {
  success: boolean;
  result?: Record<string, unknown>;
  failure?: { type?: string; detail?: string; resolution?: { action?: string }; approval_required?: { approval_request_id?: string } };
};

async function post(path: string, bearer: string, body: unknown) {
  return app.request(path, {
    method: "POST",
    headers: { authorization: "Bearer " + bearer, "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

async function token(key: string, capability: string, scope: string[]) {
  const response = await post("/anip/tokens", key, { capability, scope, subject: key });
  expect(response.status).toBe(200);
  return ((await response.json()) as { token: string }).token;
}

async function invoke(key: string, capability: string, scope: string[], parameters: Record<string, unknown>, approvalGrant?: string): Promise<Payload> {
  const body: Record<string, unknown> = { parameters };
  if (approvalGrant !== undefined) body.approval_grant = approvalGrant;
  const response = await post("/anip/invoke/" + capability, await token(key, capability, scope), body);
  return (await response.json()) as Payload;
}

async function approve(payload: Payload) {
  const approver = await token("approver-key", "conformance.prepare_change", ["conformance.prepare", "approver:*"]);
  const response = await post("/anip/approval_grants", approver, {
    approval_request_id: payload.failure?.approval_required?.approval_request_id,
    grant_type: "one_time",
  });
  expect(response.status).toBe(200);
  return ((await response.json()) as { grant_id: string }).grant_id;
}

function expectRefused(payload: Payload, type: string, action: string, detail?: string) {
  expect(payload.success).toBe(false);
  expect(payload.failure?.type).toBe(type);
  expect(payload.failure?.resolution?.action).toBe(action);
  if (detail !== undefined) expect(payload.failure?.detail).toBe(detail);
}

function expectApprovalRequired(payload: Payload) {
  expectRefused(payload, "approval_required", "request_approval");
  expect(payload.failure?.approval_required?.approval_request_id).toBeTruthy();
}

function recordAdapterCalls() {
  const calls: string[] = [];
  vi.spyOn(backendAdapter, "execute").mockImplementation(async (capability) => {
    calls.push(capability.capability_id);
    return { execution_status: "executed_by_test" };
  });
  return calls;
}

async function evaluate(capabilityId: string, rootPrincipal: string) {
  return evaluatePolicy({ capability: { capability_id: capabilityId } as any, params: {}, rootPrincipal });
}

describe("generated policy rules", () => {
  afterEach(() => vi.restoreAllMocks());

  it("rule 1: a matching deny refuses a read capability", async () => {
    expectRefused(await invoke("contractor-key", "conformance.lookup", ["conformance.read"], { query: "records" }), "denied", "contact_service_owner", "Contractors cannot read records.");
  });

  it("rule 1: a matching deny refuses a governed capability", async () => {
    expectRefused(await invoke("analyst-key", "conformance.prepare_change", ["conformance.prepare"], CHANGE), "denied", "contact_service_owner", "Analysts cannot prepare changes.");
  });

  it("rule 1: a child deny applies at a composition step", async () => {
    // The deny binding names only the child; the composition reaches it as a step.
    expectRefused(await invoke("analyst-key", "conformance.lookup_and_prepare", ["conformance.read", "conformance.prepare"], { query: "CON-1", requested_status: "done", change_reason: "policy rules" }), "denied", "contact_service_owner", "Analysts cannot prepare changes.");
  });

  it("rule 1: an unrecognised decision refuses", async () => {
    expectRefused(await invoke("auditor-key", "conformance.lookup", ["conformance.read"], { query: "records" }), "denied", "contact_service_owner");
  });

  it("a clarify binding applies to a read capability", async () => {
    expectRefused(await invoke("intern-key", "conformance.lookup", ["conformance.read"], { query: "records" }), "clarification_required", "obtain_binding", "Interns must say which team they read for.");
  });

  it("rule 2: an actor matching no binding is refused", async () => {
    expectRefused(await invoke("visitor-key", "conformance.lookup", ["conformance.read"], { query: "records" }), "denied", "contact_service_owner", NO_MATCH);
  });

  it("rule 2: a principal without actor claims is refused", async () => {
    expectRefused(await invoke("dev-admin-key", "conformance.lookup", ["conformance.read"], { query: "records" }), "denied", "contact_service_owner", NO_MATCH);
    expect((await evaluate("conformance.lookup", "")).decision).toBe("deny");
  });

  it("rule 2: composition children are checked", async () => {
    const payload = await invoke("dev-admin-key", "conformance.lookup_and_prepare", ["conformance.read", "conformance.prepare"], { query: "CON-1", requested_status: "done", change_reason: "policy rules" });
    expect(payload.success).toBe(false);
    expect(payload.failure?.type).toBe("denied");
  });

  it("rule 3: a capability without bindings is allowed", async () => {
    for (const principal of ["human:visitor|actor_id=visitor", "human:local-developer", ""]) {
      expect((await evaluate("conformance.unbound", principal)).decision).toBe("allow");
    }
  });

  it("rule 4: an allowed actor stops before the adapter", async () => {
    const calls = recordAdapterCalls();
    expectApprovalRequired(await invoke("contractor-key", "conformance.prepare_change", ["conformance.prepare"], CHANGE));
    expect(calls).toEqual([]);
  });

  it("rule 4: a validated grant reaches the adapter", async () => {
    const calls = recordAdapterCalls();
    const first = await invoke("contractor-key", "conformance.prepare_change", ["conformance.prepare"], CHANGE);
    expectApprovalRequired(first);
    const second = await invoke("contractor-key", "conformance.prepare_change", ["conformance.prepare"], CHANGE, await approve(first));
    expect(second.success).toBe(true);
    expect(second.result?.execution_status).toBe("executed_by_test");
    expect(calls).toEqual(["conformance.prepare_change"]);
  });

  it("rule 4: a grant satisfies an approval binding", async () => {
    const calls = recordAdapterCalls();
    const first = await invoke("manager-key", "conformance.prepare_change", ["conformance.prepare"], CHANGE);
    expectApprovalRequired(first);
    expect(calls).toEqual([]);
    const second = await invoke("manager-key", "conformance.prepare_change", ["conformance.prepare"], CHANGE, await approve(first));
    expect(second.success).toBe(true);
    expect(calls).toEqual(["conformance.prepare_change"]);
  });

  it("rule 4: a composition stops at an approval-gated child", async () => {
    expectApprovalRequired(await invoke("manager-key", "conformance.lookup_and_prepare", ["conformance.read", "conformance.prepare"], { query: "CON-1", requested_status: "done", change_reason: "policy rules" }));
  });
});
`, "\n"), "__NO_MATCH__", generatedPolicyNoMatchDetail)
}

func goExecutablePolicyRulesTest() string {
	return strings.ReplaceAll(strings.TrimLeft(`
package app

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"reflect"
	"testing"

	"generated/generator-conformance-service/extensions"
	"generated/generator-conformance-service/generated"
)

const policyRulesNoMatch = "__NO_MATCH__"

var policyRulesChange = map[string]any{"record_ref": "CON-1", "new_status": "done", "change_reason": "policy rules"}

type policyRulesRecorder struct{ calls *[]string }

func (recorder policyRulesRecorder) Execute(capability generated.GeneratedCapabilityRuntimeMetadata, _ generated.BackendInvocationPlan, _ map[string]any, _ extensions.BackendInvocationContext) (map[string]any, error) {
	*recorder.calls = append(*recorder.calls, capability.CapabilityID)
	return map[string]any{"execution_status": "executed_by_test"}, nil
}

func policyRulesServer(t *testing.T) *httptest.Server {
	t.Helper()
	svc, err := NewService()
	if err != nil {
		t.Fatalf("NewService: %v", err)
	}
	ts := httptest.NewServer(NewMux(svc))
	t.Cleanup(func() {
		ts.Close()
		svc.Shutdown()
	})
	return ts
}

func policyRulesRecordAdapterCalls(t *testing.T) *[]string {
	t.Helper()
	calls := []string{}
	original := extensions.BackendAdapterInstance
	extensions.BackendAdapterInstance = policyRulesRecorder{calls: &calls}
	t.Cleanup(func() { extensions.BackendAdapterInstance = original })
	return &calls
}

func policyRulesPost(t *testing.T, ts *httptest.Server, path string, bearer string, body map[string]any) (int, map[string]any) {
	t.Helper()
	encoded, _ := json.Marshal(body)
	req, _ := http.NewRequest(http.MethodPost, ts.URL+path, bytes.NewReader(encoded))
	req.Header.Set("Authorization", "Bearer "+bearer)
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("POST %s: %v", path, err)
	}
	defer resp.Body.Close()
	var payload map[string]any
	_ = json.NewDecoder(resp.Body).Decode(&payload)
	return resp.StatusCode, payload
}

func policyRulesToken(t *testing.T, ts *httptest.Server, key string, capability string, scope []string) string {
	t.Helper()
	status, payload := policyRulesPost(t, ts, "/anip/tokens", key, map[string]any{"capability": capability, "scope": scope, "subject": key})
	token, _ := payload["token"].(string)
	if status != http.StatusOK || token == "" {
		t.Fatalf("token for %s: %d %#v", key, status, payload)
	}
	return token
}

func policyRulesInvoke(t *testing.T, ts *httptest.Server, key string, capability string, scope []string, parameters map[string]any, approvalGrant string) map[string]any {
	t.Helper()
	body := map[string]any{"parameters": parameters}
	if approvalGrant != "" {
		body["approval_grant"] = approvalGrant
	}
	_, payload := policyRulesPost(t, ts, "/anip/invoke/"+capability, policyRulesToken(t, ts, key, capability, scope), body)
	return payload
}

func policyRulesApprove(t *testing.T, ts *httptest.Server, payload map[string]any) string {
	t.Helper()
	failure, _ := payload["failure"].(map[string]any)
	request, _ := failure["approval_required"].(map[string]any)
	approver := policyRulesToken(t, ts, "approver-key", "conformance.prepare_change", []string{"conformance.prepare", "approver:*"})
	status, grant := policyRulesPost(t, ts, "/anip/approval_grants", approver, map[string]any{"approval_request_id": request["approval_request_id"], "grant_type": "one_time"})
	grantID, _ := grant["grant_id"].(string)
	if status != http.StatusOK || grantID == "" {
		t.Fatalf("approval grant: %d %#v", status, grant)
	}
	return grantID
}

func policyRulesRefused(t *testing.T, payload map[string]any, failureType string, action string, detail string) {
	t.Helper()
	failure, _ := payload["failure"].(map[string]any)
	resolution, _ := failure["resolution"].(map[string]any)
	if payload["success"] != false || failure["type"] != failureType || resolution["action"] != action {
		t.Fatalf("expected %s/%s, got %#v", failureType, action, payload)
	}
	if detail != "" && failure["detail"] != detail {
		t.Fatalf("expected detail %q, got %#v", detail, failure["detail"])
	}
}

func policyRulesApprovalRequired(t *testing.T, payload map[string]any) {
	t.Helper()
	policyRulesRefused(t, payload, "approval_required", "request_approval", "")
	request, _ := payload["failure"].(map[string]any)["approval_required"].(map[string]any)
	if id, _ := request["approval_request_id"].(string); id == "" {
		t.Fatalf("approval_required without an approval request: %#v", payload)
	}
}

func policyRulesEvaluate(capabilityID string, rootPrincipal string) string {
	return extensions.EvaluatePolicy(extensions.PolicyContext{
		Capability:    generated.GeneratedCapabilityRuntimeMetadata{CapabilityID: capabilityID},
		Params:        map[string]any{},
		RootPrincipal: rootPrincipal,
	}).Decision
}

func TestPolicyRule1MatchingDenyRefuses(t *testing.T) {
	ts := policyRulesServer(t)
	policyRulesRefused(t, policyRulesInvoke(t, ts, "contractor-key", "conformance.lookup", []string{"conformance.read"}, map[string]any{"query": "records"}, ""), "denied", "contact_service_owner", "Contractors cannot read records.")
	policyRulesRefused(t, policyRulesInvoke(t, ts, "analyst-key", "conformance.prepare_change", []string{"conformance.prepare"}, policyRulesChange, ""), "denied", "contact_service_owner", "Analysts cannot prepare changes.")
	policyRulesRefused(t, policyRulesInvoke(t, ts, "auditor-key", "conformance.lookup", []string{"conformance.read"}, map[string]any{"query": "records"}, ""), "denied", "contact_service_owner", "")
}

// The deny binding names only the child; the composition reaches it as a step.
func TestPolicyRule1ChildDenyAppliesAtCompositionStep(t *testing.T) {
	ts := policyRulesServer(t)
	policyRulesRefused(t, policyRulesInvoke(t, ts, "analyst-key", "conformance.lookup_and_prepare", []string{"conformance.read", "conformance.prepare"}, map[string]any{"query": "CON-1", "requested_status": "done", "change_reason": "policy rules"}, ""), "denied", "contact_service_owner", "Analysts cannot prepare changes.")
}

func TestPolicyClarifyAppliesToReadCapability(t *testing.T) {
	ts := policyRulesServer(t)
	policyRulesRefused(t, policyRulesInvoke(t, ts, "intern-key", "conformance.lookup", []string{"conformance.read"}, map[string]any{"query": "records"}, ""), "clarification_required", "obtain_binding", "Interns must say which team they read for.")
}

func TestPolicyRule2UnmatchedActorIsRefused(t *testing.T) {
	ts := policyRulesServer(t)
	policyRulesRefused(t, policyRulesInvoke(t, ts, "visitor-key", "conformance.lookup", []string{"conformance.read"}, map[string]any{"query": "records"}, ""), "denied", "contact_service_owner", policyRulesNoMatch)
	policyRulesRefused(t, policyRulesInvoke(t, ts, "dev-admin-key", "conformance.lookup", []string{"conformance.read"}, map[string]any{"query": "records"}, ""), "denied", "contact_service_owner", policyRulesNoMatch)
	if decision := policyRulesEvaluate("conformance.lookup", ""); decision != "deny" {
		t.Fatalf("empty principal on a bound capability: %q", decision)
	}
	composed := policyRulesInvoke(t, ts, "dev-admin-key", "conformance.lookup_and_prepare", []string{"conformance.read", "conformance.prepare"}, map[string]any{"query": "CON-1", "requested_status": "done", "change_reason": "policy rules"}, "")
	if failure, _ := composed["failure"].(map[string]any); composed["success"] != false || failure["type"] != "denied" {
		t.Fatalf("composition child policy was not applied: %#v", composed)
	}
}

func TestPolicyRule3CapabilityWithoutBindingsIsAllowed(t *testing.T) {
	for _, principal := range []string{"human:visitor|actor_id=visitor", "human:local-developer", ""} {
		if decision := policyRulesEvaluate("conformance.unbound", principal); decision != "allow" {
			t.Fatalf("%q: %q", principal, decision)
		}
	}
}

func TestPolicyRule4ApprovalGatedStopsBeforeAdapter(t *testing.T) {
	ts := policyRulesServer(t)
	calls := policyRulesRecordAdapterCalls(t)
	policyRulesApprovalRequired(t, policyRulesInvoke(t, ts, "contractor-key", "conformance.prepare_change", []string{"conformance.prepare"}, policyRulesChange, ""))
	if len(*calls) != 0 {
		t.Fatalf("adapter ran before approval: %#v", *calls)
	}
	policyRulesApprovalRequired(t, policyRulesInvoke(t, ts, "manager-key", "conformance.lookup_and_prepare", []string{"conformance.read", "conformance.prepare"}, map[string]any{"query": "CON-1", "requested_status": "done", "change_reason": "policy rules"}, ""))
}

func TestPolicyRule4ValidatedGrantReachesAdapter(t *testing.T) {
	for _, key := range []string{"contractor-key", "manager-key"} {
		t.Run(key, func(t *testing.T) {
			ts := policyRulesServer(t)
			calls := policyRulesRecordAdapterCalls(t)
			first := policyRulesInvoke(t, ts, key, "conformance.prepare_change", []string{"conformance.prepare"}, policyRulesChange, "")
			policyRulesApprovalRequired(t, first)
			second := policyRulesInvoke(t, ts, key, "conformance.prepare_change", []string{"conformance.prepare"}, policyRulesChange, policyRulesApprove(t, ts, first))
			result, _ := second["result"].(map[string]any)
			if second["success"] != true || result["execution_status"] != "executed_by_test" {
				t.Fatalf("approved invocation did not reach the adapter: %#v", second)
			}
			if !reflect.DeepEqual(*calls, []string{"conformance.prepare_change"}) {
				t.Fatalf("adapter calls: %#v", *calls)
			}
		})
	}
}
`, "\n"), "__NO_MATCH__", generatedPolicyNoMatchDetail)
}

func javaExecutablePolicyRulesTest() string {
	return strings.ReplaceAll(strings.TrimLeft(`
package dev.anip.generated.generator_conformance_service;

import dev.anip.core.DelegationToken;
import dev.anip.core.TokenResponse;
import dev.anip.service.ANIPService;
import dev.anip.service.InvokeOpts;
import dev.anip.service.ServiceConfig;

import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class GeneratedPolicyRulesTest {
    private static final String NO_MATCH = "__NO_MATCH__";
    private static final Map<String, Object> CHANGE = Map.of("record_ref", "CON-1", "new_status", "done", "change_reason", "policy rules");
    private static final Map<String, Object> COMPOSED = Map.of("query", "CON-1", "requested_status", "done", "change_reason", "policy rules");
    private final List<String> calls = new ArrayList<>();

    private ANIPService newService(BackendAdapter adapter) throws Exception {
        ANIPService service = new ANIPService(new ServiceConfig()
                .setServiceId("generator-conformance-service")
                .setCapabilities(GeneratedCapabilities.createAll(adapter))
                .setStorage(":memory:")
                .setTrust("signed")
                .setKeyPath(null));
        service.start();
        return service;
    }

    private BackendAdapter recording() {
        return (capability, plan, input, context) -> {
            calls.add(String.valueOf(capability.get("capability_id")));
            Map<String, Object> result = new LinkedHashMap<>();
            result.put("execution_status", "executed_by_test");
            return result;
        };
    }

    private Map<String, Object> invoke(ANIPService service, String principal, String capability, List<String> scope, Map<String, Object> parameters, String approvalGrant) throws Exception {
        TokenResponse response = service.issueCapabilityToken(principal, capability, scope);
        DelegationToken token = service.resolveBearerToken(response.getToken());
        InvokeOpts opts = new InvokeOpts();
        if (approvalGrant != null) opts.setApprovalGrant(approvalGrant);
        return service.invoke(capability, token, parameters, opts);
    }

    @SuppressWarnings("unchecked")
    private String approve(ANIPService service, Map<String, Object> payload) throws Exception {
        Map<String, Object> failure = (Map<String, Object>) payload.get("failure");
        Map<String, Object> request = (Map<String, Object>) failure.get("approval_required");
        return service.issueApprovalGrant(String.valueOf(request.get("approval_request_id")), "one_time",
                Map.of("subject", "human:approver", "root_principal", "human:approver"), null, null, null).getGrantId();
    }

    @SuppressWarnings("unchecked")
    private void assertRefused(Map<String, Object> payload, String type, String action, String detail) {
        assertFalse((Boolean) payload.get("success"), String.valueOf(payload));
        Map<String, Object> failure = (Map<String, Object>) payload.get("failure");
        assertEquals(type, failure.get("type"), String.valueOf(payload));
        assertEquals(action, ((Map<String, Object>) failure.get("resolution")).get("action"), String.valueOf(payload));
        if (detail != null) assertEquals(detail, failure.get("detail"));
    }

    @SuppressWarnings("unchecked")
    private void assertApprovalRequired(Map<String, Object> payload) {
        assertRefused(payload, "approval_required", "request_approval", null);
        Map<String, Object> request = (Map<String, Object>) ((Map<String, Object>) payload.get("failure")).get("approval_required");
        assertTrue(String.valueOf(request.get("approval_request_id")).length() > 0);
    }

    private String evaluate(String capabilityId, String principal) {
        return Policy.evaluate(Map.of("capability_id", capabilityId), Map.of(), principal).decision();
    }

    @Test
    void rule1MatchingDenyRefuses() throws Exception {
        ANIPService service = newService(BackendAdapter.defaultAdapter());
        try {
            assertRefused(invoke(service, "human:contractor|actor_id=contractor", "conformance.lookup", List.of("conformance.read"), Map.of("query", "records"), null), "denied", "contact_service_owner", "Contractors cannot read records.");
            assertRefused(invoke(service, "human:analyst|actor_id=analyst", "conformance.prepare_change", List.of("conformance.prepare"), CHANGE, null), "denied", "contact_service_owner", "Analysts cannot prepare changes.");
            assertRefused(invoke(service, "human:auditor|actor_id=auditor", "conformance.lookup", List.of("conformance.read"), Map.of("query", "records"), null), "denied", "contact_service_owner", null);
        } finally {
            service.shutdown();
        }
    }

    @Test
    void rule1ChildDenyAppliesAtCompositionStep() throws Exception {
        // The deny binding names only the child; the composition reaches it as a step.
        ANIPService service = newService(BackendAdapter.defaultAdapter());
        try {
            assertRefused(invoke(service, "human:analyst|actor_id=analyst", "conformance.lookup_and_prepare", List.of("conformance.read", "conformance.prepare"), COMPOSED, null), "denied", "contact_service_owner", "Analysts cannot prepare changes.");
        } finally {
            service.shutdown();
        }
    }

    @Test
    void clarifyAppliesToReadCapability() throws Exception {
        ANIPService service = newService(BackendAdapter.defaultAdapter());
        try {
            assertRefused(invoke(service, "human:intern|actor_id=intern", "conformance.lookup", List.of("conformance.read"), Map.of("query", "records"), null), "clarification_required", "obtain_binding", "Interns must say which team they read for.");
        } finally {
            service.shutdown();
        }
    }

    @Test
    @SuppressWarnings("unchecked")
    void rule2UnmatchedActorIsRefused() throws Exception {
        ANIPService service = newService(BackendAdapter.defaultAdapter());
        try {
            assertRefused(invoke(service, "human:visitor|actor_id=visitor", "conformance.lookup", List.of("conformance.read"), Map.of("query", "records"), null), "denied", "contact_service_owner", NO_MATCH);
            assertRefused(invoke(service, "human:local-developer", "conformance.lookup", List.of("conformance.read"), Map.of("query", "records"), null), "denied", "contact_service_owner", NO_MATCH);
            assertEquals("deny", evaluate("conformance.lookup", ""));
            Map<String, Object> composed = invoke(service, "human:local-developer", "conformance.lookup_and_prepare", List.of("conformance.read", "conformance.prepare"), COMPOSED, null);
            assertFalse((Boolean) composed.get("success"));
            assertEquals("denied", ((Map<String, Object>) composed.get("failure")).get("type"));
        } finally {
            service.shutdown();
        }
    }

    @Test
    void rule3CapabilityWithoutBindingsIsAllowed() {
        for (String principal : List.of("human:visitor|actor_id=visitor", "human:local-developer", "")) {
            assertEquals("allow", evaluate("conformance.unbound", principal), principal);
        }
    }

    @Test
    void rule4ApprovalGatedStopsBeforeAdapter() throws Exception {
        ANIPService service = newService(recording());
        try {
            assertApprovalRequired(invoke(service, "human:contractor|actor_id=contractor", "conformance.prepare_change", List.of("conformance.prepare"), CHANGE, null));
            assertEquals(List.of(), calls);
        } finally {
            service.shutdown();
        }
        ANIPService defaults = newService(BackendAdapter.defaultAdapter());
        try {
            assertApprovalRequired(invoke(defaults, "human:manager|actor_id=manager", "conformance.lookup_and_prepare", List.of("conformance.read", "conformance.prepare"), COMPOSED, null));
        } finally {
            defaults.shutdown();
        }
    }

    @Test
    @SuppressWarnings("unchecked")
    void rule4ValidatedGrantReachesAdapter() throws Exception {
        for (String principal : List.of("human:contractor|actor_id=contractor", "human:manager|actor_id=manager")) {
            calls.clear();
            ANIPService service = newService(recording());
            try {
                Map<String, Object> first = invoke(service, principal, "conformance.prepare_change", List.of("conformance.prepare"), CHANGE, null);
                assertApprovalRequired(first);
                assertEquals(List.of(), calls);
                Map<String, Object> second = invoke(service, principal, "conformance.prepare_change", List.of("conformance.prepare"), CHANGE, approve(service, first));
                assertTrue((Boolean) second.get("success"), String.valueOf(second));
                assertEquals("executed_by_test", ((Map<String, Object>) second.get("result")).get("execution_status"));
                assertEquals(List.of("conformance.prepare_change"), calls);
            } finally {
                service.shutdown();
            }
        }
    }
}
`, "\n"), "__NO_MATCH__", generatedPolicyNoMatchDetail)
}

func csharpExecutablePolicyRulesTest() string {
	return strings.ReplaceAll(strings.TrimLeft(`
using Anip.Core;
using Anip.Service;
using Xunit;
using GeneratorConformanceService;

namespace GeneratorConformanceService.Tests;

public class GeneratedPolicyRulesTests
{
    private const string NoMatch = "__NO_MATCH__";
    private readonly List<string> _calls = [];

    private static Dictionary<string, object?> Change() => new()
    {
        ["record_ref"] = "CON-1",
        ["new_status"] = "done",
        ["change_reason"] = "policy rules",
    };

    private static Dictionary<string, object?> Composed() => new()
    {
        ["query"] = "CON-1",
        ["requested_status"] = "done",
        ["change_reason"] = "policy rules",
    };

    private static AnipService NewService(BackendAdapterHandler adapter)
    {
        var service = new AnipService(new ServiceConfig
        {
            ServiceId = "generator-conformance-service",
            Capabilities = GeneratedCapabilities.CreateAll(adapter),
            Storage = ":memory:",
            Trust = "signed",
            KeyPath = null,
            RetentionIntervalSeconds = -1,
        });
        service.Start();
        return service;
    }

    private BackendAdapterHandler Recording() => (capability, plan, input, context) =>
    {
        _calls.Add(capability["capability_id"]?.ToString() ?? "");
        return new Dictionary<string, object?> { ["execution_status"] = "executed_by_test" };
    };

    private static Dictionary<string, object?> Invoke(AnipService service, string principal, string capability, List<string> scope, Dictionary<string, object?> parameters, string? approvalGrant = null)
    {
        var response = service.IssueCapabilityToken(principal, capability, scope);
        var token = service.ResolveBearerToken(response.Token);
        return service.Invoke(capability, token, parameters, new InvokeOpts { ApprovalGrant = approvalGrant });
    }

    private static string Approve(AnipService service, Dictionary<string, object?> payload)
    {
        var failure = Assert.IsType<Dictionary<string, object?>>(payload["failure"]);
        var request = Assert.IsType<Dictionary<string, object?>>(failure["approval_required"]);
        return service.IssueApprovalGrant(request["approval_request_id"]!.ToString()!, "one_time",
            new Dictionary<string, object?> { ["subject"] = "human:approver", ["root_principal"] = "human:approver" }, null, null, null).GrantId;
    }

    private static void AssertRefused(Dictionary<string, object?> payload, string type, string action, string? detail = null)
    {
        Assert.False((bool)payload["success"]!);
        var failure = Assert.IsType<Dictionary<string, object?>>(payload["failure"]);
        Assert.Equal(type, failure["type"]);
        Assert.Equal(action, Assert.IsType<Dictionary<string, object?>>(failure["resolution"])["action"]);
        if (detail is not null) Assert.Equal(detail, failure["detail"]);
    }

    private static void AssertApprovalRequired(Dictionary<string, object?> payload)
    {
        AssertRefused(payload, "approval_required", "request_approval");
        var failure = Assert.IsType<Dictionary<string, object?>>(payload["failure"]);
        var request = Assert.IsType<Dictionary<string, object?>>(failure["approval_required"]);
        Assert.False(string.IsNullOrWhiteSpace(request["approval_request_id"]?.ToString()));
    }

    private static string Evaluate(string capabilityId, string principal) =>
        Policy.Evaluate(new Dictionary<string, object?> { ["capability_id"] = capabilityId }, [], principal).Decision;

    [Fact]
    public void Rule1MatchingDenyRefuses()
    {
        var service = NewService(BackendAdapter.Default);
        try
        {
            AssertRefused(Invoke(service, "human:contractor|actor_id=contractor", "conformance.lookup", ["conformance.read"], new() { ["query"] = "records" }), "denied", "contact_service_owner", "Contractors cannot read records.");
            AssertRefused(Invoke(service, "human:analyst|actor_id=analyst", "conformance.prepare_change", ["conformance.prepare"], Change()), "denied", "contact_service_owner", "Analysts cannot prepare changes.");
            AssertRefused(Invoke(service, "human:auditor|actor_id=auditor", "conformance.lookup", ["conformance.read"], new() { ["query"] = "records" }), "denied", "contact_service_owner");
        }
        finally
        {
            service.Shutdown();
        }
    }

    [Fact]
    public void Rule1ChildDenyAppliesAtCompositionStep()
    {
        // The deny binding names only the child; the composition reaches it as a step.
        var service = NewService(BackendAdapter.Default);
        try
        {
            AssertRefused(Invoke(service, "human:analyst|actor_id=analyst", "conformance.lookup_and_prepare", ["conformance.read", "conformance.prepare"], Composed()), "denied", "contact_service_owner", "Analysts cannot prepare changes.");
        }
        finally
        {
            service.Shutdown();
        }
    }

    [Fact]
    public void ClarifyAppliesToReadCapability()
    {
        var service = NewService(BackendAdapter.Default);
        try
        {
            AssertRefused(Invoke(service, "human:intern|actor_id=intern", "conformance.lookup", ["conformance.read"], new() { ["query"] = "records" }), "clarification_required", "obtain_binding", "Interns must say which team they read for.");
        }
        finally
        {
            service.Shutdown();
        }
    }

    [Fact]
    public void Rule2UnmatchedActorIsRefused()
    {
        var service = NewService(BackendAdapter.Default);
        try
        {
            AssertRefused(Invoke(service, "human:visitor|actor_id=visitor", "conformance.lookup", ["conformance.read"], new() { ["query"] = "records" }), "denied", "contact_service_owner", NoMatch);
            AssertRefused(Invoke(service, "human:local-developer", "conformance.lookup", ["conformance.read"], new() { ["query"] = "records" }), "denied", "contact_service_owner", NoMatch);
            Assert.Equal("deny", Evaluate("conformance.lookup", ""));
            var composed = Invoke(service, "human:local-developer", "conformance.lookup_and_prepare", ["conformance.read", "conformance.prepare"], Composed());
            Assert.False((bool)composed["success"]!);
            Assert.Equal("denied", Assert.IsType<Dictionary<string, object?>>(composed["failure"])["type"]);
        }
        finally
        {
            service.Shutdown();
        }
    }

    [Fact]
    public void Rule3CapabilityWithoutBindingsIsAllowed()
    {
        foreach (var principal in new[] { "human:visitor|actor_id=visitor", "human:local-developer", "" })
        {
            Assert.Equal("allow", Evaluate("conformance.unbound", principal));
        }
    }

    [Fact]
    public void Rule4ApprovalGatedStopsBeforeAdapter()
    {
        var service = NewService(Recording());
        try
        {
            AssertApprovalRequired(Invoke(service, "human:contractor|actor_id=contractor", "conformance.prepare_change", ["conformance.prepare"], Change()));
            Assert.Empty(_calls);
        }
        finally
        {
            service.Shutdown();
        }
        var defaults = NewService(BackendAdapter.Default);
        try
        {
            AssertApprovalRequired(Invoke(defaults, "human:manager|actor_id=manager", "conformance.lookup_and_prepare", ["conformance.read", "conformance.prepare"], Composed()));
        }
        finally
        {
            defaults.Shutdown();
        }
    }

    [Theory]
    [InlineData("human:contractor|actor_id=contractor")]
    [InlineData("human:manager|actor_id=manager")]
    public void Rule4ValidatedGrantReachesAdapter(string principal)
    {
        var service = NewService(Recording());
        try
        {
            var first = Invoke(service, principal, "conformance.prepare_change", ["conformance.prepare"], Change());
            AssertApprovalRequired(first);
            Assert.Empty(_calls);
            var second = Invoke(service, principal, "conformance.prepare_change", ["conformance.prepare"], Change(), Approve(service, first));
            Assert.True((bool)second["success"]!);
            Assert.Equal("executed_by_test", Assert.IsType<Dictionary<string, object?>>(second["result"])["execution_status"]);
            Assert.Equal(["conformance.prepare_change"], _calls);
        }
        finally
        {
            service.Shutdown();
        }
    }
}
`, "\n"), "__NO_MATCH__", generatedPolicyNoMatchDetail)
}
