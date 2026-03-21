# Java ANIP Runtime Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a full-parity Java ANIP runtime with Spring Boot binding and all interface packages, passing the conformance suite.

**Architecture:** Multi-module Maven project at `packages/java/`. Built bottom-up: parent POM → core → crypto → server → service → Spring Boot → REST → GraphQL → MCP → example app → conformance. Each module produces an independent JAR artifact.

**Tech Stack:** Java 17, Maven, Spring Boot 3.x, Nimbus JOSE+JWT, xerial sqlite-jdbc, HikariCP + PostgreSQL JDBC, graphql-java, official MCP Java SDK

**Design doc:** `docs/plans/2026-03-21-java-runtime-design.md`

---

## Implementation Order

Build bottom-up. Each task produces a compilable, testable module:

1. **Parent POM + anip-core** — Maven structure, protocol types
2. **anip-crypto** — Nimbus JOSE+JWT: keys, JWT, JWS, JWKS
3. **anip-server** — Storage interface, SQLite, PostgreSQL, delegation, audit, checkpoints, leases
4. **anip-service** — Orchestration, hooks, health, background workers, streaming
5. **anip-spring-boot** — Spring MVC binding, all 9 protocol routes, SSE, health endpoint
6. **anip-rest** — REST interface (OpenAPI + auto-generated endpoints)
7. **anip-graphql** — GraphQL interface (graphql-java, SDL, resolvers)
8. **anip-mcp** — MCP interface (official Java SDK, stdio + Streamable HTTP)
9. **anip-example-flights** — Spring Boot example app with all interfaces
10. **Conformance + CI** — run suite, fix failures, add workflow

Each task depends on the previous. Tasks 6-8 (REST, GraphQL, MCP) can run in parallel after Task 5.

---

## Task 1: Parent POM + anip-core

**Files:**
- Create: `packages/java/pom.xml` — parent POM
- Create: `packages/java/anip-core/pom.xml`
- Create: `packages/java/anip-core/src/main/java/dev/anip/core/` — all core types

- [ ] **Step 1: Create parent POM**

```xml
<project>
  <modelVersion>4.0.0</modelVersion>
  <groupId>dev.anip</groupId>
  <artifactId>anip-parent</artifactId>
  <version>0.11.0</version>
  <packaging>pom</packaging>
  <name>ANIP Parent</name>

  <properties>
    <maven.compiler.source>17</maven.compiler.source>
    <maven.compiler.target>17</maven.compiler.target>
    <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
    <anip.version>0.11.0</anip.version>
  </properties>

  <modules>
    <module>anip-core</module>
    <!-- add modules as they're created -->
  </modules>
</project>
```

- [ ] **Step 2: Create anip-core module**

No external dependencies. Plain Java POJOs.

Key classes (based on Go/Python/TS reference types):
- `dev.anip.core.Constants` — `PROTOCOL_VERSION = "anip/0.11"`, failure type constants, `generateInvocationId()`
- `dev.anip.core.CapabilityDeclaration` — name, description, inputs, output, sideEffect, minimumScope, cost, requires, responseModes
- `dev.anip.core.SideEffect` — type, rollbackWindow
- `dev.anip.core.Cost`, `CostActual` — certainty, financial, compute
- `dev.anip.core.DelegationToken` — tokenId, subject, scope, purpose, constraints, rootPrincipal, expires
- `dev.anip.core.DelegationConstraints` — maxDelegationDepth, concurrentBranches
- `dev.anip.core.Purpose` — capability, parameters, taskId
- `dev.anip.core.ANIPError extends RuntimeException` — errorType, detail, resolution, retry
- `dev.anip.core.Resolution` — action, requires, grantableBy, estimatedAvailability
- `dev.anip.core.TokenRequest`, `TokenResponse`
- `dev.anip.core.InvokeResponse` — success, invocationId, result, costActual, failure
- `dev.anip.core.PermissionResponse` — available, restricted, denied
- `dev.anip.core.AuditEntry`, `AuditResponse`, `AuditFilters`
- `dev.anip.core.Checkpoint`, `CheckpointListResponse`, `CheckpointDetailResponse`
- `dev.anip.core.HealthReport`, `StorageHealth`
- `dev.anip.core.CapabilityInput`, `CapabilityOutput`

All fields should use Java naming conventions internally but serialize to ANIP wire format (snake_case) — JSON serialization is handled in higher modules. Core classes are pure POJOs with constructors/getters or public records.

- [ ] **Step 3: Write core tests**

Test invocation ID format (`inv-[0-9a-f]{12}`), ANIPError behavior, failure status code mapping.

- [ ] **Step 4: Build and verify**

```bash
cd packages/java && mvn install -pl anip-core
```

- [ ] **Step 5: Commit**

```bash
git add packages/java/
git commit -m "feat(java): add parent POM and anip-core module"
```

---

## Task 2: anip-crypto

**Files:**
- Create: `packages/java/anip-crypto/pom.xml`
- Create: `packages/java/anip-crypto/src/main/java/dev/anip/crypto/` — KeyManager, JwtSigner, JwsSigner, JwksSerializer

- [ ] **Step 1: Create anip-crypto POM**

Dependencies: `anip-core`, `com.nimbusds:nimbus-jose-jwt:9.x`

- [ ] **Step 2: Implement KeyManager**

Generate/load/store two ES256 key pairs (delegation + audit). Keys stored as JSON files. Kid from JWK thumbprint (RFC 7638).

- [ ] **Step 3: Implement JWT signing/verification**

`signDelegationJwt(claims)` → JWT string. `verifyDelegationJwt(jwt, issuer, audience)` → claims map. All ANIP claims: jti, iss, sub, aud, iat, exp, scope, root_principal, capability, parent_token_id, purpose, constraints.

- [ ] **Step 4: Implement detached JWS**

For `X-ANIP-Signature` header on manifest endpoint.

- [ ] **Step 5: Implement JWKS serialization**

`toJwks()` → standard JWKS JSON with both public keys.

- [ ] **Step 6: Tests + commit**

```bash
mvn verify -pl anip-crypto -am
git commit -m "feat(java): add anip-crypto — Nimbus JOSE+JWT"
```

---

## Task 3: anip-server

**Files:**
- Create: `packages/java/anip-server/pom.xml`
- Create: `packages/java/anip-server/src/main/java/dev/anip/server/` — Storage, SqliteStorage, PostgresStorage, DelegationEngine, AuditLog, CheckpointManager

Dependencies: `anip-core`, `anip-crypto`, `org.xerial:sqlite-jdbc`, `com.zaxxer:HikariCP`, `org.postgresql:postgresql`

- [ ] **Step 1: Define Storage interface**

Same methods as Go: storeToken, loadToken, appendAuditEntry, queryAuditEntries, getMaxAuditSequence, getAuditEntriesRange, updateAuditSignature, storeCheckpoint, listCheckpoints, getCheckpointById, deleteExpiredAuditEntries, tryAcquireExclusive, releaseExclusive, tryAcquireLeader, releaseLeader, close.

- [ ] **Step 2: Implement SqliteStorage**

JDBC via xerial. WAL mode. Same schema as Go/Python/TS. Synchronized for thread safety.

- [ ] **Step 3: Implement PostgresStorage**

HikariCP connection pool. `FOR UPDATE` on `audit_append_head`. Lease tables.

- [ ] **Step 4: Implement DelegationEngine**

`issueDelegationToken()`, `resolveBearerToken()`, `validateScope()`. Same claim verification as Go.

- [ ] **Step 5: Implement AuditLog**

Append with atomic sequence, hash chain, signature. Query with filters scoped to root_principal.

- [ ] **Step 6: Implement CheckpointManager**

RFC 6962 Merkle tree. Checkpoint creation, inclusion proof, `proof_unavailable` support.

- [ ] **Step 7: Tests + commit**

```bash
mvn verify -pl anip-server -am
git commit -m "feat(java): add anip-server — storage, delegation, audit, checkpoints"
```

---

## Task 4: anip-service

**Files:**
- Create: `packages/java/anip-service/pom.xml`
- Create: `packages/java/anip-service/src/main/java/dev/anip/service/` — ANIPService, ServiceConfig, ObservabilityHooks, streaming types

Dependencies: `anip-core`, `anip-crypto`, `anip-server`, `com.fasterxml.jackson.core:jackson-databind` (for JSON serialization)

- [ ] **Step 1: Implement ANIPService**

Orchestrates crypto + server. All public methods matching the Go reference. `start()` / `shutdown()` manage storage, keys, and background workers.

- [ ] **Step 2: Implement invocation routing**

Unary invoke: look up capability → validate scope → call handler → audit → return response. Streaming invoke: same but with `BlockingQueue<StreamEvent>`, `emitProgress` callback, cancel support.

- [ ] **Step 3: Implement permissions discovery**

Available/restricted/denied classification based on token scope vs capability minimum_scope.

- [ ] **Step 4: Implement observability hooks**

`ObservabilityHooks` class with nullable consumer fields. Fire at all appropriate points (token issued/resolved, invoke start/complete on ALL paths, audit append, checkpoint created, auth failure, scope validation). Exception-safe.

- [ ] **Step 5: Implement background workers**

`ScheduledExecutorService`. Retention loop with leader lease. Checkpoint loop with leader lease. Configurable intervals.

- [ ] **Step 6: Implement health**

`getHealth()` → HealthReport with status, storage health, uptime, version.

- [ ] **Step 7: Implement discovery + manifest**

Build discovery document matching Go/Python/TS structure exactly. Signed manifest with `X-ANIP-Signature`. JWKS.

- [ ] **Step 8: Tests + commit**

```bash
mvn verify -pl anip-service -am
git commit -m "feat(java): add anip-service — orchestration, hooks, health, streaming"
```

---

## Task 5: anip-spring-boot

**Files:**
- Create: `packages/java/anip-spring-boot/pom.xml`
- Create: `packages/java/anip-spring-boot/src/main/java/dev/anip/spring/` — AnipController, AnipLifecycle, AnipAutoConfiguration

Dependencies: `anip-service`, `org.springframework.boot:spring-boot-starter-web`

- [ ] **Step 1: Implement AnipLifecycle**

`SmartLifecycle` — calls `service.start()` on Spring start, `service.shutdown()` on stop.

- [ ] **Step 2: Implement AnipController**

`@RestController` with all 9 protocol routes + optional `/-/health`. Auth extraction from `Authorization: Bearer`. Token issuance: bootstrap auth. Protected routes: ANIP JWT only. SSE streaming via `SseEmitter`. Discovery `base_url` derived from request.

- [ ] **Step 3: Implement auto-configuration**

`@Configuration` with `@Bean` for controller and lifecycle. Jackson `ObjectMapper` configured for ANIP wire format (snake_case property naming).

- [ ] **Step 4: Tests + commit**

Spring Boot test with `@SpringBootTest` + `TestRestTemplate` or `MockMvc`.

```bash
mvn verify -pl anip-spring-boot -am
git commit -m "feat(java): add anip-spring-boot — Spring MVC binding"
```

---

## Task 6: anip-rest

**Files:**
- Create: `packages/java/anip-rest/pom.xml`
- Create: `packages/java/anip-rest/src/main/java/dev/anip/rest/` — RestController, OpenApiGenerator, AuthBridge

Dependencies: `anip-service`, `spring-boot-starter-web`

- [ ] **Step 1: Implement shared auth bridge**

JWT-first, API-key-fallback. Synthetic token: subject `"adapter:anip-rest"`, scope from `minimum_scope`, purpose `{"source": "rest"}`. Return real issuance error on failure.

- [ ] **Step 2: Implement REST dispatcher controller**

Use a single `@RestController` with a generic dispatcher pattern — NOT dynamic `@RequestMapping` annotation generation (which is not possible at runtime in Spring MVC):

```java
@RestController
public class AnipRestController {
    @GetMapping("/api/{capability}")
    public ResponseEntity<?> handleGet(@PathVariable String capability, HttpServletRequest request) {
        // Route to capability handler based on name, extract query params
    }

    @PostMapping("/api/{capability}")
    public ResponseEntity<?> handlePost(@PathVariable String capability, @RequestBody Map<String, Object> body, HttpServletRequest request) {
        // Route to capability handler based on name, extract body params
    }

    @GetMapping("/rest/openapi.json")
    public ResponseEntity<?> openApi() { ... }

    @GetMapping("/rest/docs")
    public ResponseEntity<?> docs() { ... }
}
```

The controller checks capability side_effect type to enforce GET-only for read capabilities and POST for write/irreversible. Route overrides are checked before the default `/api/{capability}` pattern — if overrides exist, register additional `@RequestMapping` entries programmatically via `RequestMappingHandlerMapping.registerMapping()` at startup.

- [ ] **Step 3: Implement OpenAPI generator**

OpenAPI 3.1 spec from capabilities with `x-anip-*` extensions.

- [ ] **Step 4: Tests + commit**

```bash
mvn verify -pl anip-rest -am
git commit -m "feat(java): add anip-rest — REST interface package"
```

---

## Task 7: anip-graphql

**Files:**
- Create: `packages/java/anip-graphql/pom.xml`
- Create: `packages/java/anip-graphql/src/main/java/dev/anip/graphql/` — GraphQLController, SchemaBuilder, AuthBridge

Dependencies: `anip-service`, `spring-boot-starter-web`, `com.graphql-java:graphql-java`

- [ ] **Step 1: Implement schema builder**

Runtime schema from capabilities. Query for read, Mutation for write. Custom `@anip*` directives. Field names match existing ANIP GraphQL contract. Result types with success, result, costActual, failure.

- [ ] **Step 2: Implement resolvers with auth bridge**

Per-field auth resolution. JWT-first, API-key-fallback. Subject `"adapter:anip-graphql"`. Args: camelCase → snake_case. Results: snake_case → camelCase. Auth errors in result body, not HTTP errors.

- [ ] **Step 3: Implement controller**

POST `/graphql`, GET `/graphql` (playground), GET `/schema.graphql`.

- [ ] **Step 4: Tests + commit**

```bash
mvn verify -pl anip-graphql -am
git commit -m "feat(java): add anip-graphql — GraphQL interface package"
```

---

## Task 8: anip-mcp

**Files:**
- Create: `packages/java/anip-mcp/pom.xml`
- Create: `packages/java/anip-mcp/src/main/java/dev/anip/mcp/` — McpToolRegistry, StdioServer, HttpTransport, AuthBridge

Dependencies: `anip-service`, official MCP Java SDK artifacts (group `io.modelcontextprotocol.sdk`):
- `mcp-spring-webmvc:0.18.1` (Spring WebMVC Streamable HTTP transport provider — includes core SDK transitively)

- [ ] **Step 1: Implement tool translation**

Capability → MCP tool with JSON Schema inputs. Enriched descriptions (side-effect warnings, cost, prerequisites, scope).

- [ ] **Step 2: Implement stdio transport**

Mount-time credentials (`McpCredentials`). Per-call: authenticate → narrow scope → synthetic token → invoke. `isError` set correctly for failures.

- [ ] **Step 3: Implement Streamable HTTP transport**

`WebMvcStreamableServerTransportProvider` with `McpTransportContextExtractor` that extracts `Authorization` header into `McpTransportContext`. Tool handler reads bearer from context → shared auth bridge (JWT-first, API-key-fallback, subject `"adapter:anip-mcp"`).

- [ ] **Step 4: Tests + commit**

```bash
mvn verify -pl anip-mcp -am
git commit -m "feat(java): add anip-mcp — MCP stdio + Streamable HTTP"
```

---

## Task 9: anip-example-flights

**Files:**
- Create: `packages/java/anip-example-flights/pom.xml`
- Create: `packages/java/anip-example-flights/src/main/java/dev/anip/example/flights/` — Application, capabilities, OIDC

Dependencies: all ANIP modules, `spring-boot-starter-web`

- [ ] **Step 1: Implement capabilities**

`search_flights` (read, travel.search) + `book_flight` (irreversible, travel.book, financial). Same test data as Go/Python/TS.

- [ ] **Step 2: Implement application**

Spring Boot `@SpringBootApplication`. Wire all interfaces:
```java
@Bean ANIPService anipService() { ... }
// Spring auto-discovers AnipController from anip-spring-boot
// Mount REST, GraphQL, MCP HTTP controllers
```

API key bootstrap auth. OIDC support via `OIDC_ISSUER_URL` env var.

- [ ] **Step 3: Implement OIDC validator**

Same pattern as Go/TS/Python: discover JWKS, verify RS256, check issuer/audience/expiry, map claims to principals. JWKS cache with kid-miss refresh.

- [ ] **Step 4: Build and run**

```bash
mvn package -pl anip-example-flights
java -jar anip-example-flights/target/anip-example-flights-0.11.0.jar
```

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(java): add example flights app with all interfaces"
```

---

## Task 10: Conformance + CI

- [ ] **Step 1: Run conformance suite**

```bash
cd packages/java/anip-example-flights
mvn spring-boot:run &
sleep 5
cd conformance
pytest --base-url=http://localhost:8080 --bootstrap-bearer=demo-human-key --sample-inputs=samples/flight-service.json -v
```

Must pass 43/44.

- [ ] **Step 2: Fix any failures**

Common issues: JSON field naming (snake_case), missing response fields, wrong status codes, auth error shapes.

- [ ] **Step 3: Create CI workflow**

`.github/workflows/ci-java.yml`:
- Java 17 + 21 matrix
- `mvn verify` for all modules
- Conformance suite against example app
- `java-ci` aggregate status gate

- [ ] **Step 4: Update release workflow**

Add Java artifact publishing (Maven Central preparation — POM metadata, javadoc, sources JARs).

- [ ] **Step 5: Update documentation**

README, SPEC, deployment guide, CONTRIBUTING — add Java as fourth reference runtime.

- [ ] **Step 6: Commit**

```bash
git commit -m "feat(java): conformance passing, CI workflow, docs updated"
```
