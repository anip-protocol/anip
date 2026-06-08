package generator

import (
	"encoding/json"
	"fmt"
	"strings"

	"github.com/anip-protocol/anip/packages/go/definitionvalidation"
)

type GeneratedServiceMetadata struct {
	ServiceID               string   `json:"service_id"`
	ServiceName             string   `json:"service_name"`
	SourceRole              string   `json:"source_role"`
	SourceCapabilities      []string `json:"source_capabilities"`
	FormalizedCapabilityIDs []string `json:"formalized_capability_ids"`
	OwnedConceptIDs         []string `json:"owned_concept_ids"`
}

type GeneratedCapabilityGovernance struct {
	ApprovalRuleRefs      []string `json:"approval_rule_refs"`
	DenialRuleRefs        []string `json:"denial_rule_refs"`
	ClarificationRuleRefs []string `json:"clarification_rule_refs"`
	AuditRequired         bool     `json:"audit_required"`
}

type GeneratedCapabilityRuntimeMetadata struct {
	ServiceID                     string                         `json:"service_id"`
	ServiceName                   string                         `json:"service_name"`
	CapabilityID                  string                         `json:"capability_id"`
	Title                         string                         `json:"title"`
	Summary                       string                         `json:"summary"`
	Kind                          string                         `json:"kind"`
	Composition                   *Composition                   `json:"composition,omitempty"`
	GrantPolicy                   *GrantPolicy                   `json:"grant_policy,omitempty"`
	IntentType                    string                         `json:"intent_type"`
	OperationType                 string                         `json:"operation_type"`
	ExecutionPosture              string                         `json:"execution_posture"`
	SideEffectLevel               string                         `json:"side_effect_level"`
	ImplementationFit             *ImplementationFit             `json:"implementation_fit,omitempty"`
	BusinessEffects               *BusinessEffects               `json:"business_effects,omitempty"`
	BackendOperation              string                         `json:"backend_operation"`
	PathTemplate                  string                         `json:"path_template"`
	OutputShape                   string                         `json:"output_shape"`
	SubjectKind                   string                         `json:"subject_kind"`
	ContextType                   string                         `json:"context_type"`
	OutputIntent                  string                         `json:"output_intent"`
	MinimumScope                  []string                       `json:"minimum_scope"`
	RequiredInputs                []CapabilityInputFormalization `json:"required_inputs"`
	OptionalInputs                []CapabilityInputFormalization `json:"optional_inputs"`
	SampleParameters              map[string]any                 `json:"sample_parameters"`
	BackendInputMode              string                         `json:"backend_input_mode"`
	DerivedRequiredBackendInputs  []string                       `json:"derived_required_backend_inputs"`
	DerivedOptionalBackendInputs  []string                       `json:"derived_optional_backend_inputs"`
	ExplicitRequiredBackendInputs []string                       `json:"explicit_required_backend_inputs"`
	ExplicitOptionalBackendInputs []string                       `json:"explicit_optional_backend_inputs"`
	BackendBindings               []IntegrationBackendBinding    `json:"backend_bindings"`
	Governance                    GeneratedCapabilityGovernance  `json:"governance"`
	OutboundControls              map[string]any                 `json:"outbound_controls"`
}

type GeneratedRuntimeTarget struct {
	SystemName        string                     `json:"system_name"`
	DomainName        string                     `json:"domain_name"`
	DeliveryModel     string                     `json:"delivery_model"`
	ArchitectureShape string                     `json:"architecture_shape"`
	Protocols         []string                   `json:"protocols"`
	Services          []GeneratedServiceMetadata `json:"services"`
	PolicyBindings    []RuntimePolicyBinding     `json:"policy_bindings,omitempty"`
	Authority         struct {
		ApprovalExpectation   string `json:"approval_expectation"`
		BlockedFailurePosture string `json:"blocked_failure_posture"`
	} `json:"authority"`
	Audit struct {
		DurableRecordsRequired    bool `json:"durable_records_required"`
		SearchableHistoryRequired bool `json:"searchable_history_required"`
	} `json:"audit"`
}

type GenerationModel struct {
	SystemName        string
	Definition        *AnipServiceDefinition
	RuntimeTarget     GeneratedRuntimeTarget
	Capabilities      []GeneratedCapabilityRuntimeMetadata
	DefinitionJSON    []byte
	RuntimeTargetJSON []byte
	CapabilitiesJSON  []byte
}

func firstGeneratedCapabilityID(model *GenerationModel) string {
	if model != nil && len(model.Capabilities) > 0 && strings.TrimSpace(model.Capabilities[0].CapabilityID) != "" {
		return model.Capabilities[0].CapabilityID
	}
	return "generated.capability"
}

func BuildGenerationModel(definition *AnipServiceDefinition) (*GenerationModel, error) {
	if err := assertDefinition(definition); err != nil {
		return nil, err
	}

	generation := definition.Generation
	if generation == nil {
		generation = &GenerationConfig{}
	}
	authority := definition.Authority
	if authority == nil {
		authority = &AuthorityConfig{}
	}
	audit := definition.Audit
	if audit == nil {
		audit = &AuditConfig{}
	}

	systemName := strings.TrimSpace(definition.Identity.SystemName)
	services := buildServiceMetadata(definition)
	capabilities := buildCapabilityMetadata(definition, services)
	if len(capabilities) == 0 {
		return nil, fmt.Errorf("service definition must include at least one capability formalization")
	}

	runtimeTarget := GeneratedRuntimeTarget{
		SystemName:        systemName,
		DomainName:        fallbackString(definition.Identity.DomainName, "unspecified"),
		DeliveryModel:     fallbackString(definition.Identity.DeliveryModel, "service_platform"),
		ArchitectureShape: fallbackString(definition.Identity.ArchitectureShape, "single_service"),
		Protocols:         uniqueStrings(fallbackStrings(generation.Protocols, []string{"https"})),
		Services:          services,
	}
	runtimeTarget.Authority.ApprovalExpectation = fallbackString(authority.ApprovalExpectation, "project_specific")
	runtimeTarget.Authority.BlockedFailurePosture = fallbackString(authority.BlockedFailurePosture, "clarify_or_stop")
	runtimeTarget.Audit.DurableRecordsRequired = audit.DurableRecordsRequired
	runtimeTarget.Audit.SearchableHistoryRequired = audit.SearchableHistoryRequired
	runtimeTarget.PolicyBindings = buildRuntimePolicyBindings(definition, capabilities)

	definitionJSON, err := NormalizeServiceDefinitionBytes(definition)
	if err != nil {
		return nil, err
	}
	runtimeTargetJSON, err := marshalIndented(runtimeTarget)
	if err != nil {
		return nil, fmt.Errorf("encode runtime target: %w", err)
	}
	capabilitiesJSON, err := marshalIndented(capabilities)
	if err != nil {
		return nil, fmt.Errorf("encode capability metadata: %w", err)
	}

	return &GenerationModel{
		SystemName:        systemName,
		Definition:        definition,
		RuntimeTarget:     runtimeTarget,
		Capabilities:      capabilities,
		DefinitionJSON:    definitionJSON,
		RuntimeTargetJSON: runtimeTargetJSON,
		CapabilitiesJSON:  capabilitiesJSON,
	}, nil
}

func buildRuntimePolicyBindings(definition *AnipServiceDefinition, capabilities []GeneratedCapabilityRuntimeMetadata) []RuntimePolicyBinding {
	if len(definition.RuntimePolicyBindings) > 0 {
		return normalizeRuntimePolicyBindings(definition.RuntimePolicyBindings, capabilities)
	}
	return deriveRuntimePolicyBindings(definition.PermissionIntentBindings, capabilities)
}

func normalizeRuntimePolicyBindings(bindings []RuntimePolicyBinding, capabilities []GeneratedCapabilityRuntimeMetadata) []RuntimePolicyBinding {
	capabilityByID := map[string]GeneratedCapabilityRuntimeMetadata{}
	for _, capability := range capabilities {
		capabilityByID[capability.CapabilityID] = capability
	}
	result := make([]RuntimePolicyBinding, 0, len(bindings))
	for _, binding := range bindings {
		capabilityIDs := filterKnownCapabilities(binding.CapabilityIDs, capabilityByID)
		if len(capabilityIDs) == 0 {
			continue
		}
		binding.CapabilityIDs = capabilityIDs
		binding.RequiredScopes = requiredScopesForCapabilities(capabilityIDs, capabilityByID)
		if strings.TrimSpace(binding.Decision) == "" {
			binding.Decision = "allow"
		}
		if strings.TrimSpace(binding.PrincipalSelector.Claim) == "" && strings.TrimSpace(binding.ActorID) != "" {
			binding.PrincipalSelector = PrincipalSelector{Claim: "actor_id", Equals: binding.ActorID}
		}
		result = append(result, binding)
	}
	return result
}

func deriveRuntimePolicyBindings(bindings []PermissionIntentBinding, capabilities []GeneratedCapabilityRuntimeMetadata) []RuntimePolicyBinding {
	capabilityByID := map[string]GeneratedCapabilityRuntimeMetadata{}
	capabilitiesByService := map[string][]GeneratedCapabilityRuntimeMetadata{}
	for _, capability := range capabilities {
		capabilityByID[capability.CapabilityID] = capability
		capabilitiesByService[capability.ServiceID] = append(capabilitiesByService[capability.ServiceID], capability)
	}
	result := make([]RuntimePolicyBinding, 0, len(bindings))
	for _, binding := range bindings {
		capabilityIDs := filterKnownCapabilities(binding.TargetCapabilityIDs, capabilityByID)
		if len(capabilityIDs) == 0 {
			for _, serviceID := range binding.TargetServiceIDs {
				for _, capability := range capabilitiesByService[serviceID] {
					capabilityIDs = append(capabilityIDs, capability.CapabilityID)
				}
			}
			capabilityIDs = uniqueStrings(capabilityIDs)
		}
		if len(capabilityIDs) == 0 {
			continue
		}
		actorID := strings.TrimSpace(binding.ActorID)
		result = append(result, RuntimePolicyBinding{
			ID:                 fallbackString(binding.ID, "permission") + "-policy",
			SourcePermissionID: binding.ID,
			ActorID:            actorID,
			PrincipalSelector:  PrincipalSelector{Claim: "actor_id", Equals: actorID},
			BusinessArea:       binding.BusinessArea,
			BusinessAreaLabel:  binding.BusinessAreaLabel,
			ServiceIDs:         uniqueStrings(binding.TargetServiceIDs),
			CapabilityIDs:      capabilityIDs,
			RequiredScopes:     requiredScopesForCapabilities(capabilityIDs, capabilityByID),
			Decision:           policyDecisionForPermission(binding),
			BusinessRule:       binding.GovernedOutcome,
			EnforcementNotes:   binding.FormalizationStrategy,
		})
	}
	return result
}

func filterKnownCapabilities(values []string, capabilityByID map[string]GeneratedCapabilityRuntimeMetadata) []string {
	result := []string{}
	for _, value := range values {
		if _, ok := capabilityByID[value]; ok {
			result = append(result, value)
		}
	}
	return uniqueStrings(result)
}

func requiredScopesForCapabilities(capabilityIDs []string, capabilityByID map[string]GeneratedCapabilityRuntimeMetadata) []string {
	result := []string{}
	for _, capabilityID := range capabilityIDs {
		capability, ok := capabilityByID[capabilityID]
		if !ok {
			continue
		}
		result = append(result, capability.MinimumScope...)
	}
	return uniqueStrings(result)
}

func policyDecisionForPermission(binding PermissionIntentBinding) string {
	access := strings.TrimSpace(binding.AccessPosture)
	outcome := strings.TrimSpace(binding.GovernedOutcomeType)
	if access == "denied" || outcome == "deny_request" {
		return "deny"
	}
	if outcome == "clarification_required" {
		return "clarify"
	}
	if access == "approval_required" || outcome == "approval_required" || outcome == "approval_stop" {
		return "approval_required"
	}
	if access == "bounded" || access == "restricted" || outcome == "bounded_result" || outcome == "masked_or_restricted_result" {
		return "allow_with_limits"
	}
	return "allow"
}

func assertDefinition(definition *AnipServiceDefinition) error {
	if definition == nil {
		return fmt.Errorf("service definition is required")
	}
	bytes, err := json.Marshal(definition)
	if err != nil {
		return fmt.Errorf("encode service definition for validation: %w", err)
	}
	var payload map[string]any
	if err := json.Unmarshal(bytes, &payload); err != nil {
		return fmt.Errorf("decode service definition for validation: %w", err)
	}
	return definitionvalidation.ValidateServiceDefinition(payload)
}

func buildServiceMetadata(definition *AnipServiceDefinition) []GeneratedServiceMetadata {
	topologyByID := make(map[string]ServiceTopologyBinding, len(definition.ServiceTopologyBindings))
	for _, binding := range definition.ServiceTopologyBindings {
		topologyByID[strings.TrimSpace(binding.ServiceID)] = binding
	}

	serviceIDs := make([]string, 0)
	seen := make(map[string]struct{})
	for _, capability := range definition.CapabilityFormalizations {
		serviceID := strings.TrimSpace(capability.ServiceID)
		if serviceID == "" {
			continue
		}
		if _, ok := seen[serviceID]; ok {
			continue
		}
		seen[serviceID] = struct{}{}
		serviceIDs = append(serviceIDs, serviceID)
	}
	selectedServiceIDs := []string(nil)
	if definition.Generation != nil {
		selectedServiceIDs = definition.Generation.SelectedServiceIDs
	}
	for _, serviceID := range fallbackStrings(selectedServiceIDs, nil) {
		serviceID = strings.TrimSpace(serviceID)
		if serviceID == "" {
			continue
		}
		if _, ok := seen[serviceID]; ok {
			continue
		}
		seen[serviceID] = struct{}{}
		serviceIDs = append(serviceIDs, serviceID)
	}

	services := make([]GeneratedServiceMetadata, 0, len(serviceIDs))
	for _, serviceID := range serviceIDs {
		topology := topologyByID[serviceID]
		serviceName := strings.TrimSpace(topology.ServiceName)
		if serviceName == "" {
			serviceName = titleCase(strings.NewReplacer("-", " ", "_", " ").Replace(serviceID))
		}
		services = append(services, GeneratedServiceMetadata{
			ServiceID:               serviceID,
			ServiceName:             serviceName,
			SourceRole:              fallbackString(topology.SourceRole, "application_integration"),
			SourceCapabilities:      fallbackStrings(topology.SourceCapabilities, []string{}),
			FormalizedCapabilityIDs: fallbackStrings(topology.FormalizedCapabilityIDs, []string{}),
			OwnedConceptIDs:         fallbackStrings(topology.OwnedConceptIDs, []string{}),
		})
	}
	return services
}

func buildCapabilityMetadata(definition *AnipServiceDefinition, services []GeneratedServiceMetadata) []GeneratedCapabilityRuntimeMetadata {
	serviceNameByID := make(map[string]string, len(services))
	for _, service := range services {
		serviceNameByID[service.ServiceID] = service.ServiceName
	}
	capabilityByID := make(map[string]CapabilityFormalization, len(definition.CapabilityFormalizations))
	for _, capability := range definition.CapabilityFormalizations {
		capabilityByID[capability.CapabilityID] = capability
	}
	mappings := []IntegrationCapabilityMapping{}
	if definition.IntegrationFronting != nil {
		mappings = definition.IntegrationFronting.CapabilityMappings
	}
	mappingByCapability := make(map[string]IntegrationCapabilityMapping, len(mappings))
	for _, mapping := range mappings {
		mappingByCapability[mapping.CapabilityID] = mapping
	}

	capabilities := make([]GeneratedCapabilityRuntimeMetadata, 0, len(definition.CapabilityFormalizations))
	for _, capability := range definition.CapabilityFormalizations {
		mapping, hasMapping := mappingByCapability[capability.CapabilityID]
		requiredInputs := make([]CapabilityInputFormalization, 0)
		optionalInputs := make([]CapabilityInputFormalization, 0)
		for _, input := range capability.Inputs {
			if input.Required {
				requiredInputs = append(requiredInputs, input)
			} else {
				optionalInputs = append(optionalInputs, input)
			}
		}

		serviceName := serviceNameByID[capability.ServiceID]
		if strings.TrimSpace(serviceName) == "" {
			serviceName = titleCase(strings.NewReplacer("-", " ", "_", " ").Replace(capability.ServiceID))
		}
		executionPosture := capability.IntentType
		subjectKind := fallbackString(capability.SubjectKind, "record")
		contextType := fallbackString(capability.ContextType, "governed_request")
		outputIntent := fallbackString(capability.OutputIntent, capability.OutputShape)
		if outputIntent == "" {
			outputIntent = "governed_result"
		}
		kind := fallbackString(capability.Kind, "atomic")
		if capability.Composition != nil {
			kind = "composed"
		}
		backendInputMode := "implicit"
		if hasMapping && strings.TrimSpace(mapping.ExecutionPosture) != "" {
			executionPosture = mapping.ExecutionPosture
		}
		if hasMapping && strings.TrimSpace(mapping.SubjectKind) != "" {
			subjectKind = mapping.SubjectKind
		}
		if hasMapping && strings.TrimSpace(mapping.ContextType) != "" {
			contextType = mapping.ContextType
		}
		if hasMapping && strings.TrimSpace(mapping.OutputIntent) != "" {
			outputIntent = mapping.OutputIntent
		}
		if hasMapping && strings.TrimSpace(mapping.BackendInputMode) != "" {
			backendInputMode = mapping.BackendInputMode
		}

		outboundControls := map[string]any{}
		if hasMapping && mapping.OutboundControls != nil {
			outboundControls = mapping.OutboundControls
		}

		capabilities = append(capabilities, GeneratedCapabilityRuntimeMetadata{
			ServiceID:                     capability.ServiceID,
			ServiceName:                   serviceName,
			CapabilityID:                  capability.CapabilityID,
			Title:                         capability.Title,
			Summary:                       capability.Summary,
			Kind:                          kind,
			Composition:                   capability.Composition,
			GrantPolicy:                   capability.GrantPolicy,
			IntentType:                    capability.IntentType,
			OperationType:                 capability.OperationType,
			ExecutionPosture:              executionPosture,
			SideEffectLevel:               capability.SideEffectLevel,
			ImplementationFit:             capability.ImplementationFit,
			BusinessEffects:               capability.BusinessEffects,
			BackendOperation:              capability.BackendOperation,
			PathTemplate:                  capability.PathTemplate,
			OutputShape:                   capability.OutputShape,
			SubjectKind:                   subjectKind,
			ContextType:                   contextType,
			OutputIntent:                  outputIntent,
			MinimumScope:                  effectiveMinimumScope(capability, capabilityByID),
			RequiredInputs:                requiredInputs,
			OptionalInputs:                optionalInputs,
			SampleParameters:              buildSampleParameters(capability.Inputs),
			BackendInputMode:              backendInputMode,
			DerivedRequiredBackendInputs:  uniqueStrings(mapping.DerivedRequiredBackendInputs),
			DerivedOptionalBackendInputs:  uniqueStrings(mapping.DerivedOptionalBackendInputs),
			ExplicitRequiredBackendInputs: uniqueStrings(mapping.ExplicitRequiredBackendInputs),
			ExplicitOptionalBackendInputs: uniqueStrings(mapping.ExplicitOptionalBackendInputs),
			BackendBindings:               normalizeBackendBindings(hasMapping, mapping),
			Governance: GeneratedCapabilityGovernance{
				ApprovalRuleRefs:      uniqueStrings(mapping.ApprovalRuleRefs),
				DenialRuleRefs:        uniqueStrings(mapping.DenialRuleRefs),
				ClarificationRuleRefs: uniqueStrings(mapping.ClarificationRuleRefs),
				AuditRequired:         mapping.AuditRequired,
			},
			OutboundControls: outboundControls,
		})
	}
	return capabilities
}

func effectiveMinimumScope(capability CapabilityFormalization, capabilityByID map[string]CapabilityFormalization) []string {
	scope := fallbackStrings(capability.MinimumScope, []string{capability.CapabilityID})
	if capability.Composition == nil {
		return uniqueStrings(scope)
	}
	for _, step := range capability.Composition.Steps {
		child, ok := capabilityByID[step.Capability]
		if !ok {
			continue
		}
		scope = append(scope, fallbackStrings(child.MinimumScope, []string{child.CapabilityID})...)
	}
	return uniqueStrings(scope)
}

func normalizeBackendBindings(hasMapping bool, mapping IntegrationCapabilityMapping) []IntegrationBackendBinding {
	if !hasMapping {
		return []IntegrationBackendBinding{}
	}
	if len(mapping.BackendBindings) > 0 {
		bindings := make([]IntegrationBackendBinding, 0, len(mapping.BackendBindings))
		for _, binding := range mapping.BackendBindings {
			normalized := binding
			if strings.TrimSpace(normalized.BackendInputMode) == "" {
				normalized.BackendInputMode = fallbackString(mapping.BackendInputMode, "implicit")
			}
			if len(normalized.DerivedRequiredBackendInputs) == 0 {
				normalized.DerivedRequiredBackendInputs = uniqueStrings(mapping.DerivedRequiredBackendInputs)
			}
			if len(normalized.DerivedOptionalBackendInputs) == 0 {
				normalized.DerivedOptionalBackendInputs = uniqueStrings(mapping.DerivedOptionalBackendInputs)
			}
			if len(normalized.ExplicitRequiredBackendInputs) == 0 {
				normalized.ExplicitRequiredBackendInputs = uniqueStrings(mapping.ExplicitRequiredBackendInputs)
			}
			if len(normalized.ExplicitOptionalBackendInputs) == 0 {
				normalized.ExplicitOptionalBackendInputs = uniqueStrings(mapping.ExplicitOptionalBackendInputs)
			}
			normalized.Status = fallbackString(normalized.Status, "ready")
			normalized.StatusDetail = fallbackString(normalized.StatusDetail, "")
			normalized.MatchedDiscoveryRecordIDs = fallbackStrings(normalized.MatchedDiscoveryRecordIDs, []string{})
			bindings = append(bindings, normalized)
		}
		return bindings
	}

	return []IntegrationBackendBinding{{
		BackendKind:                   mapping.BackendKind,
		ConnectionRef:                 mapping.ConnectionRef,
		RawOperationRefs:              fallbackStrings(mapping.RawOperationRefs, []string{}),
		BackendInputMode:              fallbackString(mapping.BackendInputMode, "implicit"),
		DerivedRequiredBackendInputs:  uniqueStrings(mapping.DerivedRequiredBackendInputs),
		DerivedOptionalBackendInputs:  uniqueStrings(mapping.DerivedOptionalBackendInputs),
		ExplicitRequiredBackendInputs: uniqueStrings(mapping.ExplicitRequiredBackendInputs),
		ExplicitOptionalBackendInputs: uniqueStrings(mapping.ExplicitOptionalBackendInputs),
		MatchedDiscoveryRecordIDs:     []string{},
		Status:                        "ready",
		StatusDetail:                  "",
	}}
}

func buildSampleParameters(inputs []CapabilityInputFormalization) map[string]any {
	parameters := make(map[string]any, len(inputs))
	for _, input := range inputs {
		parameters[input.InputName] = sampleValueForInput(input)
	}
	return parameters
}

func sampleValueForInput(input CapabilityInputFormalization) any {
	if len(input.AllowedValues) > 0 {
		return input.AllowedValues[0]
	}
	if trimmed := strings.TrimSpace(input.DefaultValue); trimmed != "" {
		switch trimmed {
		case "true":
			return true
		case "false":
			return false
		}
		if number, ok := parseNumber(trimmed); ok {
			return number
		}
		return trimmed
	}

	if sample, ok := sampleValueForDeclaredFormat(input); ok {
		return sample
	}

	inputType := strings.ToLower(input.InputType)
	switch {
	case strings.Contains(inputType, "bool"):
		return false
	case strings.Contains(inputType, "int"), strings.Contains(inputType, "number"), strings.Contains(inputType, "float"):
		return 1
	case strings.Contains(inputType, "array"), strings.HasSuffix(inputType, "[]"):
		return []any{}
	case strings.Contains(inputType, "object"), strings.Contains(inputType, "json"):
		return map[string]any{}
	default:
		return input.InputName + "-value"
	}
}

func sampleValueForDeclaredFormat(input CapabilityInputFormalization) (any, bool) {
	format := strings.TrimSpace(input.InputFormat)
	switch format {
	case "business_quarter":
		return "2026-Q2", true
	case "date":
		return "2026-05-08", true
	case "date_time":
		return "2026-05-08T12:00:00Z", true
	case "email":
		return "user@example.com", true
	case "url":
		return "https://example.com", true
	case "uuid":
		return "00000000-0000-4000-8000-000000000000", true
	}

	pattern := strings.TrimSpace(input.ValidationPattern)
	switch pattern {
	case `^\d{4}-Q[1-4]$`, `^[0-9]{4}-Q[1-4]$`:
		return "2026-Q2", true
	case `^[1-9][0-9]*$`:
		return 25, true
	case `^[A-Z][A-Z0-9_]+$`, `^[A-Za-z][A-Za-z0-9_.-]*$`:
		return "PROJECT", true
	case `^[A-Z][A-Z0-9_]+-[0-9]+$`, `^[A-Za-z][A-Za-z0-9_.-]*-[0-9]+$`:
		return "PROJECT-123", true
	}

	lowerName := strings.ToLower(input.InputName)
	if strings.Contains(lowerName, "issue_key") || strings.Contains(lowerName, "ticket_key") {
		return "PROJECT-123", true
	}
	if strings.Contains(lowerName, "project_key") {
		return "PROJECT", true
	}
	return nil, false
}

func containsString(values []string, needle string) bool {
	for _, value := range values {
		if value == needle {
			return true
		}
	}
	return false
}
