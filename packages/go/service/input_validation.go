package service

import (
	"encoding/json"
	"math"
	"math/big"
	"reflect"
	"strconv"
	"strings"

	"github.com/anip-protocol/anip/packages/go/core"
)

// primitiveInputTypes are the declared input types the runtime checks at
// invocation (SPEC.md §4.1). The match is exact and case-sensitive; any other
// type name (airport_code, date, a domain type) describes the value to the
// agent and is left to the handler.
var primitiveInputTypes = map[string]bool{
	"string":  true,
	"integer": true,
	"number":  true,
	"boolean": true,
	"array":   true,
	"object":  true,
}

// validateDeclaredInputs implements SPEC.md §6.3 "Parameter Validation": it
// checks the parameters, exactly as the caller sent them, against the
// capability's declared inputs. It returns nil when the call may proceed and
// the invalid_parameters failure otherwise.
//
// Missing inputs are reported first, then undeclared parameters, then values
// of the wrong type. The check does not apply defaults (a declared default
// does not satisfy required) and does not enforce allowed_values or the
// resolution block. params is never modified.
//
// A required input whose resolution block sets on_missing (§4.10) is not
// reported as missing: the declaration already says what happens when the
// value is absent, and the handler answers through that path. A value that
// is supplied for such an input is type-checked like any other.
func validateDeclaredInputs(capName string, decl *core.CapabilityDeclaration, params map[string]any) *core.ANIPError {
	var missing []string
	for _, input := range decl.Inputs {
		if !input.MustBeSupplied() {
			continue
		}
		if value, ok := params[input.Name]; !ok || isJSONNull(value) {
			missing = append(missing, input.Name)
		}
	}
	if len(missing) > 0 {
		return invalidParametersError(capName + " is missing required input(s): " + strings.Join(missing, ", "))
	}

	// Every key must name a declared input, whatever its value. The names
	// are listed as RFC 8785 sorts member names (§4.7).
	declared := make(map[string]bool, len(decl.Inputs))
	for _, input := range decl.Inputs {
		declared[input.Name] = true
	}
	var undeclared []string
	for name := range params {
		if !declared[name] {
			undeclared = append(undeclared, name)
		}
	}
	if len(undeclared) > 0 {
		sortByUTF16CodeUnits(undeclared)
		return invalidParametersError(capName + " has undeclared parameter(s): " + strings.Join(undeclared, ", "))
	}

	var wrong []string
	for _, input := range decl.Inputs {
		value, ok := params[input.Name]
		if !ok || isJSONNull(value) {
			continue
		}
		if !primitiveInputTypes[input.Type] {
			continue
		}
		received, integral := jsonTypeOf(value)
		var accepted bool
		switch input.Type {
		case "integer":
			accepted = received == "number" && integral
		default:
			accepted = received == input.Type
		}
		if !accepted {
			wrong = append(wrong, "'"+input.Name+"' must be "+input.Type+", got "+received)
		}
	}
	if len(wrong) > 0 {
		return invalidParametersError(capName + " has invalid input(s): " + strings.Join(wrong, "; "))
	}
	return nil
}

// ParametersShapeError checks the `parameters` member of an invocation
// request body. SPEC.md §6.3: absent or null parameters are the empty object;
// a value of any other JSON type that is not an object does not match the
// request schema and is refused with invalid_parameters, like a body that is
// not JSON. raw is the decoded member (nil when absent or null).
func ParametersShapeError(capName string, raw any) *core.ANIPError {
	if raw == nil {
		return nil
	}
	received, _ := jsonTypeOf(raw)
	if received == "object" {
		return nil
	}
	return invalidParametersError(capName + " parameters must be an object, got " + received)
}

// invalidParametersError builds the failure of SPEC.md §6.3: the caller
// corrects the parameters against the manifest and sends a new request.
func invalidParametersError(detail string) *core.ANIPError {
	return &core.ANIPError{
		ErrorType:  core.FailureInvalidParameters,
		Detail:     detail,
		Resolution: core.InvalidParametersResolution("parameters that match the capability's declared inputs"),
		Retry:      false,
	}
}

// invalidParametersFailure is the failure object for a response map.
func invalidParametersFailure(err *core.ANIPError) map[string]any {
	return map[string]any{
		"type":   err.ErrorType,
		"detail": err.Detail,
		"resolution": map[string]any{
			"action":         err.Resolution.Action,
			"recovery_class": err.Resolution.RecoveryClass,
			"requires":       err.Resolution.Requires,
		},
		"retry": err.Retry,
	}
}

// isJSONNull reports whether a parameter value is JSON null: an untyped nil,
// or a nil pointer or interface. A nil slice or map handed over by Go code is
// an empty array or object, not null.
func isJSONNull(value any) bool {
	if value == nil {
		return true
	}
	rv := reflect.ValueOf(value)
	switch rv.Kind() {
	case reflect.Pointer, reflect.Interface:
		return rv.IsNil()
	}
	return false
}

// jsonTypeOf names the JSON type of a non-null parameter value as §6.3 does
// ("string", "number", "boolean", "array" or "object"), for every in-memory
// form a transport or a Go caller hands to the service: encoding/json values
// (float64, json.Number, map[string]any, []any), the native ints the REST and
// GraphQL bindings produce, and other Go numbers, strings, slices, maps and
// structs. integral is meaningful for "number" only: the value is finite and
// has no fractional part.
func jsonTypeOf(value any) (kind string, integral bool) {
	switch v := value.(type) {
	case bool:
		return "boolean", false
	case string:
		return "string", false
	case json.Number:
		// A JSON number is an IEEE 754 double (SPEC.md §4.7): "5.0" and
		// "1e2" are integers, and a value out of the double range is not
		// finite.
		f, err := strconv.ParseFloat(string(v), 64)
		return "number", err == nil && isIntegralFloat(f)
	case float64:
		return "number", isIntegralFloat(v)
	case float32:
		return "number", isIntegralFloat(float64(v))
	case int, int8, int16, int32, int64, uint, uint8, uint16, uint32, uint64, uintptr:
		return "number", true
	case *big.Int, big.Int:
		return "number", true
	case *big.Float:
		return "number", !v.IsInf() && v.IsInt()
	case *big.Rat:
		return "number", v.IsInt()
	case json.RawMessage:
		var decoded any
		if err := json.Unmarshal(v, &decoded); err == nil && decoded != nil {
			return jsonTypeOf(decoded)
		}
		return "string", false
	case map[string]any:
		return "object", false
	case []any:
		return "array", false
	}

	rv := reflect.ValueOf(value)
	for rv.Kind() == reflect.Pointer || rv.Kind() == reflect.Interface {
		rv = rv.Elem()
	}
	switch rv.Kind() {
	case reflect.Bool:
		return "boolean", false
	case reflect.String:
		return "string", false
	case reflect.Int, reflect.Int8, reflect.Int16, reflect.Int32, reflect.Int64,
		reflect.Uint, reflect.Uint8, reflect.Uint16, reflect.Uint32, reflect.Uint64, reflect.Uintptr:
		return "number", true
	case reflect.Float32, reflect.Float64:
		return "number", isIntegralFloat(rv.Float())
	case reflect.Slice, reflect.Array:
		return "array", false
	default:
		return "object", false
	}
}

func isIntegralFloat(f float64) bool {
	return !math.IsNaN(f) && !math.IsInf(f, 0) && f == math.Trunc(f)
}
