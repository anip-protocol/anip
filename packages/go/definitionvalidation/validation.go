package definitionvalidation

import (
	"encoding/json"
	"fmt"
	"regexp"
	"strings"

	"github.com/anip-protocol/anip/packages/go/core"
)

var (
	inputPathPattern    = regexp.MustCompile(`^\$\.input(?:\.[A-Za-z_][A-Za-z0-9_]*)+$`)
	stepPathPattern     = regexp.MustCompile(`^\$\.steps\.([A-Za-z_][A-Za-z0-9_-]*)\.output(?:\.[A-Za-z_][A-Za-z0-9_]*)+$`)
	inputNamePattern    = regexp.MustCompile(`^[A-Za-z_][A-Za-z0-9_]*$`)
	serviceIDPattern    = regexp.MustCompile(`^[a-z][a-z0-9]*(?:[-_][a-z0-9]+)*$`)
	capabilityIDPattern = regexp.MustCompile(`^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$`)
	operationPattern    = regexp.MustCompile(`^[A-Za-z_][A-Za-z0-9_.:-]{0,127}$`)
	typeNamePattern     = regexp.MustCompile(`^[A-Za-z][A-Za-z0-9_]*(?:<\s*[A-Za-z][A-Za-z0-9_]*(?:\s*,\s*[A-Za-z][A-Za-z0-9_]*)*\s*>)?$`)
)

func ValidateServiceDefinition(definition map[string]any) error {
	if stringField(definition, "artifact_type") != "anip_service_definition" {
		return fmt.Errorf("service_definition.artifact_type must be anip_service_definition")
	}
	if stringField(definition, "contract_schema_version") != "anip-service-definition/v1" {
		return fmt.Errorf("service_definition.contract_schema_version must be anip-service-definition/v1")
	}
	identity := mapField(definition, "identity")
	if len(identity) == 0 || stringField(identity, "system_name") == "" {
		return fmt.Errorf("service_definition.identity.system_name is required")
	}
	topology := sliceField(definition, "service_topology_bindings")
	if len(topology) == 0 {
		return fmt.Errorf("service_definition.service_topology_bindings must contain at least one service")
	}
	serviceIDs := map[string]bool{}
	for index, item := range topology {
		service, ok := item.(map[string]any)
		if !ok {
			return fmt.Errorf("service_topology_bindings[%d] must be an object", index)
		}
		if _, exists := service["ownership_mode"]; exists {
			return fmt.Errorf("service_topology_bindings[%d].ownership_mode is not supported", index)
		}
		serviceID := stringField(service, "service_id")
		if serviceID == "" {
			return fmt.Errorf("service_topology_bindings[%d].service_id is required", index)
		}
		if !serviceIDPattern.MatchString(serviceID) {
			return fmt.Errorf("service_topology_bindings[%d].service_id is invalid", index)
		}
		if name := stringField(service, "service_name"); name != "" && !isSafeText(name) {
			return fmt.Errorf("service_topology_bindings[%d].service_name contains unsafe text", index)
		}
		if serviceIDs[serviceID] {
			return fmt.Errorf("service_topology_bindings[%d].service_id %q is duplicated", index, serviceID)
		}
		serviceIDs[serviceID] = true
	}

	capabilities := sliceField(definition, "capability_formalizations")
	if len(capabilities) == 0 {
		return fmt.Errorf("service_definition.capability_formalizations must contain at least one capability")
	}
	capabilityByID := map[string]map[string]any{}
	capabilityIndexByID := map[string]int{}
	for index, item := range capabilities {
		capability, ok := item.(map[string]any)
		if !ok {
			return fmt.Errorf("capability_formalizations[%d] must be an object", index)
		}
		capabilityID := stringField(capability, "capability_id")
		if capabilityID == "" {
			return fmt.Errorf("capability_formalizations[%d].capability_id is required", index)
		}
		if !capabilityIDPattern.MatchString(capabilityID) {
			return fmt.Errorf("capability_formalizations[%d].capability_id is invalid", index)
		}
		if _, exists := capabilityByID[capabilityID]; exists {
			return fmt.Errorf("capability_formalizations[%d].capability_id %q is duplicated", index, capabilityID)
		}
		capabilityByID[capabilityID] = capability
		capabilityIndexByID[capabilityID] = index
	}
	for index, item := range capabilities {
		capability := item.(map[string]any)
		if err := validateCapability(index, capability, serviceIDs, capabilityByID, capabilityIndexByID); err != nil {
			return err
		}
	}
	if integrationFronting := mapField(definition, "integration_fronting"); len(integrationFronting) > 0 {
		if err := validateIntegrationFronting(integrationFronting, serviceIDs, capabilityByID); err != nil {
			return err
		}
	}
	return nil
}

func validateCapability(index int, capability map[string]any, serviceIDs map[string]bool, capabilityByID map[string]map[string]any, capabilityIndexByID map[string]int) error {
	required := []string{
		"service_id",
		"capability_id",
		"title",
		"summary",
		"intent_type",
		"operation_type",
		"side_effect_level",
		"backend_operation",
		"path_template",
		"output_shape",
		"kind",
	}
	for _, field := range required {
		if stringField(capability, field) == "" {
			return fmt.Errorf("capability_formalizations[%d].%s is required", index, field)
		}
	}
	serviceID := stringField(capability, "service_id")
	if !serviceIDs[serviceID] {
		return fmt.Errorf("capability_formalizations[%d].service_id %q is not in service_topology_bindings", index, serviceID)
	}
	if title := stringField(capability, "title"); !isSafeText(title) {
		return fmt.Errorf("capability_formalizations[%d].title contains unsafe text", index)
	}
	if summary := stringField(capability, "summary"); !isSafeText(summary) {
		return fmt.Errorf("capability_formalizations[%d].summary contains unsafe text", index)
	}
	if backendOperation := stringField(capability, "backend_operation"); !operationPattern.MatchString(backendOperation) {
		return fmt.Errorf("capability_formalizations[%d].backend_operation is invalid", index)
	}
	if outputShape := stringField(capability, "output_shape"); !operationPattern.MatchString(outputShape) {
		return fmt.Errorf("capability_formalizations[%d].output_shape is invalid", index)
	}
	if err := validatePathTemplate(index, stringField(capability, "path_template")); err != nil {
		return err
	}
	inputs, ok := capability["inputs"].([]any)
	if !ok {
		return fmt.Errorf("capability_formalizations[%d].inputs must be an array", index)
	}
	if err := validateInputs(index, inputs); err != nil {
		return err
	}
	if effects, exists := capability["business_effects"]; exists && effects != nil {
		if err := ValidateKnownBusinessEffectsInPayload(fmt.Sprintf("capability_formalizations[%d]", index), map[string]any{"business_effects": effects}); err != nil {
			return err
		}
	}

	kind := stringField(capability, "kind")
	composition, hasComposition := capability["composition"]
	if kind != "atomic" && kind != "composed" {
		return fmt.Errorf("capability_formalizations[%d].kind must be atomic or composed", index)
	}
	if kind == "atomic" && hasComposition && composition != nil {
		return fmt.Errorf("capability_formalizations[%d].composition must be null/absent when kind is atomic", index)
	}
	if kind == "composed" {
		compositionMap, ok := composition.(map[string]any)
		if !ok || len(compositionMap) == 0 {
			return fmt.Errorf("capability_formalizations[%d].composition is required when kind is composed", index)
		}
		if err := validateComposition(index, capability, compositionMap, capabilityByID, capabilityIndexByID); err != nil {
			return err
		}
	}
	if policy, ok := capability["grant_policy"]; ok && policy != nil {
		policyMap, ok := policy.(map[string]any)
		if !ok {
			return fmt.Errorf("capability_formalizations[%d].grant_policy must be an object or null", index)
		}
		if err := validateGrantPolicy(index, policyMap); err != nil {
			return err
		}
	}
	return nil
}

func validateInputs(capabilityIndex int, inputs []any) error {
	seen := map[string]bool{}
	for inputIndex, item := range inputs {
		input, ok := item.(map[string]any)
		if !ok {
			return fmt.Errorf("capability_formalizations[%d].inputs[%d] must be an object", capabilityIndex, inputIndex)
		}
		name := stringField(input, "input_name")
		if name == "" {
			name = stringField(input, "name")
		}
		if name == "" || !inputNamePattern.MatchString(name) {
			return fmt.Errorf("capability_formalizations[%d].inputs[%d].input_name is invalid", capabilityIndex, inputIndex)
		}
		if seen[name] {
			return fmt.Errorf("capability_formalizations[%d].inputs[%d].input_name %q is duplicated", capabilityIndex, inputIndex, name)
		}
		seen[name] = true
		if inputType := stringField(input, "input_type"); inputType != "" && !typeNamePattern.MatchString(inputType) {
			return fmt.Errorf("capability_formalizations[%d].inputs[%d].input_type is invalid", capabilityIndex, inputIndex)
		}
		if summary := stringField(input, "summary"); summary != "" && !isSafeText(summary) {
			return fmt.Errorf("capability_formalizations[%d].inputs[%d].summary contains unsafe text", capabilityIndex, inputIndex)
		}
		if allowedValues, ok := input["allowed_values"]; ok && !stringSliceValue(allowedValues) {
			return fmt.Errorf("capability_formalizations[%d].inputs[%d].allowed_values must be strings", capabilityIndex, inputIndex)
		}
		if pattern := stringField(input, "validation_pattern"); pattern != "" {
			if _, err := regexp.Compile(pattern); err != nil {
				return fmt.Errorf("capability_formalizations[%d].inputs[%d].validation_pattern is invalid", capabilityIndex, inputIndex)
			}
		}
		if format := stringField(input, "input_format"); format != "" && !isAllowedInputFormat(format) {
			return fmt.Errorf("capability_formalizations[%d].inputs[%d].input_format is invalid", capabilityIndex, inputIndex)
		}
		if err := validateInputResolutionMetadata(capabilityIndex, inputIndex, input); err != nil {
			return err
		}
	}
	return nil
}

func validateInputResolutionMetadata(capabilityIndex int, inputIndex int, input map[string]any) error {
	prefix := fmt.Sprintf("capability_formalizations[%d].inputs[%d]", capabilityIndex, inputIndex)
	if _, exists := input["reference_catalog"]; exists {
		return fmt.Errorf("%s.reference_catalog is not supported; use catalog_ref", prefix)
	}
	if _, exists := input["reference_catalogs"]; exists {
		return fmt.Errorf("%s.reference_catalogs is not supported; use catalog_ref", prefix)
	}
	if semanticType := stringField(input, "semantic_type"); semanticType != "" && !inputNamePattern.MatchString(semanticType) {
		return fmt.Errorf("%s.semantic_type is invalid", prefix)
	}
	if catalogRef := stringField(input, "catalog_ref"); catalogRef != "" && !operationPattern.MatchString(catalogRef) {
		return fmt.Errorf("%s.catalog_ref is invalid", prefix)
	}
	if value, exists := input["entity_reference"]; exists {
		if _, ok := value.(bool); !ok {
			return fmt.Errorf("%s.entity_reference must be a boolean", prefix)
		}
	}
	rawResolution, exists := input["resolution"]
	if !exists || rawResolution == nil {
		return nil
	}
	resolutionMap, ok := rawResolution.(map[string]any)
	if !ok {
		return fmt.Errorf("%s.resolution must be an object", prefix)
	}
	if len(resolutionMap) == 0 {
		return fmt.Errorf("%s.resolution.mode is required", prefix)
	}
	resolutionBytes, err := json.Marshal(resolutionMap)
	if err != nil {
		return fmt.Errorf("%s.resolution is invalid: %v", prefix, err)
	}
	var resolution core.InputResolution
	if err := json.Unmarshal(resolutionBytes, &resolution); err != nil {
		return fmt.Errorf("%s.%v", prefix, err)
	}
	capabilityInput := &core.CapabilityInput{
		Name:          firstNonEmpty(stringField(input, "input_name"), stringField(input, "name")),
		Type:          firstNonEmpty(stringField(input, "input_type"), stringField(input, "type")),
		AllowedValues: stringSliceField(input, "allowed_values"),
		Resolution:    &resolution,
	}
	if defaultValue, exists := input["default_value"]; exists {
		capabilityInput.Default = defaultValue
	} else if defaultValue, exists := input["default"]; exists {
		capabilityInput.Default = defaultValue
	}
	if err := core.ValidateCapabilityInput(capabilityInput); err != nil {
		return fmt.Errorf("%s.%v", prefix, err)
	}
	return nil
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if value != "" {
			return value
		}
	}
	return ""
}

func isAllowedInputFormat(format string) bool {
	switch format {
	case "business_quarter", "date", "date_time", "email", "url", "uuid":
		return true
	default:
		return false
	}
}

func validateComposition(index int, parent map[string]any, composition map[string]any, capabilityByID map[string]map[string]any, capabilityIndexByID map[string]int) error {
	if boundary := stringField(composition, "authority_boundary"); boundary != "same_service" {
		return fmt.Errorf("capability_formalizations[%d].composition.authority_boundary must be same_service", index)
	}
	steps := sliceField(composition, "steps")
	if len(steps) == 0 {
		return fmt.Errorf("capability_formalizations[%d].composition.steps must contain at least one step", index)
	}
	inputMapping, ok := composition["input_mapping"].(map[string]any)
	if !ok {
		return fmt.Errorf("capability_formalizations[%d].composition.input_mapping must be an object", index)
	}
	outputMapping, ok := composition["output_mapping"].(map[string]any)
	if !ok {
		return fmt.Errorf("capability_formalizations[%d].composition.output_mapping must be an object", index)
	}
	failurePolicy, ok := composition["failure_policy"].(map[string]any)
	if !ok {
		return fmt.Errorf("capability_formalizations[%d].composition.failure_policy must be an object", index)
	}
	for _, field := range []string{"child_clarification", "child_denial", "child_approval_required", "child_error"} {
		value := stringField(failurePolicy, field)
		if value == "" {
			return fmt.Errorf("capability_formalizations[%d].composition.failure_policy.%s is required", index, field)
		}
		if value != "propagate" && value != "fail_parent" {
			return fmt.Errorf("capability_formalizations[%d].composition.failure_policy.%s must be propagate or fail_parent", index, field)
		}
	}
	if _, ok := composition["audit_policy"].(map[string]any); !ok {
		return fmt.Errorf("capability_formalizations[%d].composition.audit_policy must be an object", index)
	}

	stepIndexByID := map[string]int{}
	emptySources := 0
	for stepIndex, item := range steps {
		step, ok := item.(map[string]any)
		if !ok {
			return fmt.Errorf("capability_formalizations[%d].composition.steps[%d] must be an object", index, stepIndex)
		}
		stepID := stringField(step, "id")
		stepCapability := stringField(step, "capability")
		if stepID == "" || stepCapability == "" {
			return fmt.Errorf("capability_formalizations[%d].composition.steps[%d] requires id and capability", index, stepIndex)
		}
		if !inputNamePattern.MatchString(stepID) {
			return fmt.Errorf("capability_formalizations[%d].composition.steps[%d].id is invalid", index, stepIndex)
		}
		if _, exists := stepIndexByID[stepID]; exists {
			return fmt.Errorf("capability_formalizations[%d].composition.steps[%d].id is duplicated", index, stepIndex)
		}
		stepIndexByID[stepID] = stepIndex
		if boolField(step, "empty_result_source") {
			emptySources++
		}
		if stepCapability == stringField(parent, "capability_id") {
			return fmt.Errorf("capability_formalizations[%d].composition.steps[%d].capability cannot self-reference the composed capability", index, stepIndex)
		}
		child, ok := capabilityByID[stepCapability]
		if !ok {
			return fmt.Errorf("capability_formalizations[%d].composition.steps[%d].capability %q is not defined", index, stepIndex, stepCapability)
		}
		if stringField(child, "service_id") != stringField(parent, "service_id") {
			return fmt.Errorf("capability_formalizations[%d].composition.steps[%d].capability %q is owned by service %q; same_service composition requires service %q", index, stepIndex, stepCapability, stringField(child, "service_id"), stringField(parent, "service_id"))
		}
		if stringField(child, "kind") != "atomic" {
			return fmt.Errorf("capability_formalizations[%d].composition.steps[%d].capability %q must be atomic; capability_formalizations[%d].kind is %q", index, stepIndex, stepCapability, capabilityIndexByID[stepCapability], stringField(child, "kind"))
		}
		childInputs := sliceField(child, "inputs")
		for inputIndex, item := range childInputs {
			input, ok := item.(map[string]any)
			if !ok {
				return fmt.Errorf("capability_formalizations[%d].inputs[%d] must be an object", capabilityIndexByID[stepCapability], inputIndex)
			}
			inputName := stringField(input, "input_name")
			if inputName == "" {
				inputName = stringField(input, "name")
			}
			required, _ := input["required"].(bool)
			if required {
				stepMapping, ok := inputMapping[stepID].(map[string]any)
				if !ok || strings.TrimSpace(stringField(stepMapping, inputName)) == "" {
					return fmt.Errorf("capability_formalizations[%d].composition.input_mapping[%q].%s is required for child capability %q", index, stepID, inputName, stepCapability)
				}
			}
		}
	}
	if emptySources > 1 {
		return fmt.Errorf("capability_formalizations[%d].composition.steps may contain at most one empty_result_source", index)
	}
	if emptySources == 1 && stringField(composition, "empty_result_policy") == "" {
		return fmt.Errorf("capability_formalizations[%d].composition.empty_result_policy is required when a step has empty_result_source", index)
	}
	if stringField(composition, "empty_result_policy") == "return_success_no_results" {
		output, ok := composition["empty_result_output"].(map[string]any)
		if !ok || len(output) == 0 {
			return fmt.Errorf("capability_formalizations[%d].composition.empty_result_output is required when empty_result_policy is return_success_no_results", index)
		}
	}

	for stepID, mappingValue := range inputMapping {
		stepPosition, ok := stepIndexByID[stepID]
		if !ok {
			return fmt.Errorf("capability_formalizations[%d].composition.input_mapping key %q is not a declared step", index, stepID)
		}
		mapping, ok := mappingValue.(map[string]any)
		if !ok {
			return fmt.Errorf("capability_formalizations[%d].composition.input_mapping[%q] must be an object", index, stepID)
		}
		for inputName, pathValue := range mapping {
			path, ok := pathValue.(string)
			if !ok {
				return fmt.Errorf("capability_formalizations[%d].composition.input_mapping[%q].%s must be a JSONPath string", index, stepID, inputName)
			}
			refStep, hasRef, err := parsePath(path)
			if err != nil {
				return fmt.Errorf("capability_formalizations[%d].composition.input_mapping[%q].%s contains malformed JSONPath %q", index, stepID, inputName, path)
			}
			refPosition, exists := stepIndexByID[refStep]
			if hasRef && !exists {
				return fmt.Errorf("capability_formalizations[%d].composition.input_mapping[%q].%s references unknown step %q", index, stepID, inputName, refStep)
			}
			if hasRef && refPosition >= stepPosition {
				return fmt.Errorf("capability_formalizations[%d].composition.input_mapping[%q].%s forward-references step %q", index, stepID, inputName, refStep)
			}
		}
	}
	if len(outputMapping) == 0 {
		return fmt.Errorf("capability_formalizations[%d].composition.output_mapping must contain at least one field", index)
	}
	for field, pathValue := range outputMapping {
		if strings.TrimSpace(field) == "" {
			return fmt.Errorf("capability_formalizations[%d].composition.output_mapping field name is required", index)
		}
		path, ok := pathValue.(string)
		if !ok {
			return fmt.Errorf("capability_formalizations[%d].composition.output_mapping.%s must be a JSONPath string", index, field)
		}
		refStep, hasRef, err := parsePath(path)
		if err != nil {
			return fmt.Errorf("capability_formalizations[%d].composition.output_mapping.%s contains malformed JSONPath %q", index, field, path)
		}
		if hasRef {
			if _, ok := stepIndexByID[refStep]; !ok {
				return fmt.Errorf("capability_formalizations[%d].composition.output_mapping.%s references unknown step %q", index, field, refStep)
			}
		}
	}
	return nil
}

func parsePath(path string) (string, bool, error) {
	if inputPathPattern.MatchString(path) {
		return "", false, nil
	}
	matches := stepPathPattern.FindStringSubmatch(path)
	if len(matches) == 2 {
		return matches[1], true, nil
	}
	return "", false, fmt.Errorf("malformed JSONPath")
}

func validateGrantPolicy(index int, policy map[string]any) error {
	allowed := stringSliceField(policy, "allowed_grant_types")
	if len(allowed) == 0 {
		return fmt.Errorf("capability_formalizations[%d].grant_policy.allowed_grant_types must be non-empty strings", index)
	}
	defaultGrantType := stringField(policy, "default_grant_type")
	if defaultGrantType != "one_time" && defaultGrantType != "session_bound" {
		return fmt.Errorf("capability_formalizations[%d].grant_policy.default_grant_type is invalid", index)
	}
	foundDefault := false
	for _, value := range allowed {
		if value != "one_time" && value != "session_bound" {
			return fmt.Errorf("capability_formalizations[%d].grant_policy.allowed_grant_types contains invalid value", index)
		}
		if value == defaultGrantType {
			foundDefault = true
		}
	}
	if !foundDefault {
		return fmt.Errorf("capability_formalizations[%d].grant_policy.default_grant_type must appear in allowed_grant_types", index)
	}
	if !positiveIntegerField(policy, "expires_in_seconds") || !positiveIntegerField(policy, "max_uses") {
		return fmt.Errorf("capability_formalizations[%d].grant_policy expires_in_seconds and max_uses must be positive integers", index)
	}
	return nil
}

func validateIntegrationFronting(fronting map[string]any, serviceIDs map[string]bool, capabilityByID map[string]map[string]any) error {
	mappings := sliceField(fronting, "capability_mappings")
	if len(mappings) == 0 {
		return nil
	}
	seen := map[string]bool{}
	for index, item := range mappings {
		mapping, ok := item.(map[string]any)
		if !ok {
			return fmt.Errorf("integration_fronting.capability_mappings[%d] must be an object", index)
		}
		capabilityID := stringField(mapping, "capability_id")
		if capabilityID == "" || !capabilityIDPattern.MatchString(capabilityID) {
			return fmt.Errorf("integration_fronting.capability_mappings[%d].capability_id is invalid", index)
		}
		if seen[capabilityID] {
			return fmt.Errorf("integration_fronting.capability_mappings[%d].capability_id %q is duplicated", index, capabilityID)
		}
		seen[capabilityID] = true
		capability, ok := capabilityByID[capabilityID]
		if !ok {
			return fmt.Errorf("integration_fronting.capability_mappings[%d].capability_id %q is not a formalized capability", index, capabilityID)
		}
		serviceID := stringField(mapping, "service_id")
		if serviceID == "" || !serviceIDs[serviceID] {
			return fmt.Errorf("integration_fronting.capability_mappings[%d].service_id is not in service_topology_bindings", index)
		}
		if stringField(capability, "service_id") != serviceID {
			return fmt.Errorf("integration_fronting.capability_mappings[%d].service_id must match formalized capability owner %q", index, stringField(capability, "service_id"))
		}
		if title := stringField(mapping, "title"); title != "" && !isSafeText(title) {
			return fmt.Errorf("integration_fronting.capability_mappings[%d].title contains unsafe text", index)
		}
		if intent := stringField(mapping, "intent"); intent != "" && !isSafeText(intent) {
			return fmt.Errorf("integration_fronting.capability_mappings[%d].intent contains unsafe text", index)
		}
		if err := validateIntegrationBackendBindings(index, mapping); err != nil {
			return err
		}
		for _, field := range []string{"required_inputs", "optional_inputs", "approval_rule_refs", "denial_rule_refs", "clarification_rule_refs"} {
			if value, exists := mapping[field]; exists && !stringSliceValue(value) {
				return fmt.Errorf("integration_fronting.capability_mappings[%d].%s must be strings", index, field)
			}
		}
	}
	return nil
}

func validateIntegrationBackendBindings(mappingIndex int, mapping map[string]any) error {
	bindings := sliceField(mapping, "backend_bindings")
	if len(bindings) == 0 {
		return validateIntegrationBackendBinding(mappingIndex, -1, mapping)
	}
	for bindingIndex, item := range bindings {
		binding, ok := item.(map[string]any)
		if !ok {
			return fmt.Errorf("integration_fronting.capability_mappings[%d].backend_bindings[%d] must be an object", mappingIndex, bindingIndex)
		}
		if err := validateIntegrationBackendBinding(mappingIndex, bindingIndex, binding); err != nil {
			return err
		}
	}
	return nil
}

func validateIntegrationBackendBinding(mappingIndex int, bindingIndex int, binding map[string]any) error {
	prefix := fmt.Sprintf("integration_fronting.capability_mappings[%d]", mappingIndex)
	if bindingIndex >= 0 {
		prefix = fmt.Sprintf("%s.backend_bindings[%d]", prefix, bindingIndex)
	}
	backendKind := stringField(binding, "backend_kind")
	if !isAllowedBackendKind(backendKind) {
		return fmt.Errorf("%s.backend_kind is invalid", prefix)
	}
	connectionRef := stringField(binding, "connection_ref")
	if connectionRef == "" || !operationPattern.MatchString(connectionRef) {
		return fmt.Errorf("%s.connection_ref is invalid", prefix)
	}
	rawOps := stringSliceField(binding, "raw_operation_refs")
	if len(rawOps) == 0 {
		return fmt.Errorf("%s.raw_operation_refs must contain at least one raw backend operation", prefix)
	}
	for _, operation := range rawOps {
		if !operationPattern.MatchString(operation) {
			return fmt.Errorf("%s.raw_operation_refs contains invalid operation", prefix)
		}
	}
	if mode := stringField(binding, "backend_input_mode"); mode != "" && mode != "implicit" && mode != "hybrid" && mode != "explicit" {
		return fmt.Errorf("%s.backend_input_mode is invalid", prefix)
	}
	for _, field := range []string{
		"derived_required_backend_inputs",
		"derived_optional_backend_inputs",
		"explicit_required_backend_inputs",
		"explicit_optional_backend_inputs",
		"matched_discovery_record_ids",
	} {
		if value, exists := binding[field]; exists && !stringSliceValue(value) {
			return fmt.Errorf("%s.%s must be strings", prefix, field)
		}
	}
	return nil
}

func isAllowedBackendKind(value string) bool {
	switch value {
	case "native_api", "mcp", "database", "hybrid":
		return true
	default:
		return false
	}
}

func validatePathTemplate(index int, path string) error {
	if path == "" {
		return fmt.Errorf("capability_formalizations[%d].path_template is required", index)
	}
	if len(path) > 256 || strings.Contains(path, "\\") || strings.Contains(path, "..") || strings.Contains(path, "//") {
		return fmt.Errorf("capability_formalizations[%d].path_template is invalid", index)
	}
	if !strings.HasPrefix(path, "/") {
		return fmt.Errorf("capability_formalizations[%d].path_template must start with /", index)
	}
	if !isSafeText(path) {
		return fmt.Errorf("capability_formalizations[%d].path_template contains unsafe text", index)
	}
	for _, segment := range strings.Split(path, "/") {
		if segment == "" {
			continue
		}
		if strings.HasPrefix(segment, "{") || strings.HasSuffix(segment, "}") {
			if !(strings.HasPrefix(segment, "{") && strings.HasSuffix(segment, "}") && len(segment) > 2) {
				return fmt.Errorf("capability_formalizations[%d].path_template contains malformed parameter", index)
			}
			name := strings.TrimSuffix(strings.TrimPrefix(segment, "{"), "}")
			if !inputNamePattern.MatchString(name) {
				return fmt.Errorf("capability_formalizations[%d].path_template contains invalid parameter", index)
			}
			continue
		}
		for _, r := range segment {
			if (r >= 'a' && r <= 'z') || (r >= 'A' && r <= 'Z') || (r >= '0' && r <= '9') || r == '-' || r == '_' || r == '.' {
				continue
			}
			return fmt.Errorf("capability_formalizations[%d].path_template contains invalid character", index)
		}
	}
	return nil
}

func isSafeText(value string) bool {
	if value == "" || len(value) > 8192 {
		return false
	}
	for _, r := range value {
		if r == '\t' || r == '\n' || r == '\r' {
			continue
		}
		if r < 0x20 || r == 0x7f {
			return false
		}
	}
	return true
}

func stringField(payload map[string]any, key string) string {
	value, ok := payload[key].(string)
	if !ok {
		return ""
	}
	return strings.TrimSpace(value)
}

func boolField(payload map[string]any, key string) bool {
	value, ok := payload[key].(bool)
	return ok && value
}

func mapField(payload map[string]any, key string) map[string]any {
	value, ok := payload[key].(map[string]any)
	if !ok {
		return nil
	}
	return value
}

func sliceField(payload map[string]any, key string) []any {
	value, ok := payload[key].([]any)
	if !ok {
		return nil
	}
	return value
}

func stringSliceField(payload map[string]any, key string) []string {
	values, ok := payload[key].([]any)
	if !ok {
		return nil
	}
	result := make([]string, 0, len(values))
	for _, value := range values {
		text, ok := value.(string)
		if !ok || strings.TrimSpace(text) == "" {
			return nil
		}
		result = append(result, strings.TrimSpace(text))
	}
	return result
}

func stringSliceValue(value any) bool {
	values, ok := value.([]any)
	if !ok {
		return false
	}
	for _, item := range values {
		text, ok := item.(string)
		if !ok || strings.TrimSpace(text) == "" {
			return false
		}
	}
	return true
}

func positiveIntegerField(payload map[string]any, key string) bool {
	switch value := payload[key].(type) {
	case int:
		return value > 0
	case int64:
		return value > 0
	case float64:
		return value > 0 && value == float64(int64(value))
	default:
		return false
	}
}
