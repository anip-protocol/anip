package dev.anip.mcptest;

import dev.anip.core.CapabilityDeclaration;
import dev.anip.core.CapabilityInput;
import dev.anip.core.CapabilityOutput;
import dev.anip.core.CapabilityRequirement;
import dev.anip.core.Cost;
import dev.anip.core.SideEffect;
import dev.anip.mcp.McpToolTranslator;

import io.modelcontextprotocol.spec.McpSchema;

import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

class McpToolTranslatorTest {

    private CapabilityDeclaration readDecl() {
        return new CapabilityDeclaration(
                "search_flights", "Search for flights", "1.0",
                List.of(
                        new CapabilityInput("origin", "string", true, "Origin airport"),
                        new CapabilityInput("destination", "string", true, "Destination airport"),
                        new CapabilityInput("max_results", "integer", false, 10, "Max results")
                ),
                new CapabilityOutput("object", List.of("flights")),
                new SideEffect("read", "not_applicable"),
                List.of("travel"), null, null, List.of("sync")
        );
    }

    private CapabilityDeclaration writeDecl() {
        return new CapabilityDeclaration(
                "book_flight", "Book a flight", "1.0",
                List.of(
                        new CapabilityInput("flight_id", "string", true, "Flight ID")
                ),
                new CapabilityOutput("object", List.of("booking_id")),
                new SideEffect("irreversible", "none"),
                List.of("travel", "finance"),
                new Cost("estimated", Map.of("currency", "USD",
                        "estimated_range", Map.of("min", 100, "max", 500)),
                        null, null, null, null),
                List.of(new CapabilityRequirement("search_flights", "Must search first")),
                List.of("sync")
        );
    }

    // --- Tool building ---

    @Test
    void testBuildToolReadCapability() {
        McpSchema.Tool tool = McpToolTranslator.buildTool("search_flights", readDecl(), false);

        assertEquals("search_flights", tool.name());
        assertEquals("Search for flights", tool.description());
        assertNotNull(tool.inputSchema());
        assertTrue(tool.annotations().readOnlyHint());
        assertFalse(tool.annotations().destructiveHint());
    }

    @Test
    void testBuildToolWriteCapability() {
        McpSchema.Tool tool = McpToolTranslator.buildTool("book_flight", writeDecl(), false);

        assertEquals("book_flight", tool.name());
        assertFalse(tool.annotations().readOnlyHint());
        assertTrue(tool.annotations().destructiveHint());
    }

    // --- Input schema ---

    @Test
    void testInputSchema() {
        McpSchema.JsonSchema schema = McpToolTranslator.buildInputSchema(readDecl());

        assertEquals("object", schema.type());
        assertNotNull(schema.properties());
        assertEquals(3, schema.properties().size());

        // Check required fields.
        assertNotNull(schema.required());
        assertTrue(schema.required().contains("origin"));
        assertTrue(schema.required().contains("destination"));
        assertFalse(schema.required().contains("max_results"));
    }

    // --- Enriched descriptions ---

    @Test
    void testEnrichDescriptionRead() {
        String desc = McpToolTranslator.enrichDescription(readDecl());

        assertTrue(desc.contains("Search for flights"));
        assertTrue(desc.contains("Read-only, no side effects"));
        assertTrue(desc.contains("Delegation scope: travel"));
    }

    @Test
    void testEnrichDescriptionIrreversible() {
        String desc = McpToolTranslator.enrichDescription(writeDecl());

        assertTrue(desc.contains("Book a flight"));
        assertTrue(desc.contains("IRREVERSIBLE"));
        assertTrue(desc.contains("No rollback window"));
        assertTrue(desc.contains("Estimated cost: USD 100-500"));
        assertTrue(desc.contains("Requires calling first: search_flights"));
        assertTrue(desc.contains("Delegation scope: travel, finance"));
    }

    // --- Response translation ---

    @Test
    void testTranslateSuccessResponse() {
        Map<String, Object> response = Map.of(
                "success", true,
                "result", Map.of("flights", List.of(Map.of("id", "FL-001")))
        );

        McpToolTranslator.McpInvokeResult result = McpToolTranslator.translateResponse(response);

        assertFalse(result.isError());
        assertTrue(result.text().contains("FL-001"));
    }

    @Test
    void testTranslateFailureResponse() {
        Map<String, Object> response = Map.of(
                "success", false,
                "failure", Map.of(
                        "type", "scope_insufficient",
                        "detail", "Missing travel scope",
                        "retry", false
                )
        );

        McpToolTranslator.McpInvokeResult result = McpToolTranslator.translateResponse(response);

        assertTrue(result.isError());
        assertTrue(result.text().contains("FAILED: scope_insufficient"));
        assertTrue(result.text().contains("Missing travel scope"));
        assertTrue(result.text().contains("Retryable: no"));
    }
}
