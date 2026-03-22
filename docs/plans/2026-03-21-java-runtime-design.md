# Java ANIP Runtime Design

**Goal:** Implement a full-parity Java ANIP runtime with Spring Boot binding, all interface packages, and production features — passing the conformance suite from day one.

**Architecture:** Multi-module Maven project at `packages/java/`. Core runtime (types, crypto, delegation, audit, checkpoints, storage, leases, hooks, health, retention, checkpoint scheduling, streaming) plus Spring Boot binding, REST, GraphQL, and MCP interface packages. Java 17 target.

**Tech Stack:** Java 17, Maven, Spring Boot 3.x, Nimbus JOSE+JWT, xerial sqlite-jdbc, HikariCP + PostgreSQL JDBC, graphql-java, official MCP Java SDK

---

## Module Structure

```
packages/java/
├── pom.xml                          # parent POM, Java 17, lockstep 0.11.0
├── anip-core/                       # types, models, constants (no external deps)
├── anip-crypto/                     # Nimbus JOSE+JWT: keys, JWT, JWS, JWKS
├── anip-server/                     # delegation, audit, checkpoints, storage, leases
├── anip-service/                    # orchestration, hooks, health, background workers
├── anip-spring-boot/                # Spring MVC binding (mount routes)
├── anip-rest/                       # REST interface (OpenAPI + endpoints)
├── anip-graphql/                    # GraphQL interface (SDL + resolvers)
├── anip-mcp/                        # MCP interface (stdio + Streamable HTTP)
└── anip-example-flights/            # example Spring Boot app
```

**Group ID:** `dev.anip`
**Package namespace:** `dev.anip.*`
**Version:** `0.11.0` (lockstep with protocol)

## Dependencies

| Module | Key Dependencies |
|--------|-----------------|
| `anip-core` | None (plain Java POJOs, no Jackson) |
| `anip-crypto` | Nimbus JOSE+JWT |
| `anip-server` | `anip-core`, `anip-crypto`, xerial sqlite-jdbc, HikariCP, postgresql JDBC |
| `anip-service` | `anip-core`, `anip-crypto`, `anip-server`, Jackson (for JSON serialization) |
| `anip-spring-boot` | `anip-service`, Spring Web MVC |
| `anip-rest` | `anip-service`, Spring Web MVC |
| `anip-graphql` | `anip-service`, graphql-java |
| `anip-mcp` | `anip-service`, MCP Java SDK (official) |
| `anip-example-flights` | all of the above, Spring Boot Starter Web |

## Core Types (`anip-core`)

Dependency-free. Plain Java POJOs with public fields or records.

Key types:
- `CapabilityDeclaration` — name, description, inputs, output, side_effect, minimum_scope, cost, requires, response_modes
- `SideEffect` — type (read/write/irreversible/transactional), rollback_window
- `Cost`, `CostActual` — certainty, financial, compute
- `DelegationToken` — token_id, subject, scope, purpose, constraints, root_principal, expires
- `ANIPError extends RuntimeException` — error_type, detail, resolution, retry
- `InvokeResponse`, `TokenResponse`, `PermissionResponse`, `AuditEntry`, `Checkpoint`
- Protocol constants: `PROTOCOL_VERSION = "anip/0.11"`, failure type strings

No JSON annotations in core — serialization is handled by higher modules (Jackson in service/spring layers).

## Crypto (`anip-crypto`)

Uses Nimbus JOSE+JWT for all JOSE operations.

- `KeyManager` — generate/load/store two ES256 key pairs (delegation + audit)
- `JwtSigner` — sign delegation tokens as ES256 JWTs with all ANIP claims
- `JwtVerifier` — verify and decode, check expiry/issuer/audience
- `JwsSigner` — detached JWS for manifest (`X-ANIP-Signature`)
- `JwksSerializer` — serialize public keys as JWKS

## Server (`anip-server`)

### Storage

JDBC-based `Storage` interface:

```java
public interface Storage extends Closeable {
    void storeToken(DelegationToken token);
    DelegationToken loadToken(String tokenId);
    AuditEntry appendAuditEntry(AuditEntry entry);
    List<AuditEntry> queryAuditEntries(AuditFilters filters);
    int getMaxAuditSequence();
    List<AuditEntry> getAuditEntriesRange(int first, int last);
    void updateAuditSignature(int seqNum, String signature);
    void storeCheckpoint(Checkpoint cp, String signature);
    List<Checkpoint> listCheckpoints(int limit);
    Checkpoint getCheckpointById(String id);
    int deleteExpiredAuditEntries(String now);
    boolean tryAcquireExclusive(String key, String holder, int ttlSeconds);
    void releaseExclusive(String key, String holder);
    boolean tryAcquireLeader(String role, String holder, int ttlSeconds);
    void releaseLeader(String role, String holder);
}
```

**SQLite:** via xerial `sqlite-jdbc`. WAL mode. Same schema as Go/Python/TS.
**PostgreSQL:** via HikariCP connection pool + PostgreSQL JDBC. `FOR UPDATE` on `audit_append_head`. Full lease tables.

### Delegation Engine

- `issueDelegationToken` — create, sign JWT, store
- `resolveBearerToken` — verify JWT, load stored token, compare all signed claims
- `validateScope` — check token scope covers capability minimum_scope

### Audit Log

- Append with atomic sequence assignment, hash chain, signature
- Query with filters (capability, since, invocation_id, limit), scoped to root_principal

### Checkpoints

- RFC 6962 Merkle tree (leaf: `SHA256(0x00 || data)`, node: `SHA256(0x01 || left || right)`)
- Inclusion proof with `proof_unavailable: "audit_entries_expired"` support
- Pagination via next_cursor

## Service (`anip-service`)

### ANIPService

```java
public class ANIPService {
    public ANIPService(ServiceConfig config);
    public void start();
    public void shutdown();

    // Auth
    public Optional<String> authenticateBearer(String bearer);
    public DelegationToken resolveBearerToken(String jwt);
    public TokenResponse issueToken(String principal, TokenRequest req);

    // Invocation
    public Map<String, Object> invoke(String capName, DelegationToken token, Map<String, Object> params, InvokeOpts opts);
    public StreamResult invokeStream(String capName, DelegationToken token, Map<String, Object> params, InvokeOpts opts);

    // Discovery
    public Map<String, Object> getDiscovery(String baseUrl);
    public Object getManifest();
    public SignedManifest getSignedManifest();
    public Map<String, Object> getJwks();
    public CapabilityDeclaration getCapabilityDeclaration(String name);

    // Permissions & Audit
    public PermissionResponse discoverPermissions(DelegationToken token);
    public AuditResponse queryAudit(DelegationToken token, AuditFilters filters);

    // Checkpoints
    public CheckpointListResponse listCheckpoints(int limit);
    public CheckpointDetailResponse getCheckpoint(String id, boolean includeProof, int leafIndex);

    // Health
    public HealthReport getHealth();
}
```

### Auth callback

```java
Function<String, Optional<String>> authenticate;
```

Bootstrap auth only. Returns principal or empty.

### Observability Hooks

```java
public class ObservabilityHooks {
    public Consumer<TokenEvent> onTokenIssued;
    public Consumer<TokenEvent> onTokenResolved;
    public Consumer<InvokeEvent> onInvokeStart;
    public Consumer<InvokeCompleteEvent> onInvokeComplete;
    public Consumer<AuditEvent> onAuditAppend;
    public Consumer<CheckpointEvent> onCheckpointCreated;
    public Consumer<AuthFailureEvent> onAuthFailure;
    public BiConsumer<String, Boolean> onScopeValidation;
    public Consumer<InvokeDurationEvent> onInvokeDuration;
}
```

All nullable. Exceptions in hooks are caught and logged, never propagate.

### Background Workers

`ScheduledExecutorService` with two tasks:
- **Retention enforcement** — acquire leader lease, delete expired audit entries
- **Checkpoint scheduling** — acquire leader lease, create checkpoint if enough new entries

Both configurable (interval, min entries). Leader lease acquisition on every iteration, not just startup.

### Streaming

`InvokeContext.emitProgress(payload)` callback. For unary mode: no-op. For streaming: pushes to a `BlockingQueue<StreamEvent>`. Terminal event: exactly one completed/failed, then queue closes. `emitProgress` returns false if stream closed (client disconnected).

## Spring Boot Binding (`anip-spring-boot`)

### Lifecycle Wiring

`ANIPService` lifecycle is managed via Spring's `SmartLifecycle`:

```java
@Configuration
public class AnipAutoConfiguration {
    @Bean
    public AnipController anipController(ANIPService service) {
        return new AnipController(service);
    }

    @Bean
    public AnipLifecycle anipLifecycle(ANIPService service) {
        return new AnipLifecycle(service);
    }
}

public class AnipLifecycle implements SmartLifecycle {
    private final ANIPService service;
    private boolean running = false;

    public void start() {
        service.start();    // init storage, keys, background workers
        running = true;
    }
    public void stop() {
        service.shutdown(); // stop workers, close storage
        running = false;
    }
    public boolean isRunning() { return running; }
    public int getPhase() { return 0; } // start early, stop late
}
```

This ensures:
- `service.start()` runs after Spring context is ready (storage init, key loading, background workers start)
- `service.shutdown()` runs on application stop (workers stop, storage closes)
- Background workers (retention, checkpoint) are fully managed by the Spring lifecycle

### Controller

`AnipController` is a `@RestController` with all 9 protocol endpoints. SSE streaming via `SseEmitter`. `/-/health` endpoint (not Actuator).

Auth extraction from `Authorization: Bearer` header. Same patterns as other bindings:
- Token issuance: bootstrap auth only
- Protected routes: ANIP JWT only, no API key fallback

## Interface Packages

### Auth Bridge (shared by REST, GraphQL, MCP HTTP)

All three interface packages use the same auth resolution pattern. When a bearer token is received:

1. Try `service.resolveBearerToken(bearer)` — JWT mode, preserves delegation chain
2. If `ANIPError` → try `service.authenticateBearer(bearer)` — API key mode
3. If API key succeeds → issue synthetic token:
   - **subject:** `"adapter:anip-{package}"` (e.g., `"adapter:anip-rest"`, `"adapter:anip-graphql"`, `"adapter:anip-mcp"`)
   - **scope:** from the capability's `minimum_scope` (or `["*"]` if empty)
   - **capability:** bound to the specific capability being invoked
   - **purpose_parameters:** `{"source": "rest"}`, `{"source": "graphql"}`, or `{"source": "mcp"}`
4. If token issuance fails → return the actual issuance error (not the stale JWT error)
5. If neither JWT nor API key → re-throw the original JWT `ANIPError`
6. Only catch `ANIPError` from JWT resolution — rethrow unexpected exceptions

### REST (`anip-rest`)

Spring MVC `@RestController` auto-generated from capabilities. GET for read, POST for write/irreversible. Route overrides. OpenAPI at `/rest/openapi.json`, Swagger UI at `/rest/docs`. Uses the shared auth bridge above.

### GraphQL (`anip-graphql`)

`graphql-java` runtime schema. Query for read, Mutation for write. Custom `@anip*` directives. Field names match the existing ANIP GraphQL contract exactly. Auth errors in result body, not HTTP errors. Uses the shared auth bridge — auth resolved per-field in the resolver, not at the HTTP layer.

### MCP (`anip-mcp`)

Official MCP Java SDK.

**Stdio transport:** Mount-time credentials required:
```java
McpCredentials credentials = new McpCredentials(apiKey, scope, subject);
AnipMcpServer.mountStdio(service, credentials, options);
```
Each tool call: authenticate API key → narrow scope to capability's `minimum_scope` → issue synthetic token (subject from credentials, purpose `{"source": "mcp"}`) → invoke with resolved token.

**Streamable HTTP transport:** Per-request auth from `Authorization: Bearer` header via the SDK's `McpTransportContext` mechanism.

The MCP Java SDK does NOT pass HTTP headers to tool handlers by default — `McpTransportContext` is empty unless a `McpTransportContextExtractor` is configured on the transport provider.

Concrete wiring:

```java
WebMvcStreamableServerTransportProvider.builder()
    .contextExtractor((serverRequest) -> {
        Map<String, Object> context = new HashMap<>();
        String auth = serverRequest.headers().firstHeader("Authorization");
        if (auth != null) {
            context.put("authorization", auth);
        }
        return McpTransportContext.create(context);
    })
    .build();
```

Tool handler reads the bearer from `McpTransportContext`:

```java
@Tool("search_flights")
public ToolResponse searchFlights(McpTransportContext ctx, Map<String, Object> args) {
    String auth = (String) ctx.getAttribute("authorization");
    String bearer = extractBearer(auth); // strip "Bearer " prefix
    DelegationToken token = resolveAuth(bearer, service, "search_flights");
    // ... invoke with resolved token
}
```

This is the same pattern as TypeScript's `HandleRequestOptions.authInfo` and Go's `WithHTTPContextFunc` — the transport layer injects auth context, the tool handler resolves it.

## Example App

Spring Boot application at `anip-example-flights/`:
- `search_flights` (read) + `book_flight` (irreversible, financial)
- All interfaces mounted (ANIP, REST, GraphQL, MCP HTTP)
- API key bootstrap auth
- OIDC support via env vars (same pattern as Go/TS/Python)
- Same test data as other implementations

## Testing

- Unit tests per module (JUnit 5)
- Conformance suite: must pass 43/44 against Spring Boot example app
- CI: Java 17 + 21 matrix, conformance workflow

## What This Delivers

Full parity with Go, TypeScript, and Python:
- All protocol endpoints
- All storage backends (SQLite + PostgreSQL)
- All production features (leases, hooks, health, retention, checkpoints)
- Streaming SSE
- All interface packages (REST, GraphQL, MCP)
- Conformance-validated

## What This Defers

- Quarkus binding (Phase 2 per framework-targets doc)
- Maven Central publishing automation (same-release but not parity-defining)
