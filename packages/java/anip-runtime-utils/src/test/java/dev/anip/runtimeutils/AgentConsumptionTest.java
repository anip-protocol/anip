package dev.anip.runtimeutils;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;

class AgentConsumptionTest {

    @Test
    void sharedAgentConsumptionFixturesPass() throws Exception {
        Path fixturePath = Path.of("..", "..", "agent-consumption-fixtures", "capability-selection.json");
        ObjectMapper mapper = new ObjectMapper();
        Map<String, Object> fixture = mapper.readValue(
                fixturePath.toFile(),
                new TypeReference<Map<String, Object>>() {});

        List<Map<String, Object>> cases = listOfMaps(fixture.get("cases"));
        for (Map<String, Object> testCase : cases) {
            String id = stringValue(testCase.get("id"));
            String conversation = stringValue(testCase.get("conversation"));
            String selectedCapability = stringValue(testCase.get("selected_capability"));
            Map<String, Map<String, Object>> metadata = metadataByCapability(testCase.get("metadata"));

            String chosen = AgentConsumption.selectConsumableCapability(conversation, selectedCapability, metadata);
            assertEquals(stringValue(testCase.get("expected_capability")), chosen, id);

            assertEquals(
                    sortedStrings(testCase.get("expected_missing_inputs")),
                    sortedStrings(AgentConsumption.missingRequiredInputNames(conversation, metadata.get(chosen))),
                    id);
            assertEquals(
                    sortedStrings(testCase.get("expected_unsupported_effects")),
                    sortedStrings(AgentConsumption.detectUnsupportedEffects(conversation, metadata.get(selectedCapability))),
                    id);
            assertEquals(
                    sortedStrings(testCase.get("expected_unsupported_effects")),
                    sortedStrings(AgentConsumption.requestedUnsupportedEffects(conversation, metadata.get(selectedCapability))),
                    id);
        }
    }

    @Test
    void sharedPlannerFallbackValidationFixturesPass() throws Exception {
        Path fixturePath = Path.of("..", "..", "agent-consumption-fixtures", "planner-fallback-validation.json");
        ObjectMapper mapper = new ObjectMapper();
        Map<String, Object> fixture = mapper.readValue(
                fixturePath.toFile(),
                new TypeReference<Map<String, Object>>() {});

        List<Map<String, Object>> cases = listOfMaps(fixture.get("cases"));
        for (Map<String, Object> testCase : cases) {
            String id = stringValue(testCase.get("id"));
            String conversation = stringValue(testCase.get("conversation"));
            Map<String, Object> plan = mapValue(testCase.get("plan"));
            Map<String, Map<String, Object>> metadata = metadataByCapability(testCase.get("metadata"));
            List<String> compactCandidateIds = stringList(testCase.get("compact_candidate_ids"));

            assertEquals(
                    stringList(testCase.get("expected_reasons")),
                    AgentConsumption.validateInvocationPlanForFallback(
                            plan,
                            conversation,
                            metadata,
                            new AgentConsumption.FallbackValidationOptions(compactCandidateIds)),
                    id);
        }
    }

    @SuppressWarnings("unchecked")
    private static List<Map<String, Object>> listOfMaps(Object value) {
        return (List<Map<String, Object>>) value;
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Map<String, Object>> metadataByCapability(Object value) {
        return (Map<String, Map<String, Object>>) value;
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> mapValue(Object value) {
        return (Map<String, Object>) value;
    }

    private static String stringValue(Object value) {
        return String.valueOf(value);
    }

    private static List<String> sortedStrings(Object value) {
        List<String> strings = new ArrayList<>();
        if (value instanceof Iterable<?> iterable) {
            for (Object item : iterable) {
                strings.add(stringValue(item));
            }
        }
        Collections.sort(strings);
        return strings;
    }

    private static List<String> stringList(Object value) {
        List<String> strings = new ArrayList<>();
        if (value instanceof Iterable<?> iterable) {
            for (Object item : iterable) {
                strings.add(stringValue(item));
            }
        }
        return strings;
    }
}
