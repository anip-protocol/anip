package dev.anip.server;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import dev.anip.core.CapabilityInput;
import dev.anip.core.InputMeaning;
import dev.anip.core.InputResolution;
import dev.anip.core.ResolutionBehavior;
import dev.anip.core.ResolutionMode;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class AnipJacksonModuleTest {

    private final ObjectMapper M = JsonHelper.MAPPER;

    @Test
    void resolutionModeSerializesAsWireValue() throws Exception {
        String json = M.writeValueAsString(ResolutionMode.BACKEND_RESOLVED);
        assertEquals("\"backend_resolved\"", json);
    }

    @Test
    void resolutionModeDeserializesFromWireValue() throws Exception {
        ResolutionMode m = M.readValue("\"backend_resolved\"", ResolutionMode.class);
        assertEquals(ResolutionMode.BACKEND_RESOLVED, m);
    }

    @Test
    void resolutionModeDeserializeRejectsUnknown() {
        assertThrows(Exception.class, () -> M.readValue("\"not_real\"", ResolutionMode.class));
    }

    @Test
    void resolutionModeDeserializeRejectsName() {
        // Jackson's default would accept "BACKEND_RESOLVED"; our bridge must reject it
        // because the wire format is the snake_case wire value, not the Java enum name.
        assertThrows(Exception.class, () -> M.readValue("\"BACKEND_RESOLVED\"", ResolutionMode.class));
    }

    @Test
    void resolutionBehaviorSerializesAsWireValue() throws Exception {
        String json = M.writeValueAsString(ResolutionBehavior.USE_DEFAULT);
        assertEquals("\"use_default\"", json);
    }

    @Test
    void resolutionBehaviorDeserializesFromWireValue() throws Exception {
        ResolutionBehavior b = M.readValue("\"app_select_or_clarify\"", ResolutionBehavior.class);
        assertEquals(ResolutionBehavior.APP_SELECT_OR_CLARIFY, b);
    }

    @Test
    void inputResolutionRoundTripsWithSnakeCaseFields() throws Exception {
        InputResolution res = new InputResolution(
                ResolutionMode.BACKEND_RESOLVED,
                "gtm.cohort_catalog",
                ResolutionBehavior.CLARIFY,
                null,
                null);
        String json = M.writeValueAsString(res);
        // The MAPPER applies SNAKE_CASE naming strategy to record components, so
        // resolverRef -> resolver_ref. mode/on_missing already use our serializers.
        JsonNode tree = M.readTree(json);
        assertEquals("backend_resolved", tree.get("mode").asText());
        assertEquals("gtm.cohort_catalog", tree.get("resolver_ref").asText());
        assertEquals("clarify", tree.get("on_missing").asText());

        InputResolution rt = M.readValue(json, InputResolution.class);
        assertEquals(res, rt);
    }

    // SPEC.md §4.1: `required` defaults to true wherever a declaration is read.

    @Test
    void capabilityInputWithoutRequiredIsRequired() throws Exception {
        CapabilityInput input = M.readValue(
                "{\"name\":\"origin\",\"type\":\"airport_code\"}", CapabilityInput.class);
        assertEquals("origin", input.getName());
        assertEquals("airport_code", input.getType());
        assertTrue(input.isRequired());
    }

    @Test
    void capabilityInputKeepsAStatedRequired() throws Exception {
        assertFalse(M.readValue(
                "{\"name\":\"n\",\"type\":\"integer\",\"required\":false,\"default\":1}",
                CapabilityInput.class).isRequired());
        assertTrue(M.readValue(
                "{\"name\":\"n\",\"type\":\"integer\",\"required\":true}",
                CapabilityInput.class).isRequired());
    }

    @Test
    void capabilityInputDecodesEveryDeclaredField() throws Exception {
        CapabilityInput input = M.readValue("""
                {"name":"cohort","type":"string","required":false,"default":"renewal_risk",
                 "description":"Cohort","semantic_type":"cohort_reference","entity_reference":true,
                 "allowed_values":["renewal_risk","expansion_ready"],"catalog_ref":"gtm.cohorts",
                 "input_meanings":[{"label":"Risk","value":"renewal_risk","description":"at risk"}],
                 "resolution":{"mode":"closed_values","on_missing":"use_default"},
                 "unknown_member":1}
                """, CapabilityInput.class);
        assertFalse(input.isRequired());
        assertEquals("renewal_risk", input.getDefaultValue());
        assertEquals("Cohort", input.getDescription());
        assertEquals("cohort_reference", input.getSemanticType());
        assertTrue(input.isEntityReference());
        assertEquals(java.util.List.of("renewal_risk", "expansion_ready"), input.getAllowedValues());
        assertEquals("gtm.cohorts", input.getCatalogRef());
        assertEquals(new InputMeaning("Risk", "renewal_risk", "at risk"), input.getInputMeanings().get(0));
        assertEquals(ResolutionMode.CLOSED_VALUES, input.getResolution().mode());
        assertEquals(ResolutionBehavior.USE_DEFAULT, input.getResolution().onMissing());
    }

    @Test
    void capabilityInputSerialisationAlwaysWritesRequired() throws Exception {
        JsonNode required = M.readTree(M.writeValueAsString(new CapabilityInput("a", "string")));
        assertTrue(required.get("required").isBoolean());
        assertTrue(required.get("required").asBoolean());
        JsonNode optional = M.readTree(M.writeValueAsString(
                new CapabilityInput("a", "string", false, "optional")));
        assertTrue(optional.get("required").isBoolean());
        assertFalse(optional.get("required").asBoolean());
    }

    @Test
    void inputMeaningRoundTrips() throws Exception {
        InputMeaning m = new InputMeaning("High", "P0", "critical");
        String json = M.writeValueAsString(m);
        InputMeaning rt = M.readValue(json, InputMeaning.class);
        assertEquals(m, rt);
    }
}
