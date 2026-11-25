package dev.anip.core;

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

class InputResolutionTest {

    @Test
    void v023ShapedInputDefaultsClean() {
        CapabilityInput inp = new CapabilityInput("q", "string", true, "");
        assertNull(inp.getResolution());
        assertFalse(inp.isEntityReference());
        assertNull(inp.getSemanticType());
        assertNull(inp.getCatalogRef());
        assertNull(inp.getAllowedValues());
        assertNull(inp.getInputMeanings());
    }

    @Test
    void fullConstructionPreservesAllFields() {
        InputResolution res = new InputResolution(
                ResolutionMode.BACKEND_RESOLVED, "gtm.cohort_catalog",
                ResolutionBehavior.CLARIFY, null, null);
        CapabilityInput inp = new CapabilityInput(
                "cohort_ref", "string", true, null, "",
                "cohort_reference", true, null, "gtm.cohort_catalog", null, res);
        CapabilityInput.validate(inp);
        assertEquals(ResolutionMode.BACKEND_RESOLVED, inp.getResolution().mode());
        assertEquals("gtm.cohort_catalog", inp.getResolution().resolverRef());
        assertEquals(ResolutionBehavior.CLARIFY, inp.getResolution().onMissing());
        assertEquals("gtm.cohort_catalog", inp.getCatalogRef());
        assertTrue(inp.isEntityReference());
        assertEquals("cohort_reference", inp.getSemanticType());
    }

    @Test
    void unknownModeWireRejected() {
        assertThrows(IllegalArgumentException.class, () -> ResolutionMode.fromWire("not_real"));
    }

    @Test
    void unknownBehaviorWireRejected() {
        assertThrows(IllegalArgumentException.class, () -> ResolutionBehavior.fromWire("bogus"));
    }

    @Test
    void missingModeRejectedAtConstruction() {
        assertThrows(IllegalArgumentException.class,
                () -> new InputResolution(null, null, null, null, null));
    }

    @Test
    void closedValuesWithoutAllowedValuesRejected() {
        InputResolution res = new InputResolution(ResolutionMode.CLOSED_VALUES, null, null, null, null);
        CapabilityInput inp = new CapabilityInput(
                "x", "string", true, null, "",
                null, false, null, null, null, res);
        assertThrows(IllegalArgumentException.class, () -> CapabilityInput.validate(inp));
    }

    @Test
    void closedValuesWithEmptyAllowedValuesRejected() {
        InputResolution res = new InputResolution(ResolutionMode.CLOSED_VALUES, null, null, null, null);
        CapabilityInput inp = new CapabilityInput(
                "x", "string", true, null, "",
                null, false, List.of(), null, null, res);
        assertThrows(IllegalArgumentException.class, () -> CapabilityInput.validate(inp));
    }

    @Test
    void useDefaultWithoutDefaultRejected() {
        InputResolution res = new InputResolution(
                ResolutionMode.CLARIFY, null, ResolutionBehavior.USE_DEFAULT, null, null);
        CapabilityInput inp = new CapabilityInput(
                "x", "string", true, null, "",
                null, false, null, null, null, res);
        assertThrows(IllegalArgumentException.class, () -> CapabilityInput.validate(inp));
    }

    @Test
    void inputMeaningDefaultsDescriptionToEmpty() {
        InputMeaning m = new InputMeaning("High", "P0", null);
        assertEquals("", m.description());
    }

    @Test
    void wireValuesMatchSpec() {
        // Pin enum wire format against SPEC §4.10. Downstream JSON mappers
        // (configured snake_case) consume these via fromWire(...) / wire().
        assertEquals("closed_values", ResolutionMode.CLOSED_VALUES.wire());
        assertEquals("backend_resolved", ResolutionMode.BACKEND_RESOLVED.wire());
        assertEquals("actor_policy_or_explicit", ResolutionMode.ACTOR_POLICY_OR_EXPLICIT.wire());
        assertEquals("use_default", ResolutionBehavior.USE_DEFAULT.wire());
        assertEquals("app_select_or_clarify", ResolutionBehavior.APP_SELECT_OR_CLARIFY.wire());
        assertSame(ResolutionMode.BACKEND_RESOLVED, ResolutionMode.fromWire("backend_resolved"));
        assertSame(ResolutionBehavior.USE_DEFAULT, ResolutionBehavior.fromWire("use_default"));
    }

    // SPEC.md §4.1: an input whose declaration does not state `required` is required.
    @Test
    void inputDeclaredWithoutRequiredIsRequired() {
        CapabilityInput inp = new CapabilityInput("origin", "airport_code");
        assertTrue(inp.isRequired());
        assertEquals("origin", inp.getName());
        assertEquals("airport_code", inp.getType());
        assertFalse(new CapabilityInput("q", "string", false, "optional").isRequired());
    }

    // SPEC.md §6.3: a required input whose resolution sets on_missing is not
    // demanded of the caller; the service answers through the on_missing path.
    @Test
    void mustBeSuppliedFollowsRequiredAndOnMissing() {
        assertTrue(new CapabilityInput("a", "string").mustBeSupplied());
        assertFalse(new CapabilityInput("a", "string", false, "optional").mustBeSupplied());

        InputResolution modeOnly = new InputResolution(
                ResolutionMode.EXPLICIT_ONLY, null, null, ResolutionBehavior.CLARIFY, ResolutionBehavior.DENY);
        assertTrue(new CapabilityInput("a", "string", true, null, "", null, false,
                null, null, null, modeOnly).mustBeSupplied());

        for (ResolutionBehavior behavior : ResolutionBehavior.values()) {
            InputResolution onMissing = new InputResolution(
                    ResolutionMode.CLARIFY, null, behavior, null, null);
            assertFalse(new CapabilityInput("a", "string", true, null, "", null, false,
                    null, null, null, onMissing).mustBeSupplied(), behavior.wire());
            assertFalse(new CapabilityInput("a", "string", false, null, "", null, false,
                    null, null, null, onMissing).mustBeSupplied(), behavior.wire());
        }
    }
}
