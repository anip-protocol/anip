package dev.anip.graphql.spring;

import com.fasterxml.jackson.databind.ObjectMapper;

import dev.anip.graphql.SchemaBuilder;
import dev.anip.service.ANIPService;

import graphql.ExecutionInput;
import graphql.ExecutionResult;
import graphql.GraphQL;

import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import jakarta.servlet.http.HttpServletRequest;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * GraphQL controller for ANIP capabilities.
 * POST /graphql: execute query/mutation
 * GET /graphql: playground HTML
 * GET /schema.graphql: SDL text
 */
@RestController
public class AnipGraphQLController {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    private final GraphQL graphQL;
    private final String sdlText;

    public AnipGraphQLController(ANIPService service) {
        SchemaBuilder.SchemaResult schemaResult = SchemaBuilder.buildSchema(service);
        this.graphQL = GraphQL.newGraphQL(schemaResult.schema()).build();
        this.sdlText = schemaResult.sdl();
    }

    @PostMapping(value = "/graphql", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<Object> executeGraphQL(@RequestBody Map<String, Object> body,
                                                   HttpServletRequest request) {
        String query = (String) body.get("query");
        @SuppressWarnings("unchecked")
        Map<String, Object> variables = (Map<String, Object>) body.get("variables");
        String operationName = (String) body.get("operationName");

        if (query == null || query.isEmpty()) {
            return ResponseEntity.ok(Map.of(
                    "errors", List.of(Map.of("message", "Missing query"))
            ));
        }

        // Inject auth header into GraphQL context.
        String authHeader = request.getHeader("Authorization");
        String finalAuthHeader = authHeader != null ? authHeader : "";

        ExecutionInput.Builder execBuilder = ExecutionInput.newExecutionInput()
                .query(query)
                .graphQLContext(builder -> builder.of("authHeader", finalAuthHeader));

        if (variables != null) {
            execBuilder.variables(variables);
        }
        if (operationName != null) {
            execBuilder.operationName(operationName);
        }

        ExecutionResult result = graphQL.execute(execBuilder.build());

        Map<String, Object> response = new LinkedHashMap<>();
        if (result.getData() != null) {
            response.put("data", result.getData());
        }
        if (result.getErrors() != null && !result.getErrors().isEmpty()) {
            response.put("errors", result.getErrors().stream()
                    .map(e -> Map.of("message", e.getMessage()))
                    .toList());
        }

        // Always return 200 for GraphQL (errors in body, not HTTP status).
        return ResponseEntity.ok(response);
    }

    @GetMapping(value = "/graphql", produces = MediaType.TEXT_HTML_VALUE)
    public ResponseEntity<String> playground() {
        String html = """
                <!DOCTYPE html>
                <html><head><title>ANIP GraphQL</title></head><body>
                <h2>ANIP GraphQL Playground</h2>
                <textarea id="q" rows="10" cols="60">{ }</textarea><br>
                <button onclick="run()">Run</button><pre id="r"></pre>
                <script>
                async function run() {
                  const r = await fetch("/graphql", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({query: document.getElementById("q").value})
                  });
                  document.getElementById("r").textContent = JSON.stringify(await r.json(), null, 2);
                }
                </script></body></html>""";
        return ResponseEntity.ok(html);
    }

    @GetMapping(value = "/schema.graphql", produces = "text/plain")
    public ResponseEntity<String> schema() {
        return ResponseEntity.ok(sdlText);
    }
}
