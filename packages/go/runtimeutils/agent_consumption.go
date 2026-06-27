package runtimeutils

import (
	"encoding/json"
	"regexp"
	"sort"
	"strings"
)

var (
	tokenPattern          = regexp.MustCompile(`[a-z0-9]+`)
	semanticTextPattern   = regexp.MustCompile(`[^a-z0-9]+`)
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
