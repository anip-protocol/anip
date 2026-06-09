package extensions

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"strings"
	"sync"

	"generated/gtm-pipeline-q2-review/generated"
	"github.com/anip-protocol/anip/packages/go/core"
)

type BackendInvocationContext struct {
	RootPrincipal string
}

type BackendAdapter interface {
	Execute(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, adapterInput map[string]any, context BackendInvocationContext) (map[string]any, error)
}

type gtmProxyBackendAdapter struct {
	manifestScopes sync.Map
}

func CreateDefaultBackendAdapter() BackendAdapter {
	return &gtmProxyBackendAdapter{}
}

func (adapter *gtmProxyBackendAdapter) Execute(capability generated.GeneratedCapabilityRuntimeMetadata, plan generated.BackendInvocationPlan, _ map[string]any, context BackendInvocationContext) (map[string]any, error) {
	if strings.TrimSpace(os.Getenv("GTM_ACTOR_TOKENS_JSON")) == "" {
		return map[string]any{
			"execution_status":       "backend_execution_stub",
			"capability_id":          capability.CapabilityID,
			"selected_backend":       plan.SelectedBinding,
			"semantic_input":         plan.SemanticInput,
			"backend_input_contract": plan.BackendInputContract,
			"note":                   "Set GTM_ACTOR_TOKENS_JSON to enable the Go GTM parity proxy.",
		}, nil
	}

	targetCapability := capability
	targetParams := plan.SemanticInput
	if finalStep := finalCompositionStep(capability); finalStep != nil {
		targetCapability = finalStep.capability
		targetParams = mapCompositionInput(finalStep.mapping, plan.SemanticInput)
	}

	services := downstreamServices()
	serviceURL := strings.TrimRight(services[targetCapability.ServiceID], "/")
	if serviceURL == "" {
		return nil, core.NewANIPError("temporarily_unavailable", "No downstream GTM service URL is configured for "+targetCapability.ServiceID+".")
	}
	bearer, err := bearerForContext(context)
	if err != nil {
		return nil, err
	}
	token, err := adapter.issueDownstreamToken(serviceURL, targetCapability, bearer)
	if err != nil {
		return nil, err
	}
	payload, status, err := postJSON(serviceURL+"/anip/invoke/"+targetCapability.CapabilityID, token, map[string]any{"parameters": targetParams})
	if err != nil {
		return nil, err
	}
	if status >= 400 || payload["failure"] != nil {
		return nil, downstreamFailure(payload)
	}
	result, ok := payload["result"].(map[string]any)
	if !ok {
		return map[string]any{"result": payload["result"]}, nil
	}
	return result, nil
}

type compositionStep struct {
	capability generated.GeneratedCapabilityRuntimeMetadata
	mapping    map[string]any
}

func finalCompositionStep(capability generated.GeneratedCapabilityRuntimeMetadata) *compositionStep {
	steps, ok := capability.Composition["steps"].([]any)
	if !ok || len(steps) == 0 {
		return nil
	}
	last, ok := steps[len(steps)-1].(map[string]any)
	if !ok {
		return nil
	}
	childID, _ := last["capability"].(string)
	if childID == "" {
		return nil
	}
	child, ok := findCapability(childID)
	if !ok {
		return nil
	}
	stepID, _ := last["id"].(string)
	mapping := map[string]any{}
	if inputMapping, ok := capability.Composition["input_mapping"].(map[string]any); ok {
		if stepMapping, ok := inputMapping[stepID].(map[string]any); ok {
			mapping = stepMapping
		}
	}
	return &compositionStep{capability: child, mapping: mapping}
}

func findCapability(capabilityID string) (generated.GeneratedCapabilityRuntimeMetadata, bool) {
	for _, capability := range generated.GeneratedCapabilityMetadata {
		if capability.CapabilityID == capabilityID {
			return capability, true
		}
	}
	return generated.GeneratedCapabilityRuntimeMetadata{}, false
}

func mapCompositionInput(mapping map[string]any, source map[string]any) map[string]any {
	if len(mapping) == 0 {
		return source
	}
	mapped := map[string]any{}
	for key, value := range mapping {
		if text, ok := value.(string); ok && strings.HasPrefix(text, "$.input.") {
			sourceKey := strings.TrimPrefix(text, "$.input.")
			if source[sourceKey] != nil {
				mapped[key] = source[sourceKey]
			}
			continue
		}
		mapped[key] = value
	}
	return mapped
}

func downstreamServices() map[string]string {
	services := map[string]string{
		"gtm-pipeline-service":       "http://127.0.0.1:4100",
		"gtm-enrichment-service":     "http://127.0.0.1:4101",
		"gtm-prioritization-service": "http://127.0.0.1:4102",
		"gtm-outreach-service":       "http://127.0.0.1:4103",
	}
	for key, value := range readStringMap("GTM_BACKEND_SERVICES_JSON") {
		services[key] = value
	}
	return services
}

func readStringMap(name string) map[string]string {
	raw := strings.TrimSpace(os.Getenv(name))
	if raw == "" {
		return map[string]string{}
	}
	decoded := map[string]string{}
	if err := json.Unmarshal([]byte(raw), &decoded); err != nil {
		return map[string]string{}
	}
	return decoded
}

func actorIDFromPrincipal(rootPrincipal string) string {
	for _, piece := range strings.Split(rootPrincipal, "|") {
		key, value, ok := strings.Cut(piece, "=")
		if ok && strings.TrimSpace(key) == "actor_id" {
			return strings.TrimSpace(value)
		}
	}
	return ""
}

func bearerForContext(context BackendInvocationContext) (string, error) {
	actorID := actorIDFromPrincipal(context.RootPrincipal)
	token := readStringMap("GTM_ACTOR_TOKENS_JSON")[actorID]
	if token == "" {
		return "", core.NewANIPError("access_denied", "No downstream GTM actor token is configured for the current actor.")
	}
	return token, nil
}

func (adapter *gtmProxyBackendAdapter) downstreamMinimumScope(serviceURL string, capability generated.GeneratedCapabilityRuntimeMetadata) []string {
	cacheKey := serviceURL + "|" + capability.CapabilityID
	if cached, ok := adapter.manifestScopes.Load(cacheKey); ok {
		return cached.([]string)
	}
	response, err := http.Get(serviceURL + "/anip/manifest")
	if err == nil && response.Body != nil {
		defer response.Body.Close()
		var manifest struct {
			Capabilities map[string]struct {
				MinimumScope []string `json:"minimum_scope"`
			} `json:"capabilities"`
		}
		if json.NewDecoder(response.Body).Decode(&manifest) == nil {
			if scope := manifest.Capabilities[capability.CapabilityID].MinimumScope; len(scope) > 0 {
				adapter.manifestScopes.Store(cacheKey, scope)
				return scope
			}
		}
	}
	adapter.manifestScopes.Store(cacheKey, capability.MinimumScope)
	return capability.MinimumScope
}

func (adapter *gtmProxyBackendAdapter) issueDownstreamToken(serviceURL string, capability generated.GeneratedCapabilityRuntimeMetadata, bearer string) (string, error) {
	payload, status, err := postJSON(serviceURL+"/anip/tokens", bearer, map[string]any{
		"subject":            "agent:anip-language-parity-bridge",
		"scope":              adapter.downstreamMinimumScope(serviceURL, capability),
		"capability":         capability.CapabilityID,
		"purpose_parameters": map[string]any{"source": "go_parity_bridge"},
	})
	if err != nil {
		return "", err
	}
	token, _ := payload["token"].(string)
	issued, _ := payload["issued"].(bool)
	if status >= 400 || !issued || token == "" {
		return "", core.NewANIPError("access_denied", "Downstream token issuance failed for "+capability.CapabilityID+".")
	}
	return token, nil
}

func postJSON(url string, bearer string, body map[string]any) (map[string]any, int, error) {
	content, _ := json.Marshal(body)
	request, err := http.NewRequest(http.MethodPost, url, bytes.NewReader(content))
	if err != nil {
		return nil, 0, err
	}
	request.Header.Set("authorization", "Bearer "+bearer)
	request.Header.Set("content-type", "application/json")
	response, err := http.DefaultClient.Do(request)
	if err != nil {
		return nil, 0, err
	}
	defer response.Body.Close()
	var payload map[string]any
	if err := json.NewDecoder(response.Body).Decode(&payload); err != nil {
		return nil, response.StatusCode, err
	}
	return payload, response.StatusCode, nil
}

func downstreamFailure(payload map[string]any) error {
	failure, _ := payload["failure"].(map[string]any)
	failureType, _ := failure["type"].(string)
	detail, _ := failure["detail"].(string)
	if failureType == "" {
		failureType = "backend_error"
	}
	if detail == "" {
		detail = fmt.Sprintf("Downstream GTM service rejected the invocation: %v", payload)
	}
	return core.NewANIPError(failureType, detail)
}

var BackendAdapterInstance = CreateDefaultBackendAdapter()
