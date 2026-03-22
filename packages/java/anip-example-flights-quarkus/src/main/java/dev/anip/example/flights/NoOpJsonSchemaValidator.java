package dev.anip.example.flights;

import io.modelcontextprotocol.json.schema.JsonSchemaValidator;
import io.modelcontextprotocol.json.schema.JsonSchemaValidatorSupplier;

import java.util.Map;

/**
 * No-op implementation of the MCP SDK's JsonSchemaValidator SPI.
 * ANIP services validate inputs in their capability handlers,
 * so MCP-level schema validation is unnecessary.
 */
public class NoOpJsonSchemaValidator implements JsonSchemaValidator, JsonSchemaValidatorSupplier {

    @Override
    public ValidationResponse validate(Map<String, Object> schema, Object data) {
        return ValidationResponse.asValid(null);
    }

    @Override
    public JsonSchemaValidator get() {
        return this;
    }
}
