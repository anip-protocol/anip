package definitionvalidation

import "testing"

// SPEC.md §4.1: a child input that does not state required is required, so a
// composition has to map it.
func TestCompositionMustMapChildInputThatDoesNotStateRequired(t *testing.T) {
	definition := loadCompatDefinition(t)
	extra := addCompatChildInput(definition, "compat.lookup", "region", "region")
	extra["required"] = false
	expectCompatDefinitionAccepted(t, definition)

	delete(extra, "required")
	expectCompatDefinitionRejected(t, definition, "region is required for child capability")

	extra["required"] = true
	expectCompatDefinitionRejected(t, definition, "region is required for child capability")
}
