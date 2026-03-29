# Quarkus ANIP Binding Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Quarkus framework binding (`anip-quarkus`) that mounts the 9 core ANIP protocol endpoints via JAX-RS, plus a Quarkus example app that passes the conformance suite.

**Architecture:** New `anip-quarkus` module with a JAX-RS `@Path` resource class that delegates to `ANIPService` — same pattern as `anip-spring-boot` but using Quarkus RESTEasy Reactive + Jackson. Lifecycle managed via Quarkus `StartupEvent`/`ShutdownEvent`. Quarkus example app reuses the existing capability definitions (`SearchFlightsCapability`, `BookFlightCapability`). The Quarkus BOM manages framework dependency versions separately from the Spring Boot BOM already in the parent POM.

**Tech Stack:** Quarkus 3.17 (latest LTS), RESTEasy Reactive + Jackson, quarkus-maven-plugin, Java 17.

---

## File Structure

| File | Responsibility | Status |
|------|---------------|--------|
| `packages/java/anip-quarkus/pom.xml` | Module POM with Quarkus BOM | Create |
| `packages/java/anip-quarkus/src/main/java/dev/anip/quarkus/AnipResource.java` | JAX-RS resource — 9 ANIP endpoints | Create |
| `packages/java/anip-quarkus/src/main/java/dev/anip/quarkus/AnipLifecycle.java` | Start/shutdown lifecycle | Create |
| `packages/java/anip-quarkus/src/test/java/dev/anip/quarkustest/AnipResourceTest.java` | Integration tests via @QuarkusTest | Create |
| `packages/java/anip-quarkus/src/test/java/dev/anip/quarkustest/TestServiceProducer.java` | CDI producer providing ANIPService for tests | Create |
| `packages/java/anip-example-flights-quarkus/pom.xml` | Example app POM | Create |
| `packages/java/anip-example-flights-quarkus/src/main/java/dev/anip/example/quartzflights/QuarkusFlightsApp.java` | Quarkus app configuring ANIPService | Create |
| `packages/java/anip-example-flights-quarkus/src/main/resources/application.properties` | Quarkus config | Create |
| `packages/java/pom.xml` | Add 2 new modules, Quarkus BOM version property | Modify |
| `.github/workflows/ci-java.yml` | Add Quarkus conformance job | Modify |

---

## Task 1: Parent POM — Add Quarkus modules and BOM

**Files:**
- Modify: `packages/java/pom.xml`

- [ ] **Step 1: Add Quarkus BOM version property**

Add to `<properties>` (after `mcp-sdk.version`):

```xml
        <quarkus.version>3.17.8</quarkus.version>
```

- [ ] **Step 2: Add Quarkus BOM to dependencyManagement**

Add inside `<dependencyManagement><dependencies>`, after the Spring Boot BOM:

```xml
            <!-- Quarkus BOM -->
            <dependency>
                <groupId>io.quarkus.platform</groupId>
                <artifactId>quarkus-bom</artifactId>
                <version>${quarkus.version}</version>
                <type>pom</type>
                <scope>import</scope>
            </dependency>
```

Also add the new module to managed deps:

```xml
            <dependency>
                <groupId>dev.anip</groupId>
                <artifactId>anip-quarkus</artifactId>
                <version>${anip.version}</version>
            </dependency>
```

- [ ] **Step 3: Add modules**

Add to `<modules>` (before `anip-example-flights`):

```xml
        <module>anip-quarkus</module>
```

Add after `anip-example-flights`:

```xml
        <module>anip-example-flights-quarkus</module>
```

- [ ] **Step 4: Run build to verify POM is valid**

```bash
cd packages/java && mvn validate -q
```

- [ ] **Step 5: Commit**

```bash
git add packages/java/pom.xml
git commit -m "feat(java): add Quarkus BOM and module declarations to parent POM"
```

---

## Task 2: anip-quarkus Module — POM + Lifecycle

**Files:**
- Create: `packages/java/anip-quarkus/pom.xml`
- Create: `packages/java/anip-quarkus/src/main/java/dev/anip/quarkus/AnipLifecycle.java`

- [ ] **Step 1: Create module POM**

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

    <artifactId>anip-quarkus</artifactId>
    <name>ANIP Quarkus</name>
    <description>Quarkus JAX-RS binding for ANIP protocol routes</description>

    <dependencies>
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
                <executions>
                    <execution>
                        <goals>
                            <goal>build</goal>
                        </goals>
                    </execution>
                </executions>
            </plugin>
        </plugins>
    </build>
</project>
```

- [ ] **Step 2: Create lifecycle bean**

```java
package dev.anip.quarkus;

import dev.anip.service.ANIPService;
import io.quarkus.runtime.ShutdownEvent;
import io.quarkus.runtime.StartupEvent;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.event.Observes;
import jakarta.inject.Inject;

/**
 * Bridges Quarkus lifecycle to ANIPService start/shutdown.
 */
@ApplicationScoped
public class AnipLifecycle {

    @Inject
    ANIPService service;

    void onStart(@Observes StartupEvent ev) {
        try {
            service.start();
        } catch (Exception e) {
            throw new RuntimeException("Failed to start ANIPService", e);
        }
    }

    void onStop(@Observes ShutdownEvent ev) {
        try {
            service.shutdown();
        } catch (Exception e) {
            // Best effort shutdown.
        }
    }
}
```

- [ ] **Step 3: Verify compilation**

```bash
cd packages/java && mvn compile -pl anip-quarkus -am -q
```

- [ ] **Step 4: Commit**

```bash
git add packages/java/anip-quarkus/
git commit -m "feat(java): add anip-quarkus module POM and lifecycle bean"
```

---

## Task 3: AnipResource — 9 ANIP Protocol Endpoints

**Files:**
- Create: `packages/java/anip-quarkus/src/main/java/dev/anip/quarkus/AnipResource.java`

This is the core file — a JAX-RS `@Path` resource class mapping the same 9 endpoints as `AnipController.java` in the Spring binding. Key differences from Spring:

- `@Path` + `@GET/@POST` instead of `@GetMapping/@PostMapping`
- `@PathParam` instead of `@PathVariable`
- `@QueryParam` instead of `@RequestParam`
- `jakarta.ws.rs.core.Response` instead of `ResponseEntity`
- `@Context UriInfo` for base URL derivation
- `@HeaderParam("Authorization")` for auth header

- [ ] **Step 1: Create the resource class**

The resource must implement these endpoints:

1. `GET /.well-known/anip` → discovery
2. `GET /.well-known/jwks.json` → JWKS
3. `GET /anip/manifest` → signed manifest with X-ANIP-Signature header
4. `POST /anip/tokens` → token issuance (bootstrap auth)
5. `POST /anip/permissions` → permission discovery (JWT auth)
6. `POST /anip/invoke/{capability}` → unary invoke (JWT auth), returns `Response` with JSON
7. `POST /anip/audit` → audit query (JWT auth)
8. `GET /anip/checkpoints` → list checkpoints
9. `GET /anip/checkpoints/{id}` → checkpoint detail with optional proof
10. `GET /-/health` → health endpoint (toggled via `healthEnabled` constructor param, returns 404 when disabled)

**Health toggle:** `AnipResource` reads `@ConfigProperty(name = "anip.health.enabled", defaultValue = "true") boolean healthEnabled`. When false, `GET /-/health` returns 404. This is the Quarkus-native equivalent of the Spring binding's constructor parameter — app code sets `anip.health.enabled=false` in `application.properties` to disable it.

**Auth patterns:**
- Extract `Authorization: Bearer <token>` from `@HeaderParam("Authorization")`
- Bootstrap auth: `service.authenticateBearer(bearer)` returns `Optional<String>`
- JWT auth: `service.resolveBearerToken(bearer)` returns `DelegationToken`

**Error handling:**
- `ANIPError` maps to HTTP status via `Constants.failureStatusCode(errorType)`
- Failure responses: `{success: false, failure: {type, detail}}`

**Jackson ObjectMapper:** Configure via `application.properties` (`quarkus.jackson.*`) — no manual ObjectMapper needed since Quarkus REST handles serialization.

**SSE streaming — chosen approach: `StreamingOutput`**

The invoke endpoint returns `Response` in all cases. For streaming (`"stream": true` in request body):

1. Call `service.invokeStream(capability, token, params, opts)` → `StreamResult`
2. Return `Response.ok(streamingOutput).type(MediaType.SERVER_SENT_EVENTS_TYPE).build()`
3. The `StreamingOutput` writes SSE events by polling `StreamResult.getEvents()` with 30s timeout
4. Each event writes `event: {type}\ndata: {json}\n\n` manually to the `OutputStream`
5. On client disconnect or terminal event, close the stream

This is the simplest SSE approach that works with JAX-RS without Mutiny/Reactive dependencies. It matches how the Spring binding uses a reader thread polling the `BlockingQueue`, but outputs directly via `StreamingOutput` instead of `SseEmitter`.

```java
private Response handleStreamInvoke(String capability, DelegationToken token,
                                     Map<String, Object> params, String clientRefId) {
    StreamResult sr;
    try {
        sr = service.invokeStream(capability, token, params, new InvokeOpts(clientRefId, true));
    } catch (ANIPError e) {
        // Return initial error as SSE failed event
        StreamingOutput output = os -> {
            Map<String, Object> errorData = Map.of(
                "success", false, "failure", Map.of("type", e.getErrorType(), "detail", e.getDetail()));
            os.write(("event: failed\ndata: " + MAPPER.writeValueAsString(errorData) + "\n\n").getBytes());
            os.flush();
        };
        return Response.ok(output).type(MediaType.SERVER_SENT_EVENTS_TYPE).build();
    }

    StreamingOutput output = os -> {
        try {
            while (true) {
                StreamEvent event = sr.getEvents().poll(30, TimeUnit.SECONDS);
                if (event == null || StreamResult.DONE_TYPE.equals(event.getType())) break;
                os.write(("event: " + event.getType() + "\ndata: "
                    + MAPPER.writeValueAsString(event.getPayload()) + "\n\n").getBytes());
                os.flush();
            }
        } catch (Exception e) {
            sr.getCancel().run();
        }
    };
    return Response.ok(output).type(MediaType.SERVER_SENT_EVENTS_TYPE).build();
}
```

The resource class should be `@ApplicationScoped` with `ANIPService` injected via constructor (not `@Inject` field) for testability.

- [ ] **Step 2: Verify compilation**

```bash
cd packages/java && mvn compile -pl anip-quarkus -am -q
```

- [ ] **Step 3: Commit**

```bash
git add packages/java/anip-quarkus/src/main/java/dev/anip/quarkus/AnipResource.java
git commit -m "feat(java): add AnipResource with 9 ANIP protocol endpoints"
```

---

## Task 3b: AnipResource Tests

**Files:**
- Create: `packages/java/anip-quarkus/src/test/java/dev/anip/quarkustest/TestServiceProducer.java`
- Create: `packages/java/anip-quarkus/src/test/java/dev/anip/quarkustest/AnipResourceTest.java`

The binding module needs its own `@QuarkusTest` tests. Since `ANIPService` is not a CDI bean by default (it's created by app code), the tests need a CDI producer that provides one.

- [ ] **Step 1: Create CDI test producer**

```java
package dev.anip.quarkustest;

import dev.anip.core.*;
import dev.anip.service.*;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Produces;
import java.util.List;
import java.util.Map;
import java.util.Optional;

@ApplicationScoped
public class TestServiceProducer {

    @Produces
    @ApplicationScoped
    public ANIPService anipService() {
        return new ANIPService(new ServiceConfig()
                .setServiceId("test-quarkus-svc")
                .setCapabilities(List.of(
                        new CapabilityDef(
                                new CapabilityDeclaration(
                                        "search_flights", "Search for flights", "1.0",
                                        List.of(
                                                new CapabilityInput("origin", "string", true, "Origin"),
                                                new CapabilityInput("destination", "string", true, "Dest")
                                        ),
                                        new CapabilityOutput("object", List.of("flights")),
                                        new SideEffect("read", "not_applicable"),
                                        List.of("travel"), null, null, null
                                ),
                                (ctx, params) -> Map.of("flights", List.of(Map.of("id", "FL-001", "price", 199.99)))
                        )
                ))
                .setStorage(":memory:")
                .setAuthenticate(bearer -> "valid-api-key".equals(bearer) ? Optional.of("user@test.com") : Optional.empty())
        );
    }
}
```

- [ ] **Step 2: Create test class**

Uses `@QuarkusTest` + REST Assured to test all endpoints:

```java
package dev.anip.quarkustest;

import dev.anip.service.ANIPService;
import io.quarkus.test.junit.QuarkusTest;
import jakarta.inject.Inject;
import org.junit.jupiter.api.*;

import java.util.List;

import static io.restassured.RestAssured.given;
import static org.hamcrest.Matchers.*;

@QuarkusTest
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
class AnipResourceTest {

    @Inject
    ANIPService service;

    private String validJwt;

    @BeforeAll
    void setUp() {
        var req = new dev.anip.core.TokenRequest(
                "agent:test", List.of("travel"), "search_flights",
                null, null, 0, null);
        var resp = service.issueToken("user@test.com", req);
        validJwt = resp.getToken();
    }

    @Test @Order(1) void discoveryReturns200() {
        given().when().get("/.well-known/anip")
            .then().statusCode(200)
            .body("anip_discovery.protocol", startsWith("anip/"))
            .body("anip_discovery.compliance", equalTo("anip-compliant"));
    }

    @Test @Order(2) void jwksReturnsKeys() {
        given().when().get("/.well-known/jwks.json")
            .then().statusCode(200)
            .body("keys", not(empty()));
    }

    @Test @Order(3) void manifestHasSignature() {
        given().when().get("/anip/manifest")
            .then().statusCode(200)
            .header("X-ANIP-Signature", notNullValue());
    }

    @Test @Order(4) void tokenIssuanceSuccess() {
        given().contentType("application/json")
            .header("Authorization", "Bearer valid-api-key")
            .body("{\"subject\":\"agent:test\",\"scope\":[\"travel\"],\"capability\":\"search_flights\"}")
            .when().post("/anip/tokens")
            .then().statusCode(200)
            .body("token_id", notNullValue())
            .body("token", notNullValue());
    }

    @Test @Order(5) void tokenIssuanceMissingAuth() {
        given().contentType("application/json")
            .body("{\"subject\":\"agent:test\",\"scope\":[\"travel\"]}")
            .when().post("/anip/tokens")
            .then().statusCode(401);
    }

    @Test @Order(6) void invokeSuccess() {
        given().contentType("application/json")
            .header("Authorization", "Bearer " + validJwt)
            .body("{\"parameters\":{\"origin\":\"SEA\",\"destination\":\"SFO\"}}")
            .when().post("/anip/invoke/search_flights")
            .then().statusCode(200)
            .body("success", equalTo(true))
            .body("invocation_id", startsWith("inv-"));
    }

    @Test @Order(7) void invokeMissingAuth() {
        given().contentType("application/json")
            .body("{\"parameters\":{}}")
            .when().post("/anip/invoke/search_flights")
            .then().statusCode(401);
    }

    @Test @Order(8) void invokeUnknownCapability() {
        given().contentType("application/json")
            .header("Authorization", "Bearer " + validJwt)
            .body("{\"parameters\":{}}")
            .when().post("/anip/invoke/nonexistent")
            .then().statusCode(404);
    }

    @Test @Order(9) void healthReturnsStatus() {
        given().when().get("/-/health")
            .then().statusCode(200)
            .body("status", equalTo("healthy"));
    }
}
```

- [ ] **Step 3: Run tests**

```bash
cd packages/java && mvn test -pl anip-quarkus -am -q
```

- [ ] **Step 4: Commit**

```bash
git add packages/java/anip-quarkus/src/test/
git commit -m "test(java): add AnipResource Quarkus integration tests"
```

---

## Task 4: Quarkus Example Flights App

**Files:**
- Create: `packages/java/anip-example-flights-quarkus/pom.xml`
- Create: `packages/java/anip-example-flights-quarkus/src/main/java/dev/anip/example/quartzflights/QuarkusFlightsApp.java`
- Create: `packages/java/anip-example-flights-quarkus/src/main/resources/application.properties`

- [ ] **Step 1: Create POM**

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

    <artifactId>anip-example-flights-quarkus</artifactId>
    <name>ANIP Example Flights (Quarkus)</name>
    <description>Example ANIP flight service on Quarkus demonstrating protocol binding</description>

    <dependencies>
        <dependency>
            <groupId>dev.anip</groupId>
            <artifactId>anip-core</artifactId>
        </dependency>
        <dependency>
            <groupId>dev.anip</groupId>
            <artifactId>anip-service</artifactId>
        </dependency>
        <dependency>
            <groupId>dev.anip</groupId>
            <artifactId>anip-quarkus</artifactId>
        </dependency>
        <dependency>
            <groupId>io.quarkus</groupId>
            <artifactId>quarkus-rest-jackson</artifactId>
        </dependency>
        <dependency>
            <groupId>io.quarkus</groupId>
            <artifactId>quarkus-arc</artifactId>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>io.quarkus.platform</groupId>
                <artifactId>quarkus-maven-plugin</artifactId>
                <version>${quarkus.version}</version>
                <extensions>true</extensions>
                <executions>
                    <execution>
                        <goals>
                            <goal>build</goal>
                        </goals>
                    </execution>
                </executions>
            </plugin>
        </plugins>
    </build>
</project>
```

- [ ] **Step 2: Create application configuration producer**

The Quarkus app needs a CDI producer that creates the `ANIPService` bean — same capabilities, same auth, same config as the Spring example. Reuse `SearchFlightsCapability` and `BookFlightCapability` from the Spring example (they're framework-agnostic).

```java
package dev.anip.example.quartzflights;

import dev.anip.example.flights.SearchFlightsCapability;
import dev.anip.example.flights.BookFlightCapability;
import dev.anip.service.ANIPService;
import dev.anip.service.ServiceConfig;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Produces;
import java.util.List;
import java.util.Map;
import java.util.Optional;

@ApplicationScoped
public class QuarkusFlightsApp {

    @Produces
    @ApplicationScoped
    public ANIPService anipService() {
        Map<String, String> apiKeys = Map.of(
                "demo-human-key", "human:samir@example.com",
                "demo-agent-key", "agent:demo-agent"
        );

        String serviceId = System.getenv().getOrDefault("ANIP_SERVICE_ID", "anip-flight-service");

        return new ANIPService(new ServiceConfig()
                .setServiceId(serviceId)
                .setCapabilities(List.of(
                        SearchFlightsCapability.create(),
                        BookFlightCapability.create()
                ))
                .setStorage(System.getenv().getOrDefault("ANIP_STORAGE", ":memory:"))
                .setTrust(System.getenv().getOrDefault("ANIP_TRUST_LEVEL", "signed"))
                .setKeyPath(System.getenv().getOrDefault("ANIP_KEY_PATH", "./anip-keys"))
                .setAuthenticate(bearer -> {
                    String principal = apiKeys.get(bearer);
                    if (principal != null) {
                        return Optional.of(principal);
                    }
                    return Optional.empty();
                })
        );
    }
}
```

**Important:** The capability classes (`SearchFlightsCapability`, `BookFlightCapability`, `FlightData`) are in the `anip-example-flights` module under `dev.anip.example.flights`. The Quarkus example should depend on the capabilities directly. Since those classes are framework-agnostic (no Spring annotations), either:
- Add `anip-example-flights` as a dependency (but it pulls in Spring Boot — bad)
- Copy the 3 capability files into the Quarkus example (duplication — also bad)
- Extract capabilities into a shared module (over-engineering for now)

Best approach: **copy the 3 capability files** (`SearchFlightsCapability.java`, `BookFlightCapability.java`, `FlightData.java`) into the Quarkus example under the same package `dev.anip.example.flights`. This is the same approach Go uses (each example has its own capability definitions). Keep the files identical.

- [ ] **Step 3: Create application.properties**

```properties
quarkus.http.port=8080
quarkus.jackson.property-naming-strategy=SNAKE_CASE
quarkus.jackson.fail-on-unknown-properties=false
quarkus.jackson.serialization-inclusion=non-null
```

- [ ] **Step 4: Build and verify**

```bash
cd packages/java && mvn package -pl anip-example-flights-quarkus -am -DskipTests -q
```

- [ ] **Step 5: Commit**

```bash
git add packages/java/anip-example-flights-quarkus/
git commit -m "feat(java): add Quarkus example flights app"
```

---

## Task 5: Run Conformance Suite

- [ ] **Step 1: Start the Quarkus example**

```bash
cd packages/java
java -jar anip-example-flights-quarkus/target/quarkus-app/quarkus-run.jar &
sleep 5
```

Note: Quarkus produces a different jar structure than Spring Boot. The runner jar is at `target/quarkus-app/quarkus-run.jar`.

- [ ] **Step 2: Smoke test**

```bash
curl -sf http://localhost:8080/.well-known/anip | head -c 100
```

- [ ] **Step 3: Run conformance**

```bash
pytest conformance/ \
  --base-url=http://localhost:8080 \
  --bootstrap-bearer=demo-human-key \
  --sample-inputs=conformance/samples/flight-service.json \
  -v
```

Expected: 43 passed, 1 skipped

- [ ] **Step 4: Kill server and commit any fixups**

```bash
kill %1
git add -A && git commit -m "fix(java): conformance fixups for Quarkus binding"
```

---

## Task 6: CI Workflow

**Files:**
- Modify: `.github/workflows/ci-java.yml`

- [ ] **Step 1: Add Quarkus conformance job**

Add a new `conformance-quarkus` job that builds and tests the Quarkus example, parallel to the existing Spring Boot conformance job. The job:
1. Checks out code
2. Sets up Java 21
3. Sets up Python 3.12
4. Builds: `mvn package -pl anip-example-flights-quarkus -am -DskipTests`
5. Starts: `java -jar anip-example-flights-quarkus/target/quarkus-app/quarkus-run.jar &`
6. Runs conformance suite
7. Add to `java-ci` gate job's needs and condition

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/ci-java.yml
git commit -m "ci(java): add Quarkus conformance job"
```

---

## Task 7: Create PR

- [ ] **Step 1: Push and create PR**

```bash
git push -u origin feat/quarkus-binding
gh pr create --title "feat(java): add Quarkus ANIP binding" --body "..."
```
