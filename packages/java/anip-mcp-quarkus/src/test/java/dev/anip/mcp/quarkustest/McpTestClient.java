package dev.anip.mcp.quarkustest;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * The smallest MCP Streamable HTTP client the transport tests need: JSON-RPC
 * requests over POST, answered as JSON or as an SSE stream.
 */
final class McpTestClient {

    private static final ObjectMapper JSON = new ObjectMapper();

    // HTTP/1.1: the servlet transport writes a Connection header on its SSE
    // responses, which an HTTP/2 client refuses.
    private final HttpClient http = HttpClient.newBuilder()
            .version(HttpClient.Version.HTTP_1_1)
            .build();
    private final URI endpoint;
    private final String bearer;
    private String session;
    private int nextId = 1;

    McpTestClient(String endpoint, String bearer) {
        this.endpoint = URI.create(endpoint);
        this.bearer = bearer;
    }

    /** Opens a session: initialize, then the initialized notification. */
    McpTestClient initialize() throws Exception {
        Map<String, Object> params = new LinkedHashMap<>();
        params.put("protocolVersion", "2025-03-26");
        params.put("capabilities", Map.of());
        params.put("clientInfo", Map.of("name", "anip-transport-test", "version", "1"));
        JsonNode response = request("initialize", params);
        if (response.get("result") == null) {
            throw new IllegalStateException("initialize failed: " + response);
        }
        post(Map.of("jsonrpc", "2.0", "method", "notifications/initialized"), null);
        return this;
    }

    /** Sends a request and returns the JSON-RPC response message with its id. */
    JsonNode request(String method, Object params) throws Exception {
        int id = nextId++;
        Map<String, Object> message = new LinkedHashMap<>();
        message.put("jsonrpc", "2.0");
        message.put("id", id);
        message.put("method", method);
        message.put("params", params);
        JsonNode response = post(message, id);
        if (response == null) {
            throw new IllegalStateException("no JSON-RPC response to " + method);
        }
        return response;
    }

    /** tools/call: the JSON-RPC response message. */
    JsonNode callTool(String name, Map<String, Object> arguments) throws Exception {
        Map<String, Object> params = new LinkedHashMap<>();
        params.put("name", name);
        if (arguments != null) {
            params.put("arguments", arguments);
        }
        return request("tools/call", params);
    }

    private JsonNode post(Map<String, Object> message, Integer id) throws Exception {
        HttpRequest.Builder builder = HttpRequest.newBuilder(endpoint)
                .header("Content-Type", "application/json")
                .header("Accept", "application/json, text/event-stream")
                .POST(HttpRequest.BodyPublishers.ofString(JSON.writeValueAsString(message), StandardCharsets.UTF_8));
        if (bearer != null) {
            builder.header("Authorization", "Bearer " + bearer);
        }
        if (session != null) {
            builder.header("Mcp-Session-Id", session);
        }
        HttpResponse<String> response = http.send(builder.build(),
                HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
        response.headers().firstValue("Mcp-Session-Id").ifPresent(value -> session = value);
        if (id == null) {
            return null;
        }
        if (response.statusCode() / 100 != 2) {
            throw new IllegalStateException("HTTP " + response.statusCode() + ": " + response.body());
        }
        String contentType = response.headers().firstValue("Content-Type").orElse("");
        if (contentType.startsWith("text/event-stream")) {
            for (String line : response.body().split("\\R")) {
                if (line.startsWith("data:")) {
                    JsonNode node = JSON.readTree(line.substring(5).trim());
                    if (node.has("id") && node.get("id").asInt() == id) {
                        return node;
                    }
                }
            }
            return null;
        }
        return JSON.readTree(response.body());
    }
}
