package dev.anip.server;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.module.paramnames.ParameterNamesModule;

import java.util.Map;
import java.util.TreeMap;

/**
 * Shared Jackson ObjectMapper configured for ANIP wire format (snake_case).
 */
final class JsonHelper {

    static final ObjectMapper MAPPER = new ObjectMapper()
            .registerModule(new ParameterNamesModule())
            .setPropertyNamingStrategy(PropertyNamingStrategies.SNAKE_CASE)
            .setSerializationInclusion(JsonInclude.Include.NON_NULL)
            .configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false)
            .configure(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS, false);

    private JsonHelper() {}

    /**
     * Serialize an object to JSON string.
     */
    static String toJson(Object obj) {
        try {
            return MAPPER.writeValueAsString(obj);
        } catch (JsonProcessingException e) {
            throw new RuntimeException("JSON serialization failed", e);
        }
    }

    /**
     * Deserialize a JSON string to the given type.
     */
    static <T> T fromJson(String json, Class<T> type) {
        try {
            return MAPPER.readValue(json, type);
        } catch (JsonProcessingException e) {
            throw new RuntimeException("JSON deserialization failed: " + e.getMessage(), e);
        }
    }

    /**
     * Convert an object to a Map (for signing, hashing, etc.).
     */
    @SuppressWarnings("unchecked")
    static Map<String, Object> toMap(Object obj) {
        return MAPPER.convertValue(obj, Map.class);
    }

    /**
     * Computes a canonical JSON representation: sorted keys, no null values.
     * This matches the Go/Python canonical form used for hash chain and Merkle tree.
     */
    static String canonicalJson(Map<String, Object> map) {
        TreeMap<String, Object> sorted = new TreeMap<>(map);
        try {
            return MAPPER.writeValueAsString(sorted);
        } catch (JsonProcessingException e) {
            throw new RuntimeException("Canonical JSON serialization failed", e);
        }
    }
}
