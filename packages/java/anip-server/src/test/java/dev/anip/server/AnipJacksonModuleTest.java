package dev.anip.server;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
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

    @Test
    void inputMeaningRoundTrips() throws Exception {
        InputMeaning m = new InputMeaning("High", "P0", "critical");
        String json = M.writeValueAsString(m);
        InputMeaning rt = M.readValue(json, InputMeaning.class);
        assertEquals(m, rt);
    }
}
