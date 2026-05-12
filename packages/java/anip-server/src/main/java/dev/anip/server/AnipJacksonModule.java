package dev.anip.server;

import com.fasterxml.jackson.core.JsonGenerator;
import com.fasterxml.jackson.core.JsonParser;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.DeserializationContext;
import com.fasterxml.jackson.databind.JsonDeserializer;
import com.fasterxml.jackson.databind.JsonSerializer;
import com.fasterxml.jackson.databind.SerializerProvider;
import com.fasterxml.jackson.databind.module.SimpleModule;

import dev.anip.core.ResolutionBehavior;
import dev.anip.core.ResolutionMode;

import java.io.IOException;

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
