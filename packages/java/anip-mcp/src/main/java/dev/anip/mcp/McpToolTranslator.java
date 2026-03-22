package dev.anip.mcp;

import com.fasterxml.jackson.databind.ObjectMapper;

import dev.anip.core.CapabilityDeclaration;
import dev.anip.core.CapabilityInput;
import dev.anip.core.CapabilityRequirement;

import io.modelcontextprotocol.spec.McpSchema;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Translates ANIP capabilities to MCP tools with JSON Schema inputs
 * and enriched descriptions.
 */
public class McpToolTranslator {

    private static final Map<String, String> TYPE_MAP = Map.of(
            "string", "string",
            "integer", "integer",
            "number", "number",
            "boolean", "boolean",
            "date", "string",
            "airport_code", "string"
    );

    private McpToolTranslator() {}

    /**
     * Builds an MCP tool from an ANIP capability declaration.
     */
    public static McpSchema.Tool buildTool(String name, CapabilityDeclaration decl,
                                            boolean enrichDescriptions) {
        String description = enrichDescriptions
                ? enrichDescription(decl) : decl.getDescription();

        McpSchema.JsonSchema inputSchema = buildInputSchema(decl);

        boolean readOnly = decl.getSideEffect() != null
                && "read".equals(decl.getSideEffect().getType());
        boolean destructive = decl.getSideEffect() != null
                && "irreversible".equals(decl.getSideEffect().getType());

        McpSchema.ToolAnnotations annotations = new McpSchema.ToolAnnotations(
                null, readOnly, destructive, null, null, null
        );

        return new McpSchema.Tool(name, null, description, inputSchema,
                null, annotations, null);
    }

    /**
     * Converts capability inputs to MCP JSON Schema.
     */
    public static McpSchema.JsonSchema buildInputSchema(CapabilityDeclaration decl) {
        Map<String, Object> properties = new LinkedHashMap<>();
        List<String> required = new ArrayList<>();

        if (decl.getInputs() != null) {
            for (CapabilityInput input : decl.getInputs()) {
                String jsonType = TYPE_MAP.getOrDefault(input.getType(), "string");

                Map<String, Object> prop = new LinkedHashMap<>();
                prop.put("type", jsonType);
                if (input.getDescription() != null) {
                    prop.put("description", input.getDescription());
                }
                if ("date".equals(input.getType())) {
                    prop.put("format", "date");
                }
                if (input.getDefaultValue() != null) {
                    prop.put("default", input.getDefaultValue());
                }

                properties.put(input.getName(), prop);

                if (input.isRequired()) {
                    required.add(input.getName());
                }
            }
        }

        return new McpSchema.JsonSchema(
                "object", properties,
                required.isEmpty() ? null : required,
                null, null, null
        );
    }

    /**
     * Builds an enriched description with ANIP metadata.
     */
    @SuppressWarnings("unchecked")
    public static String enrichDescription(CapabilityDeclaration decl) {
        List<String> parts = new ArrayList<>();
        parts.add(decl.getDescription());

        if (decl.getSideEffect() != null) {
            String seType = decl.getSideEffect().getType();
            switch (seType) {
                case "irreversible" -> {
                    parts.add("WARNING: IRREVERSIBLE action — cannot be undone.");
                    if ("none".equals(decl.getSideEffect().getRollbackWindow())) {
                        parts.add("No rollback window.");
                    }
                }
                case "write" -> {
                    String rbw = decl.getSideEffect().getRollbackWindow();
                    if (rbw != null && !"none".equals(rbw) && !"not_applicable".equals(rbw)) {
                        parts.add("Reversible within " + rbw + ".");
                    }
                }
                case "read" -> parts.add("Read-only, no side effects.");
            }
        }

        if (decl.getCost() != null) {
            String certainty = decl.getCost().getCertainty();
            Map<String, Object> financial = decl.getCost().getFinancial();

            if ("fixed".equals(certainty) && financial != null) {
                Object amount = financial.get("amount");
                String currency = financial.get("currency") != null
                        ? (String) financial.get("currency") : "USD";
                if (amount != null) {
                    parts.add("Cost: " + currency + " " + amount + " (fixed).");
                }
            } else if ("estimated".equals(certainty) && financial != null) {
                String currency = financial.get("currency") != null
                        ? (String) financial.get("currency") : "USD";
                Object rangeMin = financial.get("range_min");
                Object rangeMax = financial.get("range_max");
                if (rangeMin == null || rangeMax == null) {
                    Object estRange = financial.get("estimated_range");
                    if (estRange instanceof Map) {
                        Map<String, Object> range = (Map<String, Object>) estRange;
                        rangeMin = range.get("min");
                        rangeMax = range.get("max");
                    }
                }
                if (rangeMin != null && rangeMax != null) {
                    parts.add("Estimated cost: " + currency + " " + rangeMin + "-" + rangeMax + ".");
                }
            }
        }

        if (decl.getRequires() != null && !decl.getRequires().isEmpty()) {
            List<String> prereqs = new ArrayList<>();
            for (CapabilityRequirement r : decl.getRequires()) {
                prereqs.add(r.getCapability());
            }
            parts.add("Requires calling first: " + String.join(", ", prereqs) + ".");
        }

        if (decl.getMinimumScope() != null && !decl.getMinimumScope().isEmpty()) {
            parts.add("Delegation scope: " + String.join(", ", decl.getMinimumScope()) + ".");
        }

        return String.join(" ", parts);
    }

    /**
     * Translates an ANIP invoke result to MCP text result.
     */
    @SuppressWarnings("unchecked")
    public static McpInvokeResult translateResponse(Map<String, Object> response) {
        boolean success = Boolean.TRUE.equals(response.get("success"));

        if (success) {
            Object result = response.get("result");
            String text;
            try {
                ObjectMapper mapper = new ObjectMapper();
                text = mapper.writerWithDefaultPrettyPrinter().writeValueAsString(result);
            } catch (Exception e) {
                text = String.valueOf(result);
            }

            // Append cost annotation if present.
            Object costActualRaw = response.get("cost_actual");
            if (costActualRaw instanceof Map) {
                Map<String, Object> costMap = (Map<String, Object>) costActualRaw;
                Object financialRaw = costMap.get("financial");
                if (financialRaw instanceof Map) {
                    Map<String, Object> financial = (Map<String, Object>) financialRaw;
                    Object amount = financial.get("amount");
                    String currency = financial.get("currency") != null
                            ? (String) financial.get("currency") : "USD";
                    if (amount != null) {
                        text += "\n[Cost: " + currency + " " + amount + "]";
                    }
                }
            }

            return new McpInvokeResult(text, false);
        }

        // Failure path.
        Object failureRaw = response.get("failure");
        if (!(failureRaw instanceof Map)) {
            return new McpInvokeResult(
                    "FAILED: unknown\nDetail: no detail\nRetryable: no", true);
        }

        Map<String, Object> failure = (Map<String, Object>) failureRaw;
        String failType = failure.get("type") != null ? (String) failure.get("type") : "unknown";
        String detail = failure.get("detail") != null ? (String) failure.get("detail") : "no detail";

        List<String> textParts = new ArrayList<>();
        textParts.add("FAILED: " + failType);
        textParts.add("Detail: " + detail);

        Object resRaw = failure.get("resolution");
        if (resRaw instanceof Map) {
            Map<String, Object> res = (Map<String, Object>) resRaw;
            String action = (String) res.get("action");
            if (action != null && !action.isEmpty()) {
                textParts.add("Resolution: " + action);
            }
            String requires = (String) res.get("requires");
            if (requires != null && !requires.isEmpty()) {
                textParts.add("Requires: " + requires);
            }
        }

        boolean retry = Boolean.TRUE.equals(failure.get("retry"));
        textParts.add(retry ? "Retryable: yes" : "Retryable: no");

        return new McpInvokeResult(String.join("\n", textParts), true);
    }

    /**
     * Result of an MCP tool invocation.
     */
    public record McpInvokeResult(String text, boolean isError) {}
}
