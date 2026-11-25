package dev.anip.server;

import com.fasterxml.jackson.core.JsonGenerator;
import com.fasterxml.jackson.core.JsonParser;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.DeserializationContext;
import com.fasterxml.jackson.databind.JsonDeserializer;
import com.fasterxml.jackson.databind.JsonSerializer;
import com.fasterxml.jackson.databind.SerializerProvider;
import com.fasterxml.jackson.databind.module.SimpleModule;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;

import dev.anip.core.CapabilityInput;
import dev.anip.core.InputMeaning;
import dev.anip.core.InputResolution;
import dev.anip.core.ResolutionBehavior;
import dev.anip.core.ResolutionMode;

import java.io.IOException;
import java.util.List;

/**
 * Jackson module that binds v0.24 input-resolution enum wire format.
 *
 * <p>{@code anip-core} keeps the enum types JSON-stack-agnostic (no Jackson
 * annotations). This module bridges the protocol wire format
 * (snake_case strings like {@code "backend_resolved"}) to/from
 * {@link ResolutionMode} and {@link ResolutionBehavior} via the
 * {@code wire()} / {@code fromWire(String)} contract on each enum.
 *
 * <p>Transport modules ({@code anip-server}, {@code anip-service},
 * {@code anip-spring-boot}, {@code anip-quarkus}, {@code anip-stdio}, etc.)
 * MUST register this module on every {@link com.fasterxml.jackson.databind.ObjectMapper}
 * they configure for the ANIP wire format.
 */
public final class AnipJacksonModule extends SimpleModule {

    public AnipJacksonModule() {
        super("anip-jackson");
        addSerializer(ResolutionMode.class, new ResolutionModeSerializer());
        addDeserializer(ResolutionMode.class, new ResolutionModeDeserializer());
        addSerializer(ResolutionBehavior.class, new ResolutionBehaviorSerializer());
        addDeserializer(ResolutionBehavior.class, new ResolutionBehaviorDeserializer());
        addDeserializer(CapabilityInput.class, new CapabilityInputDeserializer());
    }

    /**
     * Decodes a declared capability input from its wire form (a manifest, a
     * service definition, a registry package). SPEC.md §4.1: an input whose
     * declaration does not state {@code required} is required.
     */
    static final class CapabilityInputDeserializer extends JsonDeserializer<CapabilityInput> {
        private static final TypeReference<List<String>> STRINGS = new TypeReference<>() { };
        private static final TypeReference<List<InputMeaning>> MEANINGS = new TypeReference<>() { };

        @Override
        public CapabilityInput deserialize(JsonParser p, DeserializationContext ctxt) throws IOException {
            JsonNode node = p.getCodec().readTree(p);
            if (node == null || !node.isObject()) {
                return (CapabilityInput) ctxt.handleUnexpectedToken(CapabilityInput.class, p);
            }
            JsonNode required = node.get("required");
            return new CapabilityInput(
                    text(node, "name"),
                    text(node, "type"),
                    required == null || required.isNull() || required.asBoolean(true),
                    present(node, "default") ? p.getCodec().treeToValue(node.get("default"), Object.class) : null,
                    text(node, "description"),
                    text(node, "semantic_type"),
                    present(node, "entity_reference") && node.get("entity_reference").asBoolean(false),
                    present(node, "allowed_values")
                            ? p.getCodec().readValue(p.getCodec().treeAsTokens(node.get("allowed_values")), STRINGS)
                            : null,
                    text(node, "catalog_ref"),
                    present(node, "input_meanings")
                            ? p.getCodec().readValue(p.getCodec().treeAsTokens(node.get("input_meanings")), MEANINGS)
                            : null,
                    present(node, "resolution")
                            ? p.getCodec().treeToValue(node.get("resolution"), InputResolution.class)
                            : null);
        }

        private static boolean present(JsonNode node, String field) {
            return node.hasNonNull(field);
        }

        private static String text(JsonNode node, String field) {
            return present(node, field) ? node.get(field).asText() : null;
        }
    }

    static final class ResolutionModeSerializer extends JsonSerializer<ResolutionMode> {
        @Override
        public void serialize(ResolutionMode value, JsonGenerator gen, SerializerProvider serializers) throws IOException {
            gen.writeString(value.wire());
        }
    }

    static final class ResolutionModeDeserializer extends JsonDeserializer<ResolutionMode> {
        @Override
        public ResolutionMode deserialize(JsonParser p, DeserializationContext ctxt) throws IOException, JsonProcessingException {
            String wire = p.getValueAsString();
            try {
                return ResolutionMode.fromWire(wire);
            } catch (IllegalArgumentException e) {
                throw ctxt.weirdStringException(wire, ResolutionMode.class, e.getMessage());
            }
        }
    }

    static final class ResolutionBehaviorSerializer extends JsonSerializer<ResolutionBehavior> {
        @Override
        public void serialize(ResolutionBehavior value, JsonGenerator gen, SerializerProvider serializers) throws IOException {
            gen.writeString(value.wire());
        }
    }

    static final class ResolutionBehaviorDeserializer extends JsonDeserializer<ResolutionBehavior> {
        @Override
        public ResolutionBehavior deserialize(JsonParser p, DeserializationContext ctxt) throws IOException, JsonProcessingException {
            String wire = p.getValueAsString();
            try {
                return ResolutionBehavior.fromWire(wire);
            } catch (IllegalArgumentException e) {
                throw ctxt.weirdStringException(wire, ResolutionBehavior.class, e.getMessage());
            }
        }
    }
}
