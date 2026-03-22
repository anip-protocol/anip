package dev.anip.example.flights;

import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.JavaType;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;

import io.modelcontextprotocol.json.McpJsonMapper;
import io.modelcontextprotocol.json.McpJsonMapperSupplier;
import io.modelcontextprotocol.json.TypeRef;

import java.io.IOException;

/**
 * Jackson-based implementation of the MCP SDK's McpJsonMapper SPI.
 */
public class JacksonMcpJsonMapper implements McpJsonMapper, McpJsonMapperSupplier {

    private static final ObjectMapper MAPPER = new ObjectMapper()
            .configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false)
            .configure(SerializationFeature.FAIL_ON_EMPTY_BEANS, false);

    @Override
    public <T> T readValue(String json, Class<T> type) throws IOException {
        return MAPPER.readValue(json, type);
    }

    @Override
    public <T> T readValue(byte[] json, Class<T> type) throws IOException {
        return MAPPER.readValue(json, type);
    }

    @Override
    public <T> T readValue(String json, TypeRef<T> typeRef) throws IOException {
        JavaType javaType = MAPPER.getTypeFactory().constructType(typeRef.getType());
        return MAPPER.readValue(json, javaType);
    }

    @Override
    public <T> T readValue(byte[] json, TypeRef<T> typeRef) throws IOException {
        JavaType javaType = MAPPER.getTypeFactory().constructType(typeRef.getType());
        return MAPPER.readValue(json, javaType);
    }

    @Override
    public <T> T convertValue(Object value, Class<T> type) {
        return MAPPER.convertValue(value, type);
    }

    @Override
    public <T> T convertValue(Object value, TypeRef<T> typeRef) {
        JavaType javaType = MAPPER.getTypeFactory().constructType(typeRef.getType());
        return MAPPER.convertValue(value, javaType);
    }

    @Override
    public String writeValueAsString(Object value) throws IOException {
        return MAPPER.writeValueAsString(value);
    }

    @Override
    public byte[] writeValueAsBytes(Object value) throws IOException {
        return MAPPER.writeValueAsBytes(value);
    }

    @Override
    public McpJsonMapper get() {
        return this;
    }
}
