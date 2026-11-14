package definitionvalidation

import (
	"encoding/json"
	"fmt"
	"slices"
	"strings"
)

// A value a backend adapter needs comes from exactly one of two places: the
// caller, as a declared input of the capability, or the service itself. The
// generated adapter reads every backend input from the invocation parameters,
// and a runtime refuses parameters a capability does not declare (SPEC.md
// §4.1). So every backend input must be a declared input:
//
//   - An explicit backend input (explicit_required_backend_inputs and
//     explicit_optional_backend_inputs, used in explicit and hybrid mode) is a
//     declared input. When the capability does not list it in inputs, the
//     generator declares it, required or optional to match the list it is in.
//     When the capability does list it, required must match.
//   - A derived backend input (derived_required_backend_inputs and
//     derived_optional_backend_inputs, used in implicit and hybrid mode) comes
//     from backend discovery. It must be a declared input; otherwise it has
//     no source. A required one declared optional needs a default_value the
//     service applies, or it has no source when the caller omits it.
//
// The service definition has no way to say that a value comes from service
// configuration or the caller's principal; a backend adapter that needs such
// a value reads it itself and does not list it as a backend input.

// backendInputContract is the backend input contract of one binding, as the
// generated adapter computes it (effectiveBackendInputContract).
type backendInputContract struct {
	required []string
	optional []string
	explicit map[string]string // name -> the explicit list that names it
}

// mappingBackendInputContracts returns the contract of each backend binding
// of an integration_fronting capability mapping. A mapping without
// backend_bindings is its own single binding, and a binding inherits each
// list it leaves empty from the mapping, as the generator normalizes them.
func mappingBackendInputContracts(mapping map[string]any) []backendInputContract {
	bindings := []map[string]any{}
	for _, item := range sliceField(mapping, "backend_bindings") {
		if binding, ok := item.(map[string]any); ok {
			bindings = append(bindings, binding)
		}
	}
	if len(bindings) == 0 {
		bindings = []map[string]any{mapping}
	}
	contracts := make([]backendInputContract, 0, len(bindings))
	for _, binding := range bindings {
		list := func(field string) []string {
			if values := stringSliceField(binding, field); len(values) > 0 {
				return values
			}
			return stringSliceField(mapping, field)
		}
		mode := firstNonEmpty(stringField(binding, "backend_input_mode"), stringField(mapping, "backend_input_mode"), "implicit")
		contract := backendInputContract{explicit: map[string]string{}}
		var required, optional []string
		switch mode {
		case "explicit":
			required = list("explicit_required_backend_inputs")
			optional = list("explicit_optional_backend_inputs")
		case "hybrid":
			required = append(list("derived_required_backend_inputs"), list("explicit_required_backend_inputs")...)
			optional = append(list("derived_optional_backend_inputs"), list("explicit_optional_backend_inputs")...)
		default:
			required = list("derived_required_backend_inputs")
			optional = list("derived_optional_backend_inputs")
		}
		if mode == "explicit" || mode == "hybrid" {
			for _, name := range list("explicit_optional_backend_inputs") {
				contract.explicit[name] = "explicit_optional_backend_inputs"
			}
			for _, name := range list("explicit_required_backend_inputs") {
				contract.explicit[name] = "explicit_required_backend_inputs"
			}
		}
		contract.required = uniqueNames(required)
		for _, name := range uniqueNames(optional) {
			if !slices.Contains(contract.required, name) {
				contract.optional = append(contract.optional, name)
			}
		}
		contracts = append(contracts, contract)
	}
	return contracts
}

// backendInputSet merges the contracts of every binding: a deployment selects
// one binding, so the capability must accept what any of them needs. A name
// is required when any binding requires it.
type backendInputSet struct {
	names    []string
	required map[string]bool
	explicit map[string]string
}

func mappingBackendInputSet(mapping map[string]any) backendInputSet {
	set := backendInputSet{required: map[string]bool{}, explicit: map[string]string{}}
	add := func(name string) {
		if !slices.Contains(set.names, name) {
			set.names = append(set.names, name)
		}
	}
	contracts := mappingBackendInputContracts(mapping)
	for _, contract := range contracts {
		for _, name := range contract.required {
			add(name)
			set.required[name] = true
		}
	}
	for _, contract := range contracts {
		for _, name := range contract.optional {
			add(name)
		}
		for name, list := range contract.explicit {
			if set.explicit[name] != "explicit_required_backend_inputs" {
				set.explicit[name] = list
			}
		}
	}
	return set
}

func uniqueNames(values []string) []string {
	result := []string{}
	for _, value := range values {
		if value != "" && !slices.Contains(result, value) {
			result = append(result, value)
		}
	}
	return result
}

func declaredInputsByName(capability map[string]any) map[string]map[string]any {
	declared := map[string]map[string]any{}
	for _, item := range sliceField(capability, "inputs") {
		if input, ok := item.(map[string]any); ok {
			if name := declaredInputName(input); name != "" {
				declared[name] = input
			}
		}
	}
	return declared
}

// declaredRequired applies the SPEC.md §4.1 default: required is true unless
// the declaration says false.
func declaredRequired(input map[string]any) bool {
	required, stated := input["required"].(bool)
	return !stated || required
}

// serviceAppliesDefault reports whether a generated service fills the input
// from its default_value when the caller omits it.
func serviceAppliesDefault(input map[string]any) bool {
	if resolution, ok := input["resolution"].(map[string]any); ok && stringField(resolution, "on_missing") == "omit" {
		return false
	}
	for _, key := range []string{"default_value", "default"} {
		switch value := input[key].(type) {
		case nil:
		case string:
			if strings.TrimSpace(value) != "" {
				return true
			}
		default:
			return true
		}
	}
	return false
}

// undeclaredExplicitBackendInputs returns, for each capability, the explicit
// backend inputs it does not declare, in contract order, with the required
// flag the generator declares them with.
func undeclaredExplicitBackendInputs(definition map[string]any, capabilityByID map[string]map[string]any) map[string][]map[string]any {
	result := map[string][]map[string]any{}
	fronting := mapField(definition, "integration_fronting")
	for _, item := range sliceField(fronting, "capability_mappings") {
		mapping, ok := item.(map[string]any)
		if !ok {
			continue
		}
		capabilityID := stringField(mapping, "capability_id")
		capability, ok := capabilityByID[capabilityID]
		if !ok {
			continue
		}
		declared := declaredInputsByName(capability)
		set := mappingBackendInputSet(mapping)
		for _, name := range set.names {
			if _, isExplicit := set.explicit[name]; !isExplicit || declared[name] != nil || !inputNamePattern.MatchString(name) {
				continue
			}
			if slices.ContainsFunc(result[capabilityID], func(input map[string]any) bool { return input["input_name"] == name }) {
				continue
			}
			summary := "Accepted by the backend adapter (explicit backend input)."
			if set.required[name] {
				summary = "Required by the backend adapter (explicit backend input)."
			}
			result[capabilityID] = append(result[capabilityID], map[string]any{
				"input_name": name,
				"input_type": "string",
				"required":   set.required[name],
				"summary":    summary,
			})
		}
	}
	return result
}

func capabilitiesByID(definition map[string]any) map[string]map[string]any {
	result := map[string]map[string]any{}
	for _, item := range sliceField(definition, "capability_formalizations") {
		if capability, ok := item.(map[string]any); ok {
			if id := stringField(capability, "capability_id"); id != "" {
				if _, exists := result[id]; !exists {
					result[id] = capability
				}
			}
		}
	}
	return result
}

// UndeclaredExplicitBackendInputs returns, for each capability ID, the input
// declarations DeclareExplicitBackendInputs appends to that capability: each
// has input_name, input_type ("string", the generators' default), required
// and summary.
func UndeclaredExplicitBackendInputs(definition map[string]any) map[string][]map[string]any {
	return undeclaredExplicitBackendInputs(definition, capabilitiesByID(definition))
}

// DeclareExplicitBackendInputs returns a copy of a service definition in
// which every explicit backend input a capability does not declare is
// appended to that capability's inputs, required or optional to match the
// explicit list that names it. Generators build from this copy, so the
// manifest a generated service serves declares every input its backend
// adapter reads. The argument is not modified, and applying the function to
// its own result changes nothing.
func DeclareExplicitBackendInputs(definition map[string]any) map[string]any {
	copied := cloneDefinition(definition)
	additions := undeclaredExplicitBackendInputs(copied, capabilitiesByID(copied))
	if len(additions) == 0 {
		return copied
	}
	for _, item := range sliceField(copied, "capability_formalizations") {
		capability, ok := item.(map[string]any)
		if !ok {
			continue
		}
		extra := additions[stringField(capability, "capability_id")]
		if len(extra) == 0 {
			continue
		}
		inputs := append([]any{}, sliceField(capability, "inputs")...)
		for _, input := range extra {
			inputs = append(inputs, input)
		}
		capability["inputs"] = inputs
	}
	return copied
}

func cloneDefinition(definition map[string]any) map[string]any {
	data, err := json.Marshal(definition)
	if err != nil {
		panic(fmt.Sprintf("service definition is not JSON: %v", err))
	}
	var copied map[string]any
	if err := json.Unmarshal(data, &copied); err != nil {
		panic(fmt.Sprintf("service definition is not JSON: %v", err))
	}
	return copied
}

// validateBackendInputSources refuses a capability mapping that leaves a
// backend input without a source, or whose explicit lists disagree with the
// capability's declared inputs.
func validateBackendInputSources(mappingIndex int, mapping map[string]any, capability map[string]any) error {
	prefix := fmt.Sprintf("integration_fronting.capability_mappings[%d]", mappingIndex)
	capabilityID := stringField(capability, "capability_id")
	declared := declaredInputsByName(capability)
	set := mappingBackendInputSet(mapping)
	for _, name := range set.names {
		input := declared[name]
		if list, isExplicit := set.explicit[name]; isExplicit {
			if input == nil {
				continue // the generator declares it
			}
			if required := declaredRequired(input); required != set.required[name] {
				state := "optional"
				if required {
					state = "required"
				}
				return fmt.Errorf("%s: backend input %q is in %s, but capability %q declares it %s; required must match", prefix, name, list, capabilityID, state)
			}
			continue
		}
		if input == nil {
			return fmt.Errorf("%s: backend input %q has no source: capability %q does not declare it as an input, and a caller cannot send an undeclared parameter; declare it as an input, or list it in explicit_required_backend_inputs or explicit_optional_backend_inputs", prefix, name, capabilityID)
		}
		if set.required[name] && !declaredRequired(input) && !serviceAppliesDefault(input) {
			return fmt.Errorf("%s: backend input %q has no source when the caller omits it: the backend requires it, but capability %q declares it optional without a default_value; declare it required or give it a default_value", prefix, name, capabilityID)
		}
	}
	return nil
}
