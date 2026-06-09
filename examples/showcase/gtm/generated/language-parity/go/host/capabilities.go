package host

import (
	"encoding/json"
	"os"
	"slices"
	"strings"

	"generated/gtm-operator-contract-20260512235040/extensions"
	"generated/gtm-operator-contract-20260512235040/generated"
	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/service"
)

type activeBackendSelection struct {
	BackendKind   string `json:"backend_kind"`
	ConnectionRef string `json:"connection_ref"`
}

var activeSelections = readActiveSelections()
var activeServiceFilter = strings.TrimSpace(os.Getenv("ANIP_SERVICE_FILTER"))

var GeneratedCapabilities = mustBuildGeneratedCapabilities()

func readActiveSelections() map[string]activeBackendSelection {
	raw := os.Getenv("ANIP_ACTIVE_BACKEND_SELECTIONS_JSON")
	if raw == "" {
		return map[string]activeBackendSelection{}
	}
	var selections map[string]activeBackendSelection
	if err := json.Unmarshal([]byte(raw), &selections); err != nil {
		return map[string]activeBackendSelection{}
	}
	return selections
}

func mustBuildGeneratedCapabilities() []service.CapabilityDef {
	capabilities := make([]service.CapabilityDef, 0, len(generated.GeneratedCapabilityMetadata))
	for _, capability := range generated.GeneratedCapabilityMetadata {
		if activeServiceFilter != "" && capability.ServiceID != activeServiceFilter {
			continue
		}
		capabilities = append(capabilities, buildCapabilityDef(capability))
	}
	return capabilities
}

func buildCapabilityDef(capability generated.GeneratedCapabilityRuntimeMetadata) service.CapabilityDef {
	return service.CapabilityDef{
		Declaration: buildCapabilityDeclaration(capability),
		Handler: func(ctx *service.InvocationContext, params map[string]any) (map[string]any, error) {
			params = applyInputDefaults(capability, params)
			if err := assertRequiredSemanticInputs(capability, params); err != nil {
				return nil, err
			}
			if err := validateInputBehavior(capability, params); err != nil {
				return nil, err
			}
			rootPrincipal := ""
			if ctx != nil {
				rootPrincipal = ctx.RootPrincipal
			}
			policy := extensions.EvaluatePolicy(extensions.PolicyContext{Capability: capability, Params: params, RootPrincipal: rootPrincipal})
			if policy.Decision == "deny" {
				return nil, core.NewANIPError("denied", firstNonEmpty(policy.Detail, "Request denied for "+capability.CapabilityID+".")).WithResolution("contact_service_owner")
			}
			if policy.Decision == "clarify" {
				return nil, core.NewANIPError("clarification_required", firstNonEmpty(policy.Detail, "Clarification required for "+capability.CapabilityID+".")).WithResolution("obtain_binding")
			}
			plan := buildBackendInvocationPlan(capability, params)
			if policy.Decision == "approval_required" {
				return nil, core.NewANIPError("approval_required", firstNonEmpty(policy.Detail, "Approval required for "+capability.CapabilityID+".")).WithResolution("request_approval")
			}
			return extensions.BackendAdapterInstance.Execute(capability, plan, plan.AdapterInput, extensions.BackendInvocationContext{
				RootPrincipal: rootPrincipal,
			})
		},
	}
}

func buildCapabilityDeclaration(capability generated.GeneratedCapabilityRuntimeMetadata) core.CapabilityDeclaration {
	inputs := make([]core.CapabilityInput, 0, len(capability.RequiredInputs)+len(capability.OptionalInputs))
	for _, input := range capability.RequiredInputs {
		inputs = append(inputs, core.CapabilityInput{
			Name:            input.InputName,
			Type:            firstNonEmpty(input.InputType, "string"),
			Required:        true,
			Default:         defaultValue(input.DefaultValue),
			Description:     firstNonEmpty(input.Summary, input.InputName),
			SemanticType:    optionalString(input.SemanticType),
			EntityReference: input.EntityReference,
			AllowedValues:   input.AllowedValues,
			CatalogRef:      optionalString(input.CatalogRef),
			Resolution:      input.Resolution,
		})
	}
	for _, input := range capability.OptionalInputs {
		inputs = append(inputs, core.CapabilityInput{
			Name:            input.InputName,
			Type:            firstNonEmpty(input.InputType, "string"),
			Required:        false,
			Default:         defaultValue(input.DefaultValue),
			Description:     firstNonEmpty(input.Summary, input.InputName),
			SemanticType:    optionalString(input.SemanticType),
			EntityReference: input.EntityReference,
			AllowedValues:   input.AllowedValues,
			CatalogRef:      optionalString(input.CatalogRef),
			Resolution:      input.Resolution,
		})
	}
	return core.CapabilityDeclaration{
		Name:            capability.CapabilityID,
		Description:     capability.Summary,
		ContractVersion: "1.0",
		Inputs:          inputs,
		Output: core.CapabilityOutput{
			Type:   firstNonEmpty(capability.OutputShape, "governed_result"),
			Fields: []string{"execution_status", "capability_id", "semantic_input"},
		},
		SideEffect: core.SideEffect{
			Type:           sideEffectType(capability.SideEffectLevel),
			RollbackWindow: rollbackWindow(capability.SideEffectLevel),
		},
		MinimumScope:        capability.MinimumScope,
		Requires:            []core.CapabilityRequirement{},
		ComposesWith:        []core.CapabilityComposition{},
		Session:             &core.SessionInfo{Type: "stateless"},
		ResponseModes:       []string{"unary"},
		RequiresBinding:     []core.BindingRequirement{},
		ControlRequirements: []core.ControlRequirement{},
		RefreshVia:          []string{},
		VerifyVia:           []string{},
		CrossService:        nil,
		Kind:                declarationKind(capability),
		Composition:         declarationComposition(capability),
		GrantPolicy:         decodeGrantPolicy(capability.GrantPolicy),
	}
}

func declarationKind(capability generated.GeneratedCapabilityRuntimeMetadata) string {
	return firstNonEmpty(capability.Kind, "atomic")
}

func declarationComposition(capability generated.GeneratedCapabilityRuntimeMetadata) *core.Composition {
	return decodeComposition(capability.Composition)
}

func decodeComposition(value map[string]any) *core.Composition {
	if len(value) == 0 {
		return nil
	}
	content, err := json.Marshal(value)
	if err != nil {
		return nil
	}
	var composition core.Composition
	if err := json.Unmarshal(content, &composition); err != nil {
		return nil
	}
	return &composition
}

func decodeGrantPolicy(value map[string]any) *core.GrantPolicy {
	if len(value) == 0 {
		return nil
	}
	content, err := json.Marshal(value)
	if err != nil {
		return nil
	}
	var policy core.GrantPolicy
	if err := json.Unmarshal(content, &policy); err != nil {
		return nil
	}
	return &policy
}

func sideEffectType(sideEffectLevel string) string {
	switch {
	case contains(sideEffectLevel, "irreversible"):
		return "irreversible"
	case contains(sideEffectLevel, "transaction"):
		return "transactional"
	case contains(sideEffectLevel, "write"):
		return "write"
	default:
		return "read"
	}
}

func rollbackWindow(sideEffectLevel string) string {
	switch sideEffectType(sideEffectLevel) {
	case "read":
		return "not_applicable"
	case "irreversible":
		return "none"
	default:
		return "PT15M"
	}
}

func effectiveBackendInputContract(capability generated.GeneratedCapabilityRuntimeMetadata, selectedBinding *generated.GeneratedBackendBinding) generated.EffectiveBackendInputContract {
	mode := firstNonEmpty(pointerString(selectedBinding, func(binding *generated.GeneratedBackendBinding) string { return binding.BackendInputMode }), capability.BackendInputMode)
	if mode == "" {
		mode = "implicit"
	}
	derivedRequired := chooseBindingList(selectedBinding, func(binding *generated.GeneratedBackendBinding) []string { return binding.DerivedRequiredBackendInputs }, capability.DerivedRequiredBackendInputs)
	derivedOptional := chooseBindingList(selectedBinding, func(binding *generated.GeneratedBackendBinding) []string { return binding.DerivedOptionalBackendInputs }, capability.DerivedOptionalBackendInputs)
	explicitRequired := chooseBindingList(selectedBinding, func(binding *generated.GeneratedBackendBinding) []string {
		return binding.ExplicitRequiredBackendInputs
	}, capability.ExplicitRequiredBackendInputs)
	explicitOptional := chooseBindingList(selectedBinding, func(binding *generated.GeneratedBackendBinding) []string {
		return binding.ExplicitOptionalBackendInputs
	}, capability.ExplicitOptionalBackendInputs)
	switch mode {
	case "explicit":
		required := uniqueStrings(explicitRequired)
		optional := exclude(uniqueStrings(explicitOptional), required)
		return generated.EffectiveBackendInputContract{Mode: mode, Required: required, Optional: optional}
	case "hybrid":
		required := uniqueStrings(append(append([]string{}, derivedRequired...), explicitRequired...))
		optional := exclude(uniqueStrings(append(append([]string{}, derivedOptional...), explicitOptional...)), required)
		return generated.EffectiveBackendInputContract{Mode: mode, Required: required, Optional: optional}
	default:
		required := uniqueStrings(derivedRequired)
		optional := exclude(uniqueStrings(derivedOptional), required)
		return generated.EffectiveBackendInputContract{Mode: "implicit", Required: required, Optional: optional}
	}
}

func selectBackendBinding(capability generated.GeneratedCapabilityRuntimeMetadata) *generated.GeneratedBackendBinding {
	if len(capability.BackendBindings) == 0 {
		return nil
	}
	if len(capability.BackendBindings) == 1 {
		return &capability.BackendBindings[0]
	}
	configured, ok := activeSelections[capability.CapabilityID]
	if !ok {
		return &capability.BackendBindings[0]
	}
	for index := range capability.BackendBindings {
		binding := &capability.BackendBindings[index]
		if (configured.BackendKind == "" || configured.BackendKind == binding.BackendKind) && (configured.ConnectionRef == "" || configured.ConnectionRef == binding.ConnectionRef) {
			return binding
		}
	}
	return &capability.BackendBindings[0]
}

func buildBackendInvocationPlan(capability generated.GeneratedCapabilityRuntimeMetadata, params map[string]any) generated.BackendInvocationPlan {
	selectedBinding := selectBackendBinding(capability)
	contract := effectiveBackendInputContract(capability, selectedBinding)
	semanticKeys := map[string]struct{}{}
	for _, input := range capability.RequiredInputs {
		semanticKeys[input.InputName] = struct{}{}
	}
	for _, input := range capability.OptionalInputs {
		semanticKeys[input.InputName] = struct{}{}
	}
	semanticInput := map[string]any{}
	for key, value := range params {
		if _, ok := semanticKeys[key]; ok {
			semanticInput[key] = value
		}
	}
	adapterKeys := map[string]struct{}{}
	for key := range semanticKeys {
		adapterKeys[key] = struct{}{}
	}
	for _, key := range contract.Required {
		adapterKeys[key] = struct{}{}
	}
	for _, key := range contract.Optional {
		adapterKeys[key] = struct{}{}
	}
	adapterInput := map[string]any{}
	for key, value := range params {
		if _, ok := adapterKeys[key]; ok {
			adapterInput[key] = value
		}
	}
	unresolved := make([]string, 0)
	for _, key := range contract.Required {
		if _, ok := params[key]; !ok {
			unresolved = append(unresolved, key)
		}
	}
	return generated.BackendInvocationPlan{
		SelectedBinding:                 selectedBinding,
		SemanticInput:                   semanticInput,
		AdapterInput:                    adapterInput,
		BackendInputContract:            contract,
		UnresolvedRequiredBackendInputs: unresolved,
	}
}

func assertRequiredSemanticInputs(capability generated.GeneratedCapabilityRuntimeMetadata, params map[string]any) error {
	missing := make([]string, 0)
	for _, input := range capability.RequiredInputs {
		if strings.TrimSpace(input.DefaultValue) != "" {
			continue
		}
		value, ok := params[input.InputName]
		if !ok || value == nil || value == "" {
			missing = append(missing, input.InputName)
		}
	}
	if len(missing) == 0 {
		return nil
	}
	err := core.NewANIPError("clarification_required", "Required semantic inputs are missing for "+capability.CapabilityID+".").WithResolution("obtain_binding")
	err.Resolution.Requires = strings.Join(missing, ",")
	return err
}

func defaultValue(value string) any {
	if strings.TrimSpace(value) == "" {
		return nil
	}
	return value
}

func applyInputDefaults(capability generated.GeneratedCapabilityRuntimeMetadata, params map[string]any) map[string]any {
	normalized := make(map[string]any, len(params))
	for key, value := range params {
		normalized[key] = value
	}
	for _, input := range append(capability.RequiredInputs, capability.OptionalInputs...) {
		if input.Resolution != nil && input.Resolution.OnMissing != nil && *input.Resolution.OnMissing == core.ResolutionBehaviorOmit {
			continue
		}
		if strings.TrimSpace(input.DefaultValue) == "" {
			continue
		}
		value, ok := normalized[input.InputName]
		if !ok || value == nil || value == "" {
			normalized[input.InputName] = input.DefaultValue
		}
	}
	return normalized
}

func validateInputBehavior(capability generated.GeneratedCapabilityRuntimeMetadata, params map[string]any) error {
	for _, input := range append(capability.RequiredInputs, capability.OptionalInputs...) {
		value, ok := params[input.InputName]
		if !ok || value == nil || value == "" || len(input.AllowedValues) == 0 {
			continue
		}
		if slices.Contains(input.AllowedValues, strings.TrimSpace(toString(value))) {
			continue
		}
		if input.Resolution != nil && input.Resolution.Mode == core.ResolutionModeClosedValues && input.Resolution.OnUnresolved != nil && *input.Resolution.OnUnresolved == core.ResolutionBehaviorDeny {
			err := core.NewANIPError("denied", "Input "+input.InputName+" must use one of the declared allowed values.").WithResolution("contact_service_owner")
			err.Resolution.Requires = input.InputName
			return err
		}
		err := core.NewANIPError("clarification_required", "Input "+input.InputName+" must use one of the declared allowed values.").WithResolution("obtain_binding")
		err.Resolution.Requires = input.InputName
		return err
	}
	return nil
}

func toString(value any) string {
	if text, ok := value.(string); ok {
		return text
	}
	content, err := json.Marshal(value)
	if err != nil {
		return ""
	}
	return string(content)
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if strings.TrimSpace(value) != "" {
			return value
		}
	}
	return ""
}

func optionalString(value string) *string {
	value = strings.TrimSpace(value)
	if value == "" {
		return nil
	}
	return &value
}

func uniqueStrings(values []string) []string {
	result := make([]string, 0, len(values))
	for _, value := range values {
		value = strings.TrimSpace(value)
		if value == "" || slices.Contains(result, value) {
			continue
		}
		result = append(result, value)
	}
	return result
}

func exclude(values []string, excluded []string) []string {
	result := make([]string, 0, len(values))
	for _, value := range values {
		if slices.Contains(excluded, value) {
			continue
		}
		result = append(result, value)
	}
	return result
}

func contains(value string, needle string) bool {
	return strings.Contains(strings.ToLower(value), strings.ToLower(needle))
}

func pointerString[T any](value *T, read func(*T) string) string {
	if value == nil {
		return ""
	}
	return read(value)
}

func chooseBindingList(value *generated.GeneratedBackendBinding, read func(*generated.GeneratedBackendBinding) []string, fallback []string) []string {
	if value == nil {
		return fallback
	}
	items := read(value)
	if len(items) == 0 {
		return fallback
	}
	return items
}
