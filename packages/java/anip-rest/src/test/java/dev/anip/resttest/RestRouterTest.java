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

    @Test void findRouteReturnsNullForUnknown() {
        List<RestRoute> routes = RestRouter.generateRoutes(service, null);
        assertNull(RestRouter.findRoute(routes, "nonexistent"));
    }
}
