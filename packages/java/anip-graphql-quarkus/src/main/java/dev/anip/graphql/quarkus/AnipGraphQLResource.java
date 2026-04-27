package dev.anip.graphql.quarkus;

import dev.anip.graphql.SchemaBuilder;
import dev.anip.service.ANIPService;

import graphql.ExecutionInput;
import graphql.ExecutionResult;
import graphql.GraphQL;

import jakarta.annotation.PostConstruct;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import jakarta.ws.rs.Consumes;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.HeaderParam;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * JAX-RS resource for ANIP GraphQL capabilities.
 * POST /graphql: execute query/mutation
 * GET /graphql (Accept: text/html): playground HTML
 * GET /schema.graphql: SDL text
 */
@ApplicationScoped
@Path("/")
public class AnipGraphQLResource {

    @Inject
    ANIPService service;

    private GraphQL graphQL;
    private String sdlText;

    @PostConstruct
    void init() {
        SchemaBuilder.SchemaResult schemaResult = SchemaBuilder.buildSchema(service);
        this.graphQL = GraphQL.newGraphQL(schemaResult.schema()).build();
        this.sdlText = schemaResult.sdl();
    }

    @POST
    @Path("/graphql")
    @Consumes(MediaType.APPLICATION_JSON)
    @Produces(MediaType.APPLICATION_JSON)
    public Response executeGraphQL(Map<String, Object> body,
                                   @HeaderParam("Authorization") String authHeader,
                                   @HeaderParam("X-Anip-Approval-Grant") String approvalGrant) {
        String query = (String) body.get("query");
        @SuppressWarnings("unchecked")
        Map<String, Object> variables = (Map<String, Object>) body.get("variables");
        String operationName = (String) body.get("operationName");

        if (query == null || query.isEmpty()) {
            return Response.ok(Map.of(
                    "errors", List.of(Map.of("message", "Missing query"))
            )).build();
        }

        // Inject auth header into GraphQL context.
        String finalAuthHeader = authHeader != null ? authHeader : "";
        // v0.23: GraphQL mutation args ARE the capability args, so
        // approval_grant rides on X-Anip-Approval-Grant alongside the auth
        // header. session_id for session_bound grants is read from the
        // signed token, never the header.
        String finalApprovalGrant = approvalGrant != null ? approvalGrant : "";

        ExecutionInput.Builder execBuilder = ExecutionInput.newExecutionInput()
                .query(query)
                .graphQLContext(builder -> builder
                        .of("authHeader", finalAuthHeader)
                        .of("approvalGrant", finalApprovalGrant));

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
        return Response.ok(response).build();
    }

    @GET
    @Path("/graphql")
    @Produces(MediaType.TEXT_HTML)
    public Response playground() {
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
        return Response.ok(html).build();
    }

    @GET
    @Path("/schema.graphql")
    @Produces("text/plain")
    public Response schema() {
        return Response.ok(sdlText).build();
    }
}
