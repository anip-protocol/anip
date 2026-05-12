package dev.anip.core;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class InputResolutionTest {
    private final ObjectMapper M = new ObjectMapper();

    @Test
    void v023ShapedInputParsesUnchanged() throws Exception {
        String raw = "{\"name\":\"q\",\"type\":\"string\"}";
        CapabilityInput inp = M.readValue(raw, CapabilityInput.class);
        assertNull(inp.getResolution());
        assertFalse(inp.isEntityReference());
        assertNull(inp.getSemanticType());
        assertNull(inp.getCatalogRef());
    }

    @Test
    void backendResolvedParses() throws Exception {
        String raw = "{\"name\":\"cohort_ref\",\"type\":\"string\",\"required\":true," +
                "\"semantic_type\":\"cohort_reference\",\"entity_reference\":true,\"catalog_ref\":\"gtm.cohort_catalog\"," +
                "\"resolution\":{\"mode\":\"backend_resolved\",\"resolver_ref\":\"gtm.cohort_catalog\",\"on_missing\":\"clarify\"}}";
        CapabilityInput inp = M.readValue(raw, CapabilityInput.class);
        CapabilityInput.validate(inp);
        assertEquals(ResolutionMode.BACKEND_RESOLVED, inp.getResolution().mode());
        assertEquals("gtm.cohort_catalog", inp.getCatalogRef());
        assertTrue(inp.isEntityReference());
    }

    @Test
    void unknownModeRejected() throws Exception {
        String raw = "{\"name\":\"x\",\"type\":\"string\",\"resolution\":{\"mode\":\"not_real\"}}";
        assertThrows(Exception.class, () -> M.readValue(raw, CapabilityInput.class));
    }

    @Test
    void missingModeRejected() throws Exception {
        String raw = "{\"name\":\"x\",\"type\":\"string\",\"resolution\":{}}";
        assertThrows(Exception.class, () -> M.readValue(raw, CapabilityInput.class));
    }

    @Test
    void closedValuesWithoutAllowedValuesRejected() throws Exception {
        String raw = "{\"name\":\"x\",\"type\":\"string\",\"resolution\":{\"mode\":\"closed_values\"}}";
        CapabilityInput inp = M.readValue(raw, CapabilityInput.class);
        assertThrows(IllegalArgumentException.class, () -> CapabilityInput.validate(inp));
    }

    @Test
    void useDefaultWithoutDefaultRejected() throws Exception {
        String raw = "{\"name\":\"x\",\"type\":\"string\",\"resolution\":{\"mode\":\"clarify\",\"on_missing\":\"use_default\"}}";
        CapabilityInput inp = M.readValue(raw, CapabilityInput.class);
        assertThrows(IllegalArgumentException.class, () -> CapabilityInput.validate(inp));
    }

    @Test
    void roundTrip() throws Exception {
        CapabilityInput inp = new CapabilityInput(
                "cohort_ref", "string", true, null, "",
                "cohort_reference", true, null, "gtm.cohort_catalog", null,
                new InputResolution(ResolutionMode.BACKEND_RESOLVED, "gtm.cohort_catalog",
                        ResolutionBehavior.CLARIFY, null, null)
        );
        String json = M.writeValueAsString(inp);
        CapabilityInput rt = M.readValue(json, CapabilityInput.class);
        assertEquals(inp.getResolution().mode(), rt.getResolution().mode());
        assertEquals(inp.getCatalogRef(), rt.getCatalogRef());
    }
}
