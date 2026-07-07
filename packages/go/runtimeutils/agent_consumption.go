package runtimeutils

import (
	"encoding/json"
	"fmt"
	"regexp"
	"sort"
	"strings"
)

var (
	tokenPattern          = regexp.MustCompile(`[a-z0-9]+`)
	semanticTextPattern   = regexp.MustCompile(`[^a-z0-9]+`)
	identifierPattern     = regexp.MustCompile(`\b[A-Z][A-Z0-9]+-[A-Z0-9]+\b|\b[A-Za-z]+-\d+\b`)
	quarterPattern        = regexp.MustCompile(`(?i)\b(?:19|20)\d{2}-Q[1-4]\b|\bQ[1-4]\s+(?:FY)?(?:19|20)?\d{2,4}\b`)
	numberPattern         = regexp.MustCompile(`\b\d+\b`)
	concreteEntityPattern = regexp.MustCompile(`[A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+){1,3}|[_-]|\d`)
	capabilityEffectTerms = map[string]map[string]bool{
		"approval.execute": {
			"approve": true, "apply": true, "commit": true, "execute": true, "perform": true,
		},
		"external_dispatch": {
			"deliver": true, "dispatch": true, "publish": true, "send": true, "ship": true,
		},
		"raw_data_export": {
			"csv": true, "download": true, "dump": true, "export": true, "raw": true, "spreadsheet": true,
		},
		"system.mutation": {
			"apply": true, "commit": true, "delete": true, "mutate": true, "update": true,
		},
	}
	negationTerms = map[string]bool{
		"avoid": true, "exclude": true, "no": true, "not": true, "without": true,
	}
	capabilityScoringStopTokens = map[string]bool{
		"after": true, "and": true, "before": true, "for": true, "in": true, "of": true,
		"that": true, "the": true, "these": true, "this": true, "those": true, "to": true, "with": true,
	}
	weakInputTokens = map[string]bool{
		"id": true, "ids": true, "input": true, "name": true, "names": true,
		"ref": true, "reference": true, "value": true, "values": true,
	}
)

// CapabilityMetadata is contract-derived metadata for one capability.
type CapabilityMetadata map[string]any

// FallbackValidationOptions configures deterministic planner fallback validation.
type FallbackValidationOptions struct {
	CompactCandidateIDs []string
}

// SemanticTextKey normalizes text for compact substring checks.
func SemanticTextKey(value string) string {
	return semanticTextPattern.ReplaceAllString(strings.ToLower(value), "")
}

// TextTokens returns normalized alphanumeric tokens keyed by token text.
func TextTokens(value string) map[string]bool {
	out := map[string]bool{}
	for _, token := range orderedTextTokens(value) {
		out[token] = true
	}
	return out
}

// MissingRequiredInputNames returns required inputs not grounded by the conversation.
func MissingRequiredInputNames(conversation string, metadata CapabilityMetadata) []string {
	missing := []string{}
	for _, rawSpec := range anyList(metadata["input_specs"]) {
		spec := record(rawSpec)
		if !boolValue(spec["required"]) {
			continue
		}
		name := stringValue(spec["name"])
		if name == "" {
			continue
		}
		if inputHasDefault(spec) && stringValue(record(spec["resolution"])["on_missing"]) == "use_default" {
			continue
		}
		if !inputGrounded(conversation, inputCandidateValues(metadata, spec)) {
			missing = append(missing, name)
		}
	}
	return missing
}

// RequestedUnsupportedEffects returns unsupported effects requested by the conversation.
func RequestedUnsupportedEffects(conversation string, metadata CapabilityMetadata) []string {
	tokens := TextTokens(conversation)
	orderedTokens := orderedTextTokens(conversation)
	blocked := capabilityDoesNotProduce(metadata)
	produced := capabilityProduces(metadata)
	boundaries := appBoundaries(metadata)
	lowered := strings.ToLower(conversation)
	requested := map[string]bool{}

	for effect, terms := range record(boundaries["unsupported_terms"]) {
		for _, term := range stringList(terms) {
			if term != "" && strings.Contains(lowered, strings.ToLower(term)) {
				requested[effect] = true
			}
		}
	}

	for effect, terms := range capabilityEffectTerms {
		matchedTerms := []string{}
		for term := range terms {
			if tokens[term] {
				matchedTerms = append(matchedTerms, term)
			}
		}
		if len(matchedTerms) == 0 {
			continue
		}
		allNegated := true
		for _, term := range matchedTerms {
			if !termIsNegated(orderedTokens, term) {
				allNegated = false
				break
			}
		}
		if allNegated {
			continue
		}
		if blocked[effect] || (effect == "raw_data_export" && !produced["raw_data_export"]) || (effect == "external_dispatch" && produced["content.draft"]) {
			requested[effect] = true
		}
	}

	return sortedKeys(requested)
}

// DetectUnsupportedEffects is an alias kept for plan/API parity.
func DetectUnsupportedEffects(conversation string, metadata CapabilityMetadata) []string {
	return RequestedUnsupportedEffects(conversation, metadata)
}

// CapabilityMatchScore scores a capability against conversation text using metadata tokens.
func CapabilityMatchScore(conversation string, capabilityID string, metadata CapabilityMetadata) float64 {
	inputFragments := []string{}
	for _, rawSpec := range anyList(metadata["input_specs"]) {
		spec := record(rawSpec)
		inputFragments = append(inputFragments,
			stringValue(spec["name"]),
			stringValue(spec["semantic_type"]),
			stringValue(spec["description"]),
		)
		inputFragments = append(inputFragments, stringList(spec["allowed_values"])...)
	}

	appProfile := record(metadata["app_profile"])
	intent := record(appProfile["intent"])
	haystack := strings.Join([]string{
		capabilityID,
		stringValue(metadata["capability_id"]),
		stringValue(metadata["id"]),
		stringValue(metadata["description"]),
		stringValue(metadata["capability_framing"]),
		stringValue(metadata["summary"]),
		stringValue(metadata["output_intent"]),
		stringValue(appProfile["capability_framing"]),
		stringValue(intent["category"]),
		stringValue(intent["summary"]),
		jsonString(appProfile["input_meanings"]),
		jsonString(appProfile["app_boundaries"]),
		strings.Join(inputFragments, " "),
	}, " ")

	sourceTokens := scoreTokens(conversation)
	targetTokens := scoreTokens(haystack)
	if len(sourceTokens) == 0 || len(targetTokens) == 0 {
		return 0
	}

	overlap := 0
	for token := range sourceTokens {
		if targetTokens[token] {
			overlap++
		}
	}
	recall := float64(overlap) / float64(len(sourceTokens))
	precision := float64(overlap) / float64(len(targetTokens))

	idTokens := scoreTokens(capabilityID)
	idPrecision := 0.0
	if len(idTokens) > 0 {
		idOverlap := 0
		for token := range sourceTokens {
			if idTokens[token] {
				idOverlap++
			}
		}
		idPrecision = float64(idOverlap) / float64(len(idTokens))
	}

	return recall*0.65 + precision*0.25 + idPrecision*0.1
}

// SelectConsumableCapability chooses the strongest same-effect capability.
func SelectConsumableCapability(conversation string, selectedCapability string, metadata map[string]CapabilityMetadata) string {
	selectedMetadata, ok := metadata[selectedCapability]
	if !ok || len(selectedMetadata) == 0 {
		return selectedCapability
	}

	selectedMissing := MissingRequiredInputNames(conversation, selectedMetadata)
	selectedScore := CapabilityMatchScore(conversation, selectedCapability, selectedMetadata)
	bestCapability := selectedCapability
	bestScore := selectedScore

	for capabilityID, candidate := range metadata {
		if capabilityID == selectedCapability || !sameEffectClass(selectedMetadata, candidate) {
			continue
		}
		missing := MissingRequiredInputNames(conversation, candidate)
		if len(selectedMissing) > 0 && len(missing) > 0 && !missingRequiredInputsAreReferenced(conversation, candidate, missing) {
			continue
		}
		score := CapabilityMatchScore(conversation, capabilityID, candidate)
		if score > bestScore {
			bestCapability = capabilityID
			bestScore = score
		}
	}

	if bestCapability != selectedCapability && bestScore >= maxFloat(0.12, selectedScore+0.08) {
		return bestCapability
	}
	return selectedCapability
}

// RequestedPrimaryContentEffect returns the primary content effect requested by conversation text.
func RequestedPrimaryContentEffect(conversation string) string {
	tokens := TextTokens(conversation)
	orderedTokens := orderedTextTokens(conversation)
	if hasUnnegatedToken(tokens, orderedTokens, []string{"recommend", "recommendation", "recommendations"}) {
		return "content.recommendation"
	}
	if hasUnnegatedToken(tokens, orderedTokens, []string{"draft", "email", "outreach", "message", "variant", "variants", "option", "options"}) {
		return "content.draft"
	}
	if hasUnnegatedToken(tokens, orderedTokens, []string{"summarize", "summary"}) {
		return "content.summary"
	}
	return ""
}

// IsApprovalCapability reports whether a capability is an approval boundary.
func IsApprovalCapability(metadata CapabilityMetadata) bool {
	produced := capabilityProduces(metadata)
	if produced["approval.request"] || produced["system.preview_mutation"] {
		return true
	}
	return boolValue(record(metadata["approval"])["required"])
}

// ValidateInvocationPlanForFallback returns deterministic reasons a primary planner result should escalate.
func ValidateInvocationPlanForFallback(plan CapabilityMetadata, conversation string, metadata map[string]CapabilityMetadata, options FallbackValidationOptions) []string {
	reasons := []string{}
	capability := strings.TrimSpace(stringValue(plan["selected_capability"]))
	if capability == "" {
		return []string{"selected capability is missing"}
	}
	capabilityMetadata, ok := metadata[capability]
	if !ok || len(capabilityMetadata) == 0 {
		return []string{fmt.Sprintf("selected capability is not discovered: %s", capability)}
	}
	if len(options.CompactCandidateIDs) > 0 && !containsString(options.CompactCandidateIDs, capability) {
		reasons = append(reasons, fmt.Sprintf("selected capability is outside compact candidate set: %s", capability))
	}

	parameters := record(plan["parameters"])
	if _, ok := plan["parameters"].(map[string]any); !ok {
		if _, ok := plan["parameters"].(CapabilityMetadata); !ok {
			reasons = append(reasons, "parameters payload is not an object")
			parameters = CapabilityMetadata{}
		}
	}

	if len(RequestedUnsupportedEffects(conversation, capabilityMetadata)) > 0 {
		return reasons
	}

	missing := []string{}
	for _, inputName := range MissingRequiredInputNames(conversation, capabilityMetadata) {
		if _, ok := parameters[inputName]; !ok {
			missing = append(missing, inputName)
		}
	}
	if missingRequiredInputsAreConcretelyReferenced(conversation, capabilityMetadata, missing) {
		sort.Strings(missing)
		reasons = append(reasons, "missing required input(s) appear present but unbound: "+strings.Join(missing, ", "))
	}

	requestedEffect := RequestedPrimaryContentEffect(conversation)
	produced := capabilityProduces(capabilityMetadata)
	if requestedEffect != "" && !produced[requestedEffect] && !IsApprovalCapability(capabilityMetadata) {
		reasons = append(reasons, fmt.Sprintf("selected capability does not produce requested primary effect: %s", requestedEffect))
	}

	return reasons
}

func orderedTextTokens(value string) []string {
	normalized := strings.ReplaceAll(strings.ToLower(value), "_", " ")
	tokens := tokenPattern.FindAllString(normalized, -1)
	out := make([]string, 0, len(tokens))
	for _, token := range tokens {
		if len(token) > 1 {
			out = append(out, token)
		}
	}
	return out
}

func tokenVariants(tokens map[string]bool) map[string]bool {
	variants := map[string]bool{}
	for token := range tokens {
		variants[token] = true
		if len(token) <= 3 {
			continue
		}
		switch {
		case strings.HasSuffix(token, "ies") && len(token) > 4:
			variants[token[:len(token)-3]+"y"] = true
		case strings.HasSuffix(token, "ing") && len(token) > 5:
			variants[token[:len(token)-3]] = true
		case strings.HasSuffix(token, "ed") && len(token) > 4:
			variants[token[:len(token)-2]] = true
		case strings.HasSuffix(token, "es") && len(token) > 4:
			variants[token[:len(token)-2]] = true
		case strings.HasSuffix(token, "s") && len(token) > 4:
			variants[token[:len(token)-1]] = true
		default:
			variants[token+"s"] = true
		}
	}
	return variants
}

func scoreTokens(value string) map[string]bool {
	filtered := map[string]bool{}
	for token := range TextTokens(value) {
		if capabilityScoringStopTokens[token] || isYearToken(token) {
			continue
		}
		filtered[token] = true
	}
	return tokenVariants(filtered)
}

func record(value any) CapabilityMetadata {
	switch typed := value.(type) {
	case CapabilityMetadata:
		return typed
	case map[string]any:
		return CapabilityMetadata(typed)
	default:
		return CapabilityMetadata{}
	}
}

func anyList(value any) []any {
	switch typed := value.(type) {
	case []any:
		return typed
	case []CapabilityMetadata:
		out := make([]any, 0, len(typed))
		for _, item := range typed {
			out = append(out, item)
		}
		return out
	default:
		return nil
	}
}

func stringList(value any) []string {
	switch typed := value.(type) {
	case []any:
		out := make([]string, 0, len(typed))
		for _, item := range typed {
			if text := stringValue(item); text != "" {
				out = append(out, text)
			}
		}
		return out
	case []string:
		out := make([]string, 0, len(typed))
		for _, item := range typed {
			if item != "" {
				out = append(out, item)
			}
		}
		return out
	default:
		return nil
	}
}

func stringValue(value any) string {
	switch typed := value.(type) {
	case string:
		return typed
	case nil:
		return ""
	default:
		return strings.TrimSpace(toString(typed))
	}
}

func toString(value any) string {
	switch typed := value.(type) {
	case []byte:
		return string(typed)
	default:
		return strings.TrimSpace(jsonString(typed))
	}
}

func boolValue(value any) bool {
	typed, ok := value.(bool)
	return ok && typed
}

func jsonString(value any) string {
	if value == nil {
		return ""
	}
	data, err := json.Marshal(value)
	if err != nil {
		return ""
	}
	return string(data)
}

func inputHasDefault(spec CapabilityMetadata) bool {
	value, ok := spec["default"]
	if !ok || value == nil {
		return false
	}
	switch typed := value.(type) {
	case string:
		return typed != ""
	case []any:
		return len(typed) > 0
	case []string:
		return len(typed) > 0
	default:
		return true
	}
}

func inputCandidateValues(metadata CapabilityMetadata, spec CapabilityMetadata) []string {
	inputName := stringValue(spec["name"])
	meanings := record(record(metadata["app_profile"])["input_meanings"])
	inputMeanings := record(meanings[inputName])
	values := stringList(spec["allowed_values"])
	for key, value := range inputMeanings {
		if key != "" {
			values = append(values, key)
		}
		if text := stringValue(value); text != "" {
			values = append(values, text)
		}
	}
	return values
}

func inputGrounded(conversation string, values []string) bool {
	conversationKey := SemanticTextKey(conversation)
	conversationTokens := TextTokens(conversation)
	for _, value := range values {
		valueKey := SemanticTextKey(value)
		if valueKey == "" {
			continue
		}
		if strings.Contains(conversationKey, valueKey) {
			return true
		}
		valueTokens := TextTokens(value)
		if len(valueTokens) == 0 {
			continue
		}
		allTokensPresent := true
		for token := range valueTokens {
			if !conversationTokens[token] {
				allTokensPresent = false
				break
			}
		}
		if allTokensPresent {
			return true
		}
	}
	return false
}

func capabilityProduces(metadata CapabilityMetadata) map[string]bool {
	return stringSet(stringList(record(metadata["business_effects"])["produces"]))
}

func capabilityDoesNotProduce(metadata CapabilityMetadata) map[string]bool {
	boundaries := appBoundaries(metadata)
	if unsupported := stringList(boundaries["unsupported_effects"]); len(unsupported) > 0 {
		return stringSet(unsupported)
	}
	return stringSet(stringList(record(metadata["business_effects"])["does_not_produce"]))
}

func appBoundaries(metadata CapabilityMetadata) CapabilityMetadata {
	if boundaries := record(record(metadata["app_profile"])["app_boundaries"]); len(boundaries) > 0 {
		return boundaries
	}
	return record(metadata["app_boundaries"])
}

func termIsNegated(tokens []string, term string) bool {
	for index, token := range tokens {
		if token != term {
			continue
		}
		start := index - 6
		if start < 0 {
			start = 0
		}
		window := tokens[start:index]
		for _, item := range window {
			if negationTerms[item] {
				return true
			}
		}
		if len(window) >= 2 && window[len(window)-2] == "do" && window[len(window)-1] == "not" {
			return true
		}
	}
	return false
}

func inputReferenceTokens(metadata CapabilityMetadata, inputName string) map[string]bool {
	spec := CapabilityMetadata{}
	for _, rawSpec := range anyList(metadata["input_specs"]) {
		candidate := record(rawSpec)
		if stringValue(candidate["name"]) == inputName {
			spec = candidate
			break
		}
	}
	tokens := TextTokens(strings.Join([]string{
		inputName,
		stringValue(spec["semantic_type"]),
		stringValue(spec["description"]),
	}, " "))
	for token := range tokens {
		if weakInputTokens[token] {
			delete(tokens, token)
		}
	}
	return tokens
}

func missingRequiredInputsAreReferenced(conversation string, metadata CapabilityMetadata, missingInputs []string) bool {
	if len(missingInputs) == 0 {
		return false
	}
	conversationTokens := TextTokens(conversation)
	if len(conversationTokens) == 0 {
		return false
	}
	for _, inputName := range missingInputs {
		tokens := inputReferenceTokens(metadata, inputName)
		if len(tokens) == 0 {
			return false
		}
		matched := false
		for token := range tokens {
			if conversationTokens[token] {
				matched = true
				break
			}
		}
		if !matched {
			return false
		}
	}
	return true
}

func missingRequiredInputsAreConcretelyReferenced(conversation string, metadata CapabilityMetadata, missingInputs []string) bool {
	if len(missingInputs) == 0 {
		return false
	}
	specs := map[string]CapabilityMetadata{}
	for _, rawSpec := range anyList(metadata["input_specs"]) {
		spec := record(rawSpec)
		name := stringValue(spec["name"])
		if name != "" {
			specs[name] = spec
		}
	}
	conversationTokens := TextTokens(conversation)
	for _, inputName := range missingInputs {
		spec := specs[inputName]
		tokens := inputReferenceTokens(metadata, inputName)
		matched := false
		for token := range tokens {
			if conversationTokens[token] {
				matched = true
				break
			}
		}
		if !matched || !missingInputHasConcreteEvidence(conversation, spec, metadata) {
			return false
		}
	}
	return true
}

func missingInputHasConcreteEvidence(conversation string, spec CapabilityMetadata, metadata CapabilityMetadata) bool {
	inputName := strings.ToLower(stringValue(spec["name"]))
	semanticType := strings.ToLower(stringValue(spec["semantic_type"]))
	rawType := strings.ToLower(stringValue(spec["type"]))
	if strings.Contains(inputName, "id") || strings.HasSuffix(semanticType, "_id") {
		return identifierPattern.MatchString(conversation)
	}
	if semanticType == "time_scope" || strings.Contains(inputName, "quarter") || strings.Contains(inputName, "period") || strings.Contains(inputName, "date") {
		return quarterPattern.MatchString(conversation)
	}
	if rawType == "integer" || rawType == "number" || rawType == "float" || strings.Contains(inputName, "limit") || strings.Contains(inputName, "count") {
		return numberPattern.MatchString(conversation)
	}
	if values := stringList(spec["allowed_values"]); len(values) > 0 {
		for _, value := range values {
			if conversationContainsValue(conversation, value) {
				return true
			}
		}
		return false
	}
	tokens := inputReferenceTokens(metadata, stringValue(spec["name"]))
	if len(tokens) == 0 || !concreteEntityPattern.MatchString(conversation) {
		return false
	}
	conversationTokens := TextTokens(conversation)
	for token := range tokens {
		if conversationTokens[token] {
			return true
		}
	}
	return false
}

func conversationContainsValue(conversation string, value string) bool {
	valueKey := SemanticTextKey(value)
	if valueKey == "" {
		return false
	}
	if strings.Contains(SemanticTextKey(conversation), valueKey) {
		return true
	}
	conversationTokens := TextTokens(conversation)
	valueTokens := TextTokens(value)
	if len(valueTokens) == 0 {
		return false
	}
	for token := range valueTokens {
		if !conversationTokens[token] {
			return false
		}
	}
	return true
}

func sameEffectClass(first CapabilityMetadata, second CapabilityMetadata) bool {
	firstProduces := capabilityProduces(first)
	secondProduces := capabilityProduces(second)
	for effect := range firstProduces {
		if secondProduces[effect] {
			return true
		}
	}
	return false
}

func hasUnnegatedToken(tokens map[string]bool, orderedTokens []string, terms []string) bool {
	for _, term := range terms {
		if tokens[term] && !termIsNegated(orderedTokens, term) {
			return true
		}
	}
	return false
}

func containsString(values []string, target string) bool {
	for _, value := range values {
		if value == target {
			return true
		}
	}
	return false
}

func sortedKeys(values map[string]bool) []string {
	out := make([]string, 0, len(values))
	for value := range values {
		out = append(out, value)
	}
	sort.Strings(out)
	return out
}

func stringSet(values []string) map[string]bool {
	out := map[string]bool{}
	for _, value := range values {
		if value != "" {
			out[value] = true
		}
	}
	return out
}

func isYearToken(token string) bool {
	if len(token) != 4 || (token[:2] != "19" && token[:2] != "20") {
		return false
	}
	for _, char := range token {
		if char < '0' || char > '9' {
			return false
		}
	}
	return true
}

func maxFloat(first float64, second float64) float64 {
	if first > second {
		return first
	}
	return second
}
