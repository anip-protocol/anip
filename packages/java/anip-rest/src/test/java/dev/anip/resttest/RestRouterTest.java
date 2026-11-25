package dev.anip.resttest;

import dev.anip.core.*;
import dev.anip.rest.*;
import dev.anip.service.*;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;

@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class RestRouterTest {

    private ANIPService service;

    @BeforeAll
    void setUp() throws Exception {
        service = new ANIPService(new ServiceConfig()
                .setServiceId("test-rest-router")
                .setCapabilities(List.of(
                        new CapabilityDef(
                                new CapabilityDeclaration(
                                        "search", "Search", "1.0",
                                        List.of(new CapabilityInput("q", "string", true, "Query"),
                                                new CapabilityInput("limit", "integer", false, "Limit")),
                                        new CapabilityOutput("object", List.of("results")),
                                        new SideEffect("read", "not_applicable"),
                                        List.of("search"), null, null, null
                                ),
                                (ctx, params) -> Map.of("results", List.of())
                        ),
                        new CapabilityDef(
                                new CapabilityDeclaration(
                                        "create", "Create item", "1.0",
                                        List.of(new CapabilityInput("name", "string", true, "Name")),
                                        new CapabilityOutput("object", List.of("id")),
                                        new SideEffect("write", "none"),
                                        List.of("items.write"), null, null, null
                                ),
                                (ctx, params) -> Map.of("id", "123")
                        )
                ))
                .setStorage(":memory:")
                .setAuthenticate(b -> Optional.empty())
        );
        service.start();
    }

    @Test void readCapabilityGetsGetRoute() {
        List<RestRoute> routes = RestRouter.generateRoutes(service, null);
        RestRoute search = RestRouter.findRoute(routes, "search");
        assertNotNull(search);
        assertEquals("GET", search.getMethod());
        assertEquals("/api/search", search.getPath());
    }

    @Test void writeCapabilityGetsPostRoute() {
        List<RestRoute> routes = RestRouter.generateRoutes(service, null);
        RestRoute create = RestRouter.findRoute(routes, "create");
        assertNotNull(create);
        assertEquals("POST", create.getMethod());
    }

    @Test void overridesApplyToMetadata() {
        Map<String, RouteOverride> overrides = Map.of(
                "search", new RouteOverride("/custom/search", "POST"));
        List<RestRoute> routes = RestRouter.generateRoutes(service, overrides);
        RestRoute search = RestRouter.findRoute(routes, "search");
        assertEquals("/custom/search", search.getPath());
        assertEquals("POST", search.getMethod());
    }

    @Test void convertQueryParamsTypes() {
        CapabilityDeclaration decl = service.getCapabilityDeclaration("search");
        Map<String, String[]> raw = Map.of(
                "q", new String[]{"flights"},
                "limit", new String[]{"10"}
        );
        Map<String, Object> result = RestRouter.convertQueryParams(raw, decl);
        assertEquals("flights", result.get("q"));
        assertEquals(10, result.get("limit"));
    }

    private static CapabilityDeclaration typedDeclaration() {
        return new CapabilityDeclaration("typed", "Typed", "1.0",
                List.of(
                        new CapabilityInput("i", "integer", false, "integer"),
                        new CapabilityInput("n", "number", false, "number"),
                        new CapabilityInput("b", "boolean", false, "boolean"),
                        new CapabilityInput("a", "array", false, "array"),
                        new CapabilityInput("o", "object", false, "object"),
                        new CapabilityInput("s", "string", false, "string"),
                        new CapabilityInput("d", "date", false, "date")),
                new CapabilityOutput("object", List.of()), new SideEffect("read", "not_applicable"),
                List.of("search"), null, null, null);
    }

    private static Map<String, Object> convert(String name, String value) {
        return RestRouter.convertQueryParams(Map.of(name, new String[]{value}), typedDeclaration());
    }

    /**
     * A query value is read as the JSON value its declared type calls for, so
     * that parameter validation (SPEC.md §6.3) sees what a JSON body would carry.
     */
    @Test void queryValuesAreReadAsTheDeclaredJsonType() {
        assertEquals(10, convert("i", "10").get("i"));
        assertEquals(-3, convert("i", "-3").get("i"));
        assertEquals(5.0, convert("i", "5.0").get("i"));
        assertEquals(100.0, convert("i", "1e2").get("i"));
        assertEquals(9007199254740993L, convert("i", "9007199254740993").get("i"));
        assertEquals(new java.math.BigInteger("123456789012345678901234567890"),
                convert("i", "123456789012345678901234567890").get("i"));
        assertEquals(1.5, convert("n", "1.5").get("n"));
        assertEquals(2, convert("n", "2").get("n"));
        assertEquals(true, convert("b", "true").get("b"));
        assertEquals(false, convert("b", "false").get("b"));
        assertEquals(List.of(1, "x"), convert("a", "[1,\"x\"]").get("a"));
        assertEquals(Map.of("k", List.of(true)), convert("o", "{\"k\":[true]}").get("o"));
        assertEquals("10", convert("s", "10").get("s"));
        assertEquals("2026-03-10", convert("d", "2026-03-10").get("d"));
        assertEquals("true", convert("undeclared", "true").get("undeclared"));
    }

    /** A value that cannot be read as the declared type stays a string and is refused by name. */
    @Test void queryValuesThatDoNotFitTheDeclaredTypeStayStrings() {
        CapabilityDeclaration decl = typedDeclaration();
        Map<String, String> unreadable = new LinkedHashMap<>();
        unreadable.put("i", "many");
        unreadable.put("n", "0x10");
        unreadable.put("b", "yes");
        unreadable.put("a", "{\"k\":1}");
        unreadable.put("o", "[1]");
        for (Map.Entry<String, String> entry : unreadable.entrySet()) {
            assertEquals(entry.getValue(), convert(entry.getKey(), entry.getValue()).get(entry.getKey()));
        }
        assertEquals("NaN", convert("n", "NaN").get("n"));
        assertEquals("01", convert("i", "01").get("i"));
        assertEquals("TRUE", convert("b", "TRUE").get("b"));
        assertEquals("[1", convert("a", "[1").get("a"));

        Map<String, String[]> raw = new LinkedHashMap<>();
        unreadable.forEach((name, value) -> raw.put(name, new String[]{value}));
        assertEquals("typed has invalid input(s): 'i' must be integer, got string; "
                        + "'n' must be number, got string; 'b' must be boolean, got string; "
                        + "'a' must be array, got string; 'o' must be object, got string",
                ParameterValidation.check("typed", decl, RestRouter.convertQueryParams(raw, decl)));
    }

    /** The document names the JSON type the service checks. */
    @SuppressWarnings("unchecked")
    @Test void openApiNamesTheJsonTypeTheServiceChecks() {
        Map<String, Object> spec = OpenApiGenerator.generateSpec("svc", List.of(
                new RestRoute("typed", "/api/typed", "GET", typedDeclaration())));
        Map<String, Object> get = (Map<String, Object>) ((Map<String, Object>)
                ((Map<String, Object>) spec.get("paths")).get("/api/typed")).get("get");
        Map<String, Object> typeByName = new LinkedHashMap<>();
        for (Map<String, Object> parameter : (List<Map<String, Object>>) get.get("parameters")) {
            typeByName.put((String) parameter.get("name"),
                    ((Map<String, Object>) parameter.get("schema")).get("type"));
        }
        assertEquals(Map.of("i", "integer", "n", "number", "b", "boolean", "a", "array",
                "o", "object", "s", "string", "d", "string"), typeByName);
    }

    @Test void extractBodyParamsWrapper() {
        Map<String, Object> body = Map.of("parameters", Map.of("name", "test"));
        Map<String, Object> params = RestRouter.extractBodyParams(body);
        assertEquals("test", params.get("name"));
    }

    @Test void extractBodyParamsFlat() {
        Map<String, Object> body = new LinkedHashMap<>(Map.of("name", "test"));
        Map<String, Object> params = RestRouter.extractBodyParams(body);
        assertEquals("test", params.get("name"));
    }

    /** SPEC.md §6.3: the document does not demand an input that declares on_missing. */
    @SuppressWarnings("unchecked")
    @Test void openApiDoesNotRequireAnOnMissingInput() {
        InputResolution clarify = new InputResolution(
                ResolutionMode.CLARIFY, null, ResolutionBehavior.CLARIFY, null, null);
        InputResolution modeOnly = new InputResolution(
                ResolutionMode.EXPLICIT_ONLY, null, null, null, null);
        List<CapabilityInput> inputs = List.of(
                new CapabilityInput("q", "string", true, "Query"),
                new CapabilityInput("cabin", "string", true, null, "Cabin", null, false,
                        null, null, null, clarify),
                new CapabilityInput("fare", "string", true, null, "Fare", null, false,
                        null, null, null, modeOnly));
        CapabilityDeclaration read = new CapabilityDeclaration("find", "Find", "1.0", inputs,
                new CapabilityOutput("object", List.of()), new SideEffect("read", "not_applicable"),
                List.of("search"), null, null, null);
        CapabilityDeclaration write = new CapabilityDeclaration("make", "Make", "1.0", inputs,
                new CapabilityOutput("object", List.of()), new SideEffect("write", "none"),
                List.of("search"), null, null, null);

        Map<String, Object> spec = OpenApiGenerator.generateSpec("svc", List.of(
                new RestRoute("find", "/api/find", "GET", read),
                new RestRoute("make", "/api/make", "POST", write)));
        Map<String, Object> paths = (Map<String, Object>) spec.get("paths");

        Map<String, Object> get = (Map<String, Object>) ((Map<String, Object>) paths.get("/api/find")).get("get");
        Map<String, Object> requiredByName = new LinkedHashMap<>();
        for (Map<String, Object> parameter : (List<Map<String, Object>>) get.get("parameters")) {
            requiredByName.put((String) parameter.get("name"), parameter.get("required"));
        }
        assertEquals(Map.of("q", true, "cabin", false, "fare", true), requiredByName);

        Map<String, Object> post = (Map<String, Object>) ((Map<String, Object>) paths.get("/api/make")).get("post");
        Map<String, Object> content = (Map<String, Object>) ((Map<String, Object>) post.get("requestBody")).get("content");
        Map<String, Object> schema = (Map<String, Object>) ((Map<String, Object>) content.get("application/json")).get("schema");
        assertEquals(List.of("q", "fare"), schema.get("required"));
    }

    @Test void findRouteReturnsNullForUnknown() {
        List<RestRoute> routes = RestRouter.generateRoutes(service, null);
        assertNull(RestRouter.findRoute(routes, "nonexistent"));
    }
}
