package dev.anip.graphql;

import dev.anip.core.ANIPError;
import dev.anip.core.CapabilityDeclaration;
import dev.anip.core.CapabilityInput;
import dev.anip.core.CapabilityRequirement;
import dev.anip.core.Constants;
import dev.anip.core.DelegationToken;
import dev.anip.service.ANIPService;
import dev.anip.service.InvokeOpts;

import graphql.schema.DataFetcher;
import graphql.schema.DataFetchingEnvironment;
import graphql.schema.GraphQLArgument;
import graphql.schema.GraphQLFieldDefinition;
import graphql.schema.GraphQLInputType;
import graphql.schema.GraphQLNonNull;
import graphql.schema.GraphQLObjectType;
import graphql.schema.GraphQLOutputType;
import graphql.schema.GraphQLSchema;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

import static graphql.Scalars.*;
import static graphql.schema.GraphQLFieldDefinition.newFieldDefinition;
import static graphql.schema.GraphQLObjectType.newObject;
import static graphql.schema.GraphQLNonNull.nonNull;

/**
 * Builds a graphql-java schema at runtime from ANIP capabilities.
 * Query for read, Mutation for write. CamelCase field names.
 */
public class SchemaBuilder {

    private SchemaBuilder() {}

    /**
     * Maps an ANIP type name to a GraphQL output type.
     */
    public static GraphQLOutputType anipTypeToGraphQL(String anipType) {
        return switch (anipType) {
            case "string", "date", "airport_code" -> GraphQLString;
            case "integer" -> GraphQLInt;
            case "number" -> GraphQLFloat;
            case "boolean" -> GraphQLBoolean;
            default -> ExtendedScalars.JSON;
        };
    }

    /**
     * Maps an ANIP type name to a GraphQL type name string (for SDL).
     */
    public static String anipTypeToGraphQLName(String anipType) {
        return switch (anipType) {
            case "string", "date", "airport_code" -> "String";
            case "integer" -> "Int";
            case "number" -> "Float";
            case "boolean" -> "Boolean";
            default -> "JSON";
        };
    }

    /**
     * Builds an executable GraphQLSchema from the service's capabilities.
     */
    @SuppressWarnings("unchecked")
    public static SchemaResult buildSchema(ANIPService service) {
        Map<String, Object> manifest = (Map<String, Object>) service.getManifest();
        Map<String, Object> capabilities = (Map<String, Object>) manifest.get("capabilities");

        // Sorted for deterministic output.
        List<String> capNames = new ArrayList<>(new TreeMap<>(capabilities).keySet());

        // Shared types.
        GraphQLObjectType financialCostType = newObject()
                .name("FinancialCost")
                .field(newFieldDefinition().name("amount").type(GraphQLFloat))
                .field(newFieldDefinition().name("currency").type(GraphQLString))
                .build();

        GraphQLObjectType costActualType = newObject()
                .name("CostActual")
                .field(newFieldDefinition().name("financial").type(financialCostType))
                .field(newFieldDefinition().name("varianceFromEstimate").type(GraphQLString))
                .build();

        GraphQLObjectType resolutionType = newObject()
                .name("Resolution")
                .field(newFieldDefinition().name("action").type(nonNull(GraphQLString)))
                .field(newFieldDefinition().name("recoveryClass").type(nonNull(GraphQLString)))
                .field(newFieldDefinition().name("requires").type(GraphQLString))
                .field(newFieldDefinition().name("grantableBy").type(GraphQLString))
                .build();

        GraphQLObjectType anipFailureType = newObject()
                .name("ANIPFailure")
                .field(newFieldDefinition().name("type").type(nonNull(GraphQLString)))
                .field(newFieldDefinition().name("detail").type(nonNull(GraphQLString)))
                .field(newFieldDefinition().name("resolution").type(resolutionType))
                .field(newFieldDefinition().name("retry").type(nonNull(GraphQLBoolean)))
                .build();

        List<GraphQLFieldDefinition> queryFields = new ArrayList<>();
        List<GraphQLFieldDefinition> mutationFields = new ArrayList<>();

        for (String name : capNames) {
            CapabilityDeclaration decl = service.getCapabilityDeclaration(name);
            if (decl == null) continue;

            String pascal = GraphQLResponseMapper.toPascalCase(name);
            String camel = GraphQLResponseMapper.toCamelCase(name);

            GraphQLObjectType resultType = newObject()
                    .name(pascal + "Result")
                    .field(newFieldDefinition().name("success").type(nonNull(GraphQLBoolean)))
                    .field(newFieldDefinition().name("result").type(ExtendedScalars.JSON))
                    .field(newFieldDefinition().name("costActual").type(costActualType))
                    .field(newFieldDefinition().name("failure").type(anipFailureType))
                    .build();

            // Build args.
            List<GraphQLArgument> args = new ArrayList<>();
            if (decl.getInputs() != null) {
                for (CapabilityInput inp : decl.getInputs()) {
                    String argName = GraphQLResponseMapper.toCamelCase(inp.getName());
                    GraphQLOutputType gqlType = anipTypeToGraphQL(inp.getType());
                    GraphQLInputType inputType = inp.isRequired()
                            ? GraphQLNonNull.nonNull((GraphQLInputType) gqlType)
                            : (GraphQLInputType) gqlType;
                    args.add(GraphQLArgument.newArgument()
                            .name(argName)
                            .type(inputType)
                            .build());
                }
            }

            DataFetcher<?> fetcher = makeResolver(service, name);

            GraphQLFieldDefinition.Builder fieldBuilder = newFieldDefinition()
                    .name(camel)
                    .type(nonNull(resultType))
                    .dataFetcher(fetcher);
            for (GraphQLArgument arg : args) {
                fieldBuilder.argument(arg);
            }

            GraphQLFieldDefinition field = fieldBuilder.build();

            String seType = decl.getSideEffect() != null ? decl.getSideEffect().getType() : "";
            if (seType.isEmpty() || "read".equals(seType)) {
                queryFields.add(field);
            } else {
                mutationFields.add(field);
            }
        }

        // Build schema.
        GraphQLSchema.Builder schemaBuilder = GraphQLSchema.newSchema();

        if (!queryFields.isEmpty()) {
            GraphQLObjectType.Builder queryBuilder = newObject().name("Query");
            for (GraphQLFieldDefinition f : queryFields) {
                queryBuilder.field(f);
            }
            schemaBuilder.query(queryBuilder.build());
        } else {
            // graphql-java requires a Query type; add a dummy.
            schemaBuilder.query(newObject().name("Query")
                    .field(newFieldDefinition().name("_empty").type(GraphQLString)
                            .dataFetcher(env -> null))
                    .build());
        }

        if (!mutationFields.isEmpty()) {
            GraphQLObjectType.Builder mutationBuilder = newObject().name("Mutation");
            for (GraphQLFieldDefinition f : mutationFields) {
                mutationBuilder.field(f);
            }
            schemaBuilder.mutation(mutationBuilder.build());
        }

        GraphQLSchema schema = schemaBuilder.build();
        String sdl = generateSDL(service, capNames);

        return new SchemaResult(schema, sdl);
    }

    /**
     * Creates a data fetcher for a given capability.
     */
    private static DataFetcher<Map<String, Object>> makeResolver(ANIPService service,
                                                                    String capName) {
        return (DataFetchingEnvironment env) -> {
            // Extract auth header from context.
            String authHeader = env.getGraphQlContext().get("authHeader");
            String bearer = extractBearer(authHeader);

            if (bearer == null || bearer.isEmpty()) {
                return GraphQLResponseMapper.buildGraphQLResponse(Map.of(
                        "success", false,
                        "failure", Map.of(
                                "type", Constants.FAILURE_AUTH_REQUIRED,
                                "detail", "Authorization header required",
                                "resolution", Map.of("action", "provide_credentials", "recovery_class", Constants.recoveryClassForAction("provide_credentials")),
                                "retry", true
                        )
                ));
            }

            DelegationToken token;
            try {
                token = GraphQLAuthBridge.resolveAuth(bearer, service, capName);
            } catch (ANIPError e) {
                Map<String, Object> failure = new LinkedHashMap<>();
                failure.put("type", e.getErrorType());
                failure.put("detail", e.getDetail());
                failure.put("retry", e.isRetry());
                if (e.getResolution() != null) {
                    failure.put("resolution", Map.of(
                            "action", e.getResolution().getAction(),
                            "recovery_class", e.getResolution().getRecoveryClass() != null
                                    ? e.getResolution().getRecoveryClass()
                                    : Constants.recoveryClassForAction(e.getResolution().getAction())
                    ));
                }
                return GraphQLResponseMapper.buildGraphQLResponse(Map.of(
                        "success", false,
                        "failure", failure
                ));
            } catch (Exception e) {
                return GraphQLResponseMapper.buildGraphQLResponse(Map.of(
                        "success", false,
                        "failure", Map.of(
                                "type", Constants.FAILURE_INTERNAL_ERROR,
                                "detail", "Authentication failed",
                                "retry", false
                        )
                ));
            }

            // Convert camelCase args to snake_case.
            Map<String, Object> snakeArgs = new LinkedHashMap<>();
            for (Map.Entry<String, Object> entry : env.getArguments().entrySet()) {
                snakeArgs.put(GraphQLResponseMapper.toSnakeCase(entry.getKey()), entry.getValue());
            }

            Map<String, Object> result = service.invoke(capName, token, snakeArgs,
                    new InvokeOpts());

            return GraphQLResponseMapper.buildGraphQLResponse(result);
        };
    }

    private static String extractBearer(String authHeader) {
        if (authHeader != null && authHeader.startsWith("Bearer ")) {
            return authHeader.substring(7).trim();
        }
        return null;
    }

    /**
     * Generates SDL text including custom @anip* directives.
     */
    private static String generateSDL(ANIPService service, List<String> capNames) {
        List<String> lines = new ArrayList<>();

        // Directives.
        lines.add("directive @anipSideEffect(type: String!, rollbackWindow: String) on FIELD_DEFINITION");
        lines.add("directive @anipCost(certainty: String!, currency: String, rangeMin: Float, rangeMax: Float) on FIELD_DEFINITION");
        lines.add("directive @anipRequires(capabilities: [String!]!) on FIELD_DEFINITION");
        lines.add("directive @anipScope(scopes: [String!]!) on FIELD_DEFINITION");
        lines.add("");
        lines.add("scalar JSON");
        lines.add("");

        // Shared types.
        lines.add("type CostActual { financial: FinancialCost, varianceFromEstimate: String }");
        lines.add("type FinancialCost { amount: Float, currency: String }");
        lines.add("type ANIPFailure { type: String!, detail: String!, resolution: Resolution, retry: Boolean! }");
        lines.add("type Resolution { action: String!, recoveryClass: String!, requires: String, grantableBy: String }");
        lines.add("type RestrictedCapability { capability: String!, reason: String!, reasonType: String!, grantableBy: String!, unmetTokenRequirements: [String!]!, resolutionHint: String }");
        lines.add("type DeniedCapability { capability: String!, reason: String!, reasonType: String! }");
        lines.add("");

        List<String> queries = new ArrayList<>();
        List<String> mutations = new ArrayList<>();

        for (String name : capNames) {
            CapabilityDeclaration decl = service.getCapabilityDeclaration(name);
            if (decl == null) continue;

            String pascal = GraphQLResponseMapper.toPascalCase(name);
            String camel = GraphQLResponseMapper.toCamelCase(name);

            // Result type.
            lines.add("type " + pascal + "Result { success: Boolean!, result: JSON, costActual: CostActual, failure: ANIPFailure }");

            String argsStr = buildSDLArgs(decl);
            String dirStr = buildSDLDirectives(decl);

            String fieldLine = "  " + camel + argsStr + ": " + pascal + "Result! " + dirStr;

            String seType = decl.getSideEffect() != null ? decl.getSideEffect().getType() : "";
            if (seType.isEmpty() || "read".equals(seType)) {
                queries.add(fieldLine);
            } else {
                mutations.add(fieldLine);
            }
        }

        lines.add("");
        if (!queries.isEmpty()) {
            lines.add("type Query {");
            lines.addAll(queries);
            lines.add("}");
        }
        if (!mutations.isEmpty()) {
            lines.add("type Mutation {");
            lines.addAll(mutations);
            lines.add("}");
        }

        return String.join("\n", lines);
    }

    private static String buildSDLArgs(CapabilityDeclaration decl) {
        if (decl.getInputs() == null || decl.getInputs().isEmpty()) {
            return "";
        }
        List<String> args = new ArrayList<>();
        for (CapabilityInput inp : decl.getInputs()) {
            String argName = GraphQLResponseMapper.toCamelCase(inp.getName());
            String gqlType = anipTypeToGraphQLName(inp.getType());
            if (inp.isRequired()) {
                gqlType += "!";
            }
            args.add(argName + ": " + gqlType);
        }
        return "(" + String.join(", ", args) + ")";
    }

    @SuppressWarnings("unchecked")
    private static String buildSDLDirectives(CapabilityDeclaration decl) {
        List<String> parts = new ArrayList<>();

        // @anipSideEffect
        String seType = decl.getSideEffect() != null ? decl.getSideEffect().getType() : "";
        if (seType.isEmpty()) seType = "read";
        StringBuilder seDir = new StringBuilder("@anipSideEffect(type: \"" + seType + "\"");
        if (decl.getSideEffect() != null && decl.getSideEffect().getRollbackWindow() != null
                && !decl.getSideEffect().getRollbackWindow().isEmpty()) {
            seDir.append(", rollbackWindow: \"").append(decl.getSideEffect().getRollbackWindow()).append("\"");
        }
        seDir.append(")");
        parts.add(seDir.toString());

        // @anipCost
        if (decl.getCost() != null) {
            String certainty = decl.getCost().getCertainty();
            if (certainty == null || certainty.isEmpty()) certainty = "estimate";
            StringBuilder costDir = new StringBuilder("@anipCost(certainty: \"" + certainty + "\"");
            if (decl.getCost().getFinancial() != null) {
                String currency = decl.getCost().getFinancial().getCurrency();
                if (currency != null) {
                    costDir.append(", currency: \"").append(currency).append("\"");
                }
                Double rangeMin = decl.getCost().getFinancial().getRangeMin();
                Double rangeMax = decl.getCost().getFinancial().getRangeMax();
                if (rangeMin != null) {
                    costDir.append(", rangeMin: ").append(rangeMin);
                }
                if (rangeMax != null) {
                    costDir.append(", rangeMax: ").append(rangeMax);
                }
            }
            costDir.append(")");
            parts.add(costDir.toString());
        }

        // @anipRequires
        if (decl.getRequires() != null && !decl.getRequires().isEmpty()) {
            List<String> capNames = new ArrayList<>();
            for (CapabilityRequirement r : decl.getRequires()) {
                capNames.add("\"" + r.getCapability() + "\"");
            }
            parts.add("@anipRequires(capabilities: [" + String.join(", ", capNames) + "])");
        }

        // @anipScope
        if (decl.getMinimumScope() != null && !decl.getMinimumScope().isEmpty()) {
            List<String> scopeVals = new ArrayList<>();
            for (String s : decl.getMinimumScope()) {
                scopeVals.add("\"" + s + "\"");
            }
            parts.add("@anipScope(scopes: [" + String.join(", ", scopeVals) + "])");
        }

        return String.join(" ", parts);
    }

    /**
     * Result of building the schema: executable schema + SDL text.
     */
    public record SchemaResult(GraphQLSchema schema, String sdl) {}
}
