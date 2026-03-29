# Java REST Interface Refactoring Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `anip-rest` from a Spring-coupled module into a framework-agnostic shared core, with thin `anip-rest-spring` and `anip-rest-quarkus` framework adapters.

**Architecture:** Extract shared logic (OpenAPI generation, auth bridge, route generation, query param conversion) from `AnipRestController` into the framework-agnostic `anip-rest` module. Move the Spring controller to a new `anip-rest-spring` module. Create a parallel `anip-rest-quarkus` module with a JAX-RS resource. Both adapters are thin — route lookup, auth extraction, param extraction, and delegation to `ANIPService.invoke()`.

**Tech Stack:** Java 17, Maven multi-module. No new dependencies beyond what exists.

---

## File Structure

| File | Responsibility | Status |
|------|---------------|--------|
| `anip-rest/pom.xml` | Remove Spring dep, keep only anip-service | Modify |
| `anip-rest/.../rest/RestRouter.java` | Route generation + query param conversion (extracted from controller) | Create |
| `anip-rest/.../rest/OpenApiGenerator.java` | Unchanged — already framework-agnostic | Keep |
| `anip-rest/.../rest/RestAuthBridge.java` | Unchanged — already framework-agnostic | Keep |
| `anip-rest/.../rest/RestRoute.java` | Unchanged — already framework-agnostic | Keep |
| `anip-rest/.../rest/RouteOverride.java` | Unchanged — already framework-agnostic | Keep |
| `anip-rest/.../rest/AnipRestController.java` | **Delete** — moves to anip-rest-spring | Delete |
| `anip-rest-spring/pom.xml` | New module: depends on anip-rest + spring-boot-starter-web | Create |
| `anip-rest-spring/.../rest/spring/AnipRestController.java` | Thin Spring controller using shared RestRouter | Create |
| `anip-rest-spring/src/test/.../AnipRestControllerTest.java` | Existing tests, moved to new module | Create |
| `anip-rest-quarkus/pom.xml` | New module: depends on anip-rest + quarkus-rest-jackson | Create |
| `anip-rest-quarkus/.../rest/quarkus/AnipRestResource.java` | Thin JAX-RS resource using shared RestRouter | Create |
| `anip-rest-quarkus/src/test/.../AnipRestResourceTest.java` | Quarkus integration tests | Create |
| `pom.xml` (parent) | Add new modules, managed deps | Modify |
| `anip-example-flights/pom.xml` | Depend on anip-rest-spring instead of anip-rest | Modify |
| `anip-example-flights-quarkus/pom.xml` | Add anip-rest-quarkus dependency | Modify |

Base paths:
- `packages/java/anip-rest/src/main/java/dev/anip/rest/`
- `packages/java/anip-rest-spring/src/main/java/dev/anip/rest/spring/`
- `packages/java/anip-rest-quarkus/src/main/java/dev/anip/rest/quarkus/`

---

## Task 1: Extract RestRouter from AnipRestController

**Files:**
- Create: `packages/java/anip-rest/src/main/java/dev/anip/rest/RestRouter.java`
- Create: `packages/java/anip-rest/src/test/java/dev/anip/resttest/RestRouterTest.java`

Extract `generateRoutes()` and `convertQueryParams()` from `AnipRestController` into a new shared `RestRouter` utility class. These are the two algorithms trapped inside the Spring controller.

- [ ] **Step 1: Create RestRouter.java**

```java
package dev.anip.rest;

import dev.anip.core.CapabilityDeclaration;
import dev.anip.core.CapabilityInput;
import dev.anip.service.ANIPService;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Shared route generation and parameter conversion for REST interface.
 * Framework-agnostic — used by both Spring and Quarkus adapters.
 *
 * Note: RouteOverride paths and methods affect OpenAPI metadata only.
 * HTTP routing always uses /api/{capability} dispatched by capability name.
 * Dynamic routing for custom paths is a future enhancement.
 */
public final class RestRouter {

    private RestRouter() {}

    /**
     * Generates REST routes from service capabilities with optional overrides.
     * Read capabilities → GET, write/irreversible → POST.
     */
    @SuppressWarnings("unchecked")
    public static List<RestRoute> generateRoutes(ANIPService service,
                                                  Map<String, RouteOverride> overrides) {
        List<RestRoute> routes = new ArrayList<>();
        Map<String, Object> manifest = (Map<String, Object>) service.getManifest();
        Map<String, Object> capabilities = (Map<String, Object>) manifest.get("capabilities");

        for (String name : capabilities.keySet()) {
            CapabilityDeclaration decl = service.getCapabilityDeclaration(name);
            if (decl == null) continue;

            String path = "/api/" + name;
            String method = "POST";
            if (decl.getSideEffect() != null && "read".equals(decl.getSideEffect().getType())) {
                method = "GET";
            }

            if (overrides != null && overrides.containsKey(name)) {
                RouteOverride override = overrides.get(name);
                if (override.getPath() != null && !override.getPath().isEmpty()) {
                    path = override.getPath();
                }
                if (override.getMethod() != null && !override.getMethod().isEmpty()) {
                    method = override.getMethod();
                }
            }

            routes.add(new RestRoute(name, path, method, decl));
        }
        return routes;
    }

    /**
     * Converts string query parameters to typed values based on capability input declarations.
     * Handles integer, number, boolean, and string types.
     *
     * @param rawParams map of parameter name → string values (first value used)
     * @param decl the capability declaration for type information
     */
    public static Map<String, Object> convertQueryParams(Map<String, String[]> rawParams,
                                                          CapabilityDeclaration decl) {
        Map<String, String> typeMap = new LinkedHashMap<>();
        if (decl.getInputs() != null) {
            for (CapabilityInput inp : decl.getInputs()) {
                typeMap.put(inp.getName(), inp.getType());
            }
        }

        Map<String, Object> result = new LinkedHashMap<>();
        for (Map.Entry<String, String[]> entry : rawParams.entrySet()) {
            String key = entry.getKey();
            String[] values = entry.getValue();
            if (values == null || values.length == 0) continue;
            String value = values[0];

            String inputType = typeMap.getOrDefault(key, "string");

            switch (inputType) {
                case "integer" -> {
                    try { result.put(key, Integer.parseInt(value)); }
                    catch (NumberFormatException e) { result.put(key, value); }
                }
                case "number" -> {
                    try { result.put(key, Double.parseDouble(value)); }
                    catch (NumberFormatException e) { result.put(key, value); }
                }
                case "boolean" -> result.put(key, "true".equals(value));
                default -> result.put(key, value);
            }
        }

        return result;
    }

    /**
     * Finds a route by capability name.
     * Returns null if not found.
     */
    public static RestRoute findRoute(List<RestRoute> routes, String capabilityName) {
        for (RestRoute r : routes) {
            if (r.getCapabilityName().equals(capabilityName)) {
                return r;
            }
        }
        return null;
    }

    /**
     * Extracts parameters from a POST body.
     * Accepts both {parameters: {...}} wrapper and flat body.
     */
    @SuppressWarnings("unchecked")
    public static Map<String, Object> extractBodyParams(Map<String, Object> body) {
        if (body == null) return new LinkedHashMap<>();
        Map<String, Object> p = (Map<String, Object>) body.get("parameters");
        if (p != null) return p;
        Map<String, Object> result = new LinkedHashMap<>(body);
        result.remove("parameters");
        return result;
    }
}
```

- [ ] **Step 2: Create RestRouterTest.java**

```java
package dev.anip.resttest;

import dev.anip.core.*;
import dev.anip.rest.*;
import dev.anip.service.*;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;

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

    @Test void overridesApply() {
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
        assertEquals(10, result.get("limit")); // integer, not string
    }

    @Test void extractBodyParamsWrapper() {
        Map<String, Object> body = Map.of("parameters", Map.of("name", "test"));
        Map<String, Object> params = RestRouter.extractBodyParams(body);
        assertEquals("test", params.get("name"));
    }

    @Test void extractBodyParamsFlat() {
        Map<String, Object> body = new java.util.LinkedHashMap<>(Map.of("name", "test"));
        Map<String, Object> params = RestRouter.extractBodyParams(body);
        assertEquals("test", params.get("name"));
    }

    @Test void findRouteReturnsNullForUnknown() {
        List<RestRoute> routes = RestRouter.generateRoutes(service, null);
        assertNull(RestRouter.findRoute(routes, "nonexistent"));
    }
}
```

- [ ] **Step 3: Run tests**

```bash
cd packages/java && mvn test -pl anip-rest -am -q
```

- [ ] **Step 4: Commit**

```bash
git add packages/java/anip-rest/src/main/java/dev/anip/rest/RestRouter.java \
       packages/java/anip-rest/src/test/java/dev/anip/resttest/RestRouterTest.java
git commit -m "feat(java): extract RestRouter from AnipRestController"
```

---

## Task 2: Make anip-rest framework-agnostic

**Files:**
- Modify: `packages/java/anip-rest/pom.xml` — remove Spring dependencies
- Delete: `packages/java/anip-rest/src/main/java/dev/anip/rest/AnipRestController.java`
- Delete: `packages/java/anip-rest/src/test/java/dev/anip/resttest/AnipRestControllerTest.java`

- [ ] **Step 1: Remove Spring deps from anip-rest POM**

Replace the dependencies with only `anip-service` and JUnit:

```xml
    <dependencies>
        <dependency>
            <groupId>dev.anip</groupId>
            <artifactId>anip-service</artifactId>
        </dependency>
        <dependency>
            <groupId>org.junit.jupiter</groupId>
            <artifactId>junit-jupiter</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>
```

- [ ] **Step 2: Delete AnipRestController.java**

```bash
rm packages/java/anip-rest/src/main/java/dev/anip/rest/AnipRestController.java
```

- [ ] **Step 3: Delete old test**

```bash
rm packages/java/anip-rest/src/test/java/dev/anip/resttest/AnipRestControllerTest.java
```

- [ ] **Step 4: Verify the module compiles and tests pass**

```bash
cd packages/java && mvn test -pl anip-rest -am -q
```

- [ ] **Step 5: Commit**

```bash
git add -A packages/java/anip-rest/
git commit -m "refactor(java): make anip-rest framework-agnostic, remove Spring coupling"
```

---

## Task 3: Create anip-rest-spring

**Files:**
- Create: `packages/java/anip-rest-spring/pom.xml`
- Create: `packages/java/anip-rest-spring/src/main/java/dev/anip/rest/spring/AnipRestController.java`
- Create: `packages/java/anip-rest-spring/src/test/java/dev/anip/rest/springtest/AnipRestControllerTest.java`
- Modify: `packages/java/pom.xml` — add module + managed dep
- Modify: `packages/java/anip-example-flights/pom.xml` — change anip-rest → anip-rest-spring

The new Spring controller is thin — it delegates to `RestRouter` for route generation, param conversion, and route lookup. The controller only handles Spring annotations, request/response mapping, and auth header extraction. HTTP routing uses `/api/{capability}` dispatched by capability name (unchanged from the current behavior). Route overrides affect OpenAPI metadata only.

- [ ] **Step 1: Add module to parent POM**

In `packages/java/pom.xml`:
- Add `<module>anip-rest-spring</module>` after `anip-rest`
- Add managed dependency for `anip-rest-spring` with `${anip.version}`

- [ ] **Step 2: Create POM**

```xml
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <parent>
        <groupId>dev.anip</groupId>
        <artifactId>anip-parent</artifactId>
        <version>0.11.0</version>
    </parent>

    <artifactId>anip-rest-spring</artifactId>
    <name>ANIP REST Spring</name>
    <description>Spring MVC adapter for the ANIP REST interface</description>

    <dependencies>
        <dependency>
            <groupId>dev.anip</groupId>
            <artifactId>anip-rest</artifactId>
        </dependency>
        <dependency>
            <groupId>dev.anip</groupId>
            <artifactId>anip-service</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>org.junit.jupiter</groupId>
            <artifactId>junit-jupiter</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>
</project>
```

- [ ] **Step 3: Create AnipRestController.java**

The controller is the same as the old one, but `generateRoutes()`, `convertQueryParams()`, `extractBodyParams()`, and `findRoute()` now delegate to `RestRouter`. The controller only contains Spring annotations and HTTP plumbing.

```java
package dev.anip.rest.spring;

import dev.anip.core.ANIPError;
import dev.anip.core.Constants;
import dev.anip.core.DelegationToken;
import dev.anip.rest.*;
import dev.anip.service.ANIPService;
import dev.anip.service.InvokeOpts;

import jakarta.servlet.http.HttpServletRequest;

import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@RestController
public class AnipRestController {

    private final ANIPService service;
    private final List<RestRoute> routes;
    private final Map<String, Object> openApiSpec;

    public AnipRestController(ANIPService service, Map<String, RouteOverride> overrides) {
        this.service = service;
        this.routes = RestRouter.generateRoutes(service, overrides);
        this.openApiSpec = OpenApiGenerator.generateSpec(service.getServiceId(), routes);
    }

    public AnipRestController(ANIPService service) {
        this(service, null);
    }

    @GetMapping(value = "/rest/openapi.json", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<Object> openApi() {
        return ResponseEntity.ok(openApiSpec);
    }

    @GetMapping(value = "/rest/docs", produces = MediaType.TEXT_HTML_VALUE)
    public ResponseEntity<String> docs() {
        String html = """
                <!DOCTYPE html>
                <html><head><title>ANIP REST API</title>
                <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist/swagger-ui.css">
                </head><body>
                <div id="swagger-ui"></div>
                <script src="https://unpkg.com/swagger-ui-dist/swagger-ui-bundle.js"></script>
                <script>SwaggerUIBundle({ url: "/rest/openapi.json", dom_id: "#swagger-ui" });</script>
                </body></html>""";
        return ResponseEntity.ok(html);
    }

    @GetMapping(value = "/api/{capability}", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<Object> handleGet(@PathVariable String capability,
                                             HttpServletRequest request) {
        return handleRoute(capability, "GET", null, request);
    }

    @PostMapping(value = "/api/{capability}", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<Object> handlePost(@PathVariable String capability,
                                              @RequestBody(required = false) Map<String, Object> body,
                                              HttpServletRequest request) {
        return handleRoute(capability, "POST", body, request);
    }

    private ResponseEntity<Object> handleRoute(String capability, String method,
                                                Map<String, Object> body,
                                                HttpServletRequest request) {
        RestRoute route = RestRouter.findRoute(routes, capability);
        if (route == null) {
            return failureResponse(404, Constants.FAILURE_UNKNOWN_CAPABILITY,
                    "Capability '" + capability + "' not found", false);
        }

        String bearer = extractBearer(request.getHeader("Authorization"));
        if (bearer == null || bearer.isEmpty()) {
            Map<String, Object> failure = new LinkedHashMap<>();
            failure.put("type", Constants.FAILURE_AUTH_REQUIRED);
            failure.put("detail", "Authorization header with Bearer token or API key required");
            failure.put("resolution", Map.of("action", "provide_credentials",
                    "requires", "Bearer token or API key"));
            failure.put("retry", true);
            Map<String, Object> resp = new LinkedHashMap<>();
            resp.put("success", false);
            resp.put("failure", failure);
            return ResponseEntity.status(401).body(resp);
        }

        DelegationToken token;
        try {
            token = RestAuthBridge.resolveAuth(bearer, service, capability);
        } catch (ANIPError e) {
            return failureResponse(Constants.failureStatusCode(e.getErrorType()),
                    e.getErrorType(), e.getDetail(), e.isRetry());
        } catch (Exception e) {
            return failureResponse(500, Constants.FAILURE_INTERNAL_ERROR,
                    "Authentication failed", false);
        }

        Map<String, Object> params;
        if ("GET".equals(method)) {
            params = RestRouter.convertQueryParams(request.getParameterMap(), route.getDeclaration());
        } else {
            params = RestRouter.extractBodyParams(body);
        }

        String clientRefId = request.getHeader("X-Client-Reference-Id");
        Map<String, Object> result = service.invoke(capability, token, params,
                new InvokeOpts(clientRefId, false));

        boolean success = Boolean.TRUE.equals(result.get("success"));
        if (!success) {
            @SuppressWarnings("unchecked")
            Map<String, Object> failure = (Map<String, Object>) result.get("failure");
            String failType = failure != null ? (String) failure.get("type") : null;
            return ResponseEntity.status(Constants.failureStatusCode(failType)).body(result);
        }
        return ResponseEntity.ok(result);
    }

    private String extractBearer(String authHeader) {
        if (authHeader != null && authHeader.startsWith("Bearer ")) {
            return authHeader.substring(7).trim();
        }
        return null;
    }

    private ResponseEntity<Object> failureResponse(int status, String type,
                                                     String detail, boolean retry) {
        Map<String, Object> failure = new LinkedHashMap<>();
        failure.put("type", type);
        failure.put("detail", detail);
        failure.put("retry", retry);
        Map<String, Object> resp = new LinkedHashMap<>();
        resp.put("success", false);
        resp.put("failure", failure);
        return ResponseEntity.status(status).body(resp);
    }

    public List<RestRoute> getRoutes() { return routes; }
}
```

- [ ] **Step 4: Move existing test to new module**

Copy the existing `AnipRestControllerTest.java` to `packages/java/anip-rest-spring/src/test/java/dev/anip/rest/springtest/AnipRestControllerTest.java`. Update the import from `dev.anip.rest.AnipRestController` to `dev.anip.rest.spring.AnipRestController`.

- [ ] **Step 5: Update example-flights POM**

In `packages/java/anip-example-flights/pom.xml`, change the `anip-rest` dependency to `anip-rest-spring`:

```xml
        <dependency>
            <groupId>dev.anip</groupId>
            <artifactId>anip-rest-spring</artifactId>
            <version>${anip.version}</version>
        </dependency>
```

Update the import in `Application.java` from `dev.anip.rest.AnipRestController` to `dev.anip.rest.spring.AnipRestController`.

- [ ] **Step 6: Build and test everything**

```bash
cd packages/java && mvn verify -q
```

All existing tests must pass — the Spring example app and conformance are unchanged functionally.

- [ ] **Step 7: Commit**

```bash
git add packages/java/anip-rest-spring/ packages/java/pom.xml \
       packages/java/anip-example-flights/
git commit -m "feat(java): create anip-rest-spring thin adapter"
```

---

## Task 4: Create anip-rest-quarkus

**Files:**
- Create: `packages/java/anip-rest-quarkus/pom.xml`
- Create: `packages/java/anip-rest-quarkus/src/main/java/dev/anip/rest/quarkus/AnipRestResource.java`
- Create: `packages/java/anip-rest-quarkus/src/main/resources/META-INF/beans.xml`
- Create: `packages/java/anip-rest-quarkus/src/test/java/dev/anip/rest/quarkustest/TestServiceProducer.java`
- Create: `packages/java/anip-rest-quarkus/src/test/java/dev/anip/rest/quarkustest/AnipRestResourceTest.java`
- Modify: `packages/java/pom.xml` — add module + managed dependency
- Modify: `packages/java/anip-example-flights-quarkus/pom.xml` — add anip-rest-quarkus dep

The JAX-RS resource mirrors the Spring controller: delegates to `RestRouter` for shared logic, handles JAX-RS annotations and response mapping. HTTP routing uses `/api/{capability}` dispatched by capability name. Route overrides affect OpenAPI metadata only.

- [ ] **Step 1: Add module and managed dependency to parent POM**

In `packages/java/pom.xml`:
- Add `<module>anip-rest-quarkus</module>` after `anip-rest-spring`
- Add managed dependency for `anip-rest-quarkus` with `${anip.version}` in `<dependencyManagement>`

- [ ] **Step 2: Create POM**

```xml
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <parent>
        <groupId>dev.anip</groupId>
        <artifactId>anip-parent</artifactId>
        <version>0.11.0</version>
    </parent>

    <artifactId>anip-rest-quarkus</artifactId>
    <name>ANIP REST Quarkus</name>
    <description>Quarkus JAX-RS adapter for the ANIP REST interface</description>

    <dependencies>
        <dependency>
            <groupId>dev.anip</groupId>
            <artifactId>anip-rest</artifactId>
        </dependency>
        <dependency>
            <groupId>dev.anip</groupId>
            <artifactId>anip-service</artifactId>
        </dependency>
        <dependency>
            <groupId>io.quarkus</groupId>
            <artifactId>quarkus-rest-jackson</artifactId>
        </dependency>
        <dependency>
            <groupId>io.quarkus</groupId>
            <artifactId>quarkus-arc</artifactId>
        </dependency>
        <dependency>
            <groupId>io.quarkus</groupId>
            <artifactId>quarkus-junit5</artifactId>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>io.rest-assured</groupId>
            <artifactId>rest-assured</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>io.quarkus.platform</groupId>
                <artifactId>quarkus-maven-plugin</artifactId>
                <version>${quarkus.version}</version>
                <extensions>true</extensions>
            </plugin>
            <plugin>
                <groupId>io.smallrye</groupId>
                <artifactId>jandex-maven-plugin</artifactId>
                <version>3.2.7</version>
                <executions>
                    <execution>
                        <id>make-index</id>
                        <goals><goal>jandex</goal></goals>
                    </execution>
                </executions>
            </plugin>
        </plugins>
    </build>
</project>
```

- [ ] **Step 3: Create beans.xml**

Same pattern as anip-quarkus:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<beans xmlns="https://jakarta.ee/xml/ns/jakartaee"
       bean-discovery-mode="all">
</beans>
```

- [ ] **Step 4: Create AnipRestResource.java**

Thin JAX-RS resource using `RestRouter` for shared logic. Same endpoints: `/rest/openapi.json`, `/rest/docs`, `/api/{capability}` (GET + POST).

Auth extraction via `@HeaderParam("Authorization")`. Query params via `@Context UriInfo`. Body parsing via `Map<String, Object>` parameter with `@Consumes(WILDCARD)` for GET compatibility.

The resource is `@ApplicationScoped` with `@Inject ANIPService service`.

- [ ] **Step 5: Create test producer + tests**

`TestServiceProducer` — CDI bean producing ANIPService for tests (same pattern as anip-quarkus tests).

`AnipRestResourceTest` — `@QuarkusTest` with REST Assured covering: OpenAPI endpoint, GET capability, POST capability, auth failures, unknown capability.

- [ ] **Step 6: Update Quarkus example app**

Add `anip-rest-quarkus` dependency to `anip-example-flights-quarkus/pom.xml`. The `AnipRestResource` will be auto-discovered via Jandex + CDI.

- [ ] **Step 7: Build, test, conformance**

```bash
cd packages/java && mvn verify -q
```

Run conformance against both Spring and Quarkus examples to verify REST endpoints work on both.

- [ ] **Step 8: Commit**

```bash
git add packages/java/anip-rest-quarkus/ packages/java/pom.xml \
       packages/java/anip-example-flights-quarkus/
git commit -m "feat(java): create anip-rest-quarkus thin adapter"
```

---

## Task 5: Update release workflow + CI

**Files:**
- Modify: `.github/workflows/release.yml`
- Modify: `.github/workflows/ci-java.yml`

- [ ] **Step 1: Update release validation and deploy lists**

Add `anip-rest-spring`, `anip-rest-quarkus` to the Java module validation loop and Maven deploy loop.

- [ ] **Step 2: Update CI smoke tests**

The Spring conformance job should also smoke-test `/rest/openapi.json` and `/api/search_flights` to validate the REST interface works through `anip-rest-spring`.

The Quarkus conformance job should do the same to validate `anip-rest-quarkus`.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/
git commit -m "ci(java): add anip-rest-spring and anip-rest-quarkus to release and CI"
```

---

## Task 6: Conformance + PR

- [ ] **Step 1: Run conformance against Spring example**

```bash
java -jar anip-example-flights/target/anip-example-flights-0.11.0.jar &
sleep 8
pytest conformance/ --base-url=http://localhost:8080 --bootstrap-bearer=demo-human-key \
  --sample-inputs=conformance/samples/flight-service.json -v
kill %1
```

- [ ] **Step 2: Run conformance against Quarkus example**

```bash
java -jar anip-example-flights-quarkus/target/quarkus-app/quarkus-run.jar &
sleep 5
pytest conformance/ --base-url=http://localhost:8080 --bootstrap-bearer=demo-human-key \
  --sample-inputs=conformance/samples/flight-service.json -v
kill %1
```

Both must pass: 43 passed, 1 skipped.

- [ ] **Step 3: Push and create PR**

```bash
git push -u origin feat/java-rest-refactor
gh pr create --title "refactor(java): split anip-rest into shared core + Spring/Quarkus adapters"
```
