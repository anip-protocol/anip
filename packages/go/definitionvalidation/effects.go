package definitionvalidation

import (
	"fmt"
	"sort"
	"strings"
)

var knownBusinessEffectIDs = map[string]struct{}{
	"approval.execute":        {},
	"approval.request":        {},
	"content.draft":           {},
	"content.recommendation":  {},
	"content.summary":         {},
	"data.aggregate":          {},
	"data.export":             {},
	"data.read":               {},
	"external_dispatch":       {},
	"raw_data_export":         {},
	"raw_model_features":      {},
	"system.mutation":         {},
	"system.preview_mutation": {},
}

// KnownBusinessEffectIDs returns the closed ANIP business-effect vocabulary.
func KnownBusinessEffectIDs() []string {
	ids := make([]string, 0, len(knownBusinessEffectIDs))
	for id := range knownBusinessEffectIDs {
		ids = append(ids, id)
	}
	sort.Strings(ids)
	return ids
}

// IsKnownBusinessEffect reports whether effectID is in the current ANIP effect vocabulary.
func IsKnownBusinessEffect(effectID string) bool {
	_, ok := knownBusinessEffectIDs[strings.TrimSpace(effectID)]
	return ok
}

func validateBusinessEffectList(path string, value any) error {
	items, ok := value.([]any)
	if !ok {
		return fmt.Errorf("%s must be an array of canonical effect ids", path)
	}
	for index, item := range items {
		effectID, ok := item.(string)
		if !ok {
			return fmt.Errorf("%s[%d] must be a string", path, index)
		}
		effectID = strings.TrimSpace(effectID)
		if effectID == "" {
			return fmt.Errorf("%s[%d] must not be empty", path, index)
		}
		if !IsKnownBusinessEffect(effectID) {
			return fmt.Errorf("%s[%d] unknown effect %q; use canonical effect ids: %s", path, index, effectID, strings.Join(KnownBusinessEffectIDs(), ", "))
		}
	}
	return nil
}

func ValidateKnownBusinessEffectsInPayload(label string, value any) error {
	return validateKnownBusinessEffectsInPayload(label, value)
}

func validateKnownBusinessEffectsInPayload(path string, value any) error {
	switch typed := value.(type) {
	case map[string]any:
		for key, item := range typed {
			childPath := path + "." + key
			if key == "business_effects" {
				effects, ok := item.(map[string]any)
				if !ok {
					return fmt.Errorf("%s must be an object", childPath)
				}
				for _, effectField := range []string{"produces", "does_not_produce"} {
					if effectValue, exists := effects[effectField]; exists {
						if err := validateBusinessEffectList(childPath+"."+effectField, effectValue); err != nil {
							return err
						}
					}
				}
				if err := validateKnownBusinessEffectsInPayload(childPath, item); err != nil {
					return err
				}
				continue
			}
			if key == "unsupported_effects" || key == "suppress_unsupported_effects" {
				if err := validateBusinessEffectList(childPath, item); err != nil {
					return err
				}
				continue
			}
			if err := validateKnownBusinessEffectsInPayload(childPath, item); err != nil {
				return err
			}
		}
	case []any:
		for index, item := range typed {
			if err := validateKnownBusinessEffectsInPayload(fmt.Sprintf("%s[%d]", path, index), item); err != nil {
				return err
			}
		}
	}
	return nil
}
