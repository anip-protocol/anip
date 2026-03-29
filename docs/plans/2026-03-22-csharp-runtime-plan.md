# C# ANIP Runtime Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the core C# ANIP runtime with SQLite storage and ASP.NET Core binding that passes the 44-test conformance suite. This is the foundation — like early Go was. PostgreSQL storage, interface packages (REST, GraphQL, MCP), and full cross-runtime parity are follow-up work.

**Architecture:** .NET 8 solution at `packages/csharp/` with 6 projects: `Anip.Core` (models), `Anip.Crypto` (keys/JWT/JWS), `Anip.Server` (storage/delegation/audit/checkpoints — SQLite only), `Anip.Service` (orchestration + security hardening), `Anip.AspNetCore` (9 protocol endpoints), `Anip.Example.Flights` (example app). Bottom-up build order. Go runtime is the reference implementation for logic; Java for structural patterns.

**Not in this plan (follow-up work):**
- PostgreSQL storage backend
- Interface packages: `Anip.Rest`, `Anip.GraphQL`, `Anip.Mcp`
- ASP.NET Core adapters for interface packages
- Release/publishing infrastructure (NuGet)

**Tech Stack:** .NET 8, C# 12, `System.Text.Json`, `Microsoft.IdentityModel.Tokens` (EC P-256 JWT/JWS), `Microsoft.Data.Sqlite`, xUnit.

---

## Solution Structure

```
packages/csharp/
├── Anip.sln
├── src/
│   ├── Anip.Core/              # Models, constants, error types
│   ├── Anip.Crypto/            # KeyManager, JWT, JWS, JWKS
│   ├── Anip.Server/            # IStorage, SQLite, delegation, audit, checkpoints
│   ├── Anip.Service/           # Service orchestration, invoke, hooks, security hardening
│   ├── Anip.AspNetCore/        # ASP.NET Core binding (controllers, lifecycle)
│   └── Anip.Example.Flights/   # Example app
└── test/
    ├── Anip.Core.Tests/
    ├── Anip.Crypto.Tests/
    ├── Anip.Server.Tests/
    ├── Anip.Service.Tests/
    └── Anip.AspNetCore.Tests/
```

---

## Task 1: Solution Scaffold + Anip.Core

**Goal:** Create the .NET solution, Anip.Core project with all model types, constants, and ANIPError.

**Files to create:**
- `packages/csharp/Anip.sln`
- `packages/csharp/src/Anip.Core/Anip.Core.csproj`
- `packages/csharp/src/Anip.Core/Constants.cs`
- `packages/csharp/src/Anip.Core/AnipError.cs`
- `packages/csharp/src/Anip.Core/Models/` — all model classes
- `packages/csharp/test/Anip.Core.Tests/Anip.Core.Tests.csproj`
- `packages/csharp/test/Anip.Core.Tests/ConstantsTests.cs`
- `packages/csharp/test/Anip.Core.Tests/AnipErrorTests.cs`

**Key decisions:**
- Target `net8.0`
- Use `System.Text.Json` with `JsonPropertyName` attributes for snake_case
- Use C# records for immutable types where appropriate (TokenResponse, PermissionResponse)
- Use classes with properties for mutable types (AuditEntry, DelegationToken)
- `ANIPError` extends `Exception` with `ErrorType`, `Detail`, `Resolution`, `Retry` properties

**Model classes to create (match Go `core/models.go`):**
- `SideEffect`, `CapabilityDeclaration`, `CapabilityInput`, `CapabilityOutput`
- `CapabilityRequirement`, `Cost`, `CostActual`
- `DelegationToken`, `DelegationConstraints`, `Purpose`
- `TokenRequest`, `TokenResponse`
- `AuditEntry`, `AuditFilters`, `AuditResponse`
- `Checkpoint`, `CheckpointListResponse`, `CheckpointDetailResponse`
- `PermissionResponse`, `AvailableCapability`, `RestrictedCapability`, `DeniedCapability`
- `AnipManifest`, `ProfileVersions`, `ManifestMetadata`, `ServiceIdentity`, `TrustPosture`
- `DiscoveryPosture`, `AuditPosture`, `LineagePosture`, `MetadataPolicy`, `FailureDisclosure`, `AnchoringPosture`
- `HealthReport`, `StorageHealth`
- `Resolution`, `InvokeResponse`

**Constants.cs** — protocol version `"anip/0.11"`, 13 failure type strings, `FailureStatusCode()` method, `GenerateInvocationId()`, default profile, Merkle hash prefixes.

**Tests:** Verify `GenerateInvocationId()` format (`inv-{hex12}`), `FailureStatusCode()` mapping, `ANIPError` construction.

- [ ] Create solution and project files via `dotnet new`
- [ ] Implement all model classes
- [ ] Implement Constants and ANIPError
- [ ] Write and run tests
- [ ] Commit: `feat(csharp): add Anip.Core with models, constants, error types`

---

## Task 2: Anip.Crypto

**Goal:** EC P-256 key management, JWT signing/verification, detached JWS, JWKS serialization.

**Files to create:**
- `packages/csharp/src/Anip.Crypto/Anip.Crypto.csproj`
- `packages/csharp/src/Anip.Crypto/KeyManager.cs`
- `packages/csharp/src/Anip.Crypto/JwtSigner.cs`
- `packages/csharp/src/Anip.Crypto/JwtVerifier.cs`
- `packages/csharp/src/Anip.Crypto/JwsSigner.cs`
- `packages/csharp/src/Anip.Crypto/JwksSerializer.cs`
- `packages/csharp/test/Anip.Crypto.Tests/Anip.Crypto.Tests.csproj`
- `packages/csharp/test/Anip.Crypto.Tests/KeyManagerTests.cs`
- `packages/csharp/test/Anip.Crypto.Tests/JwtTests.cs`
- `packages/csharp/test/Anip.Crypto.Tests/JwsTests.cs`
- `packages/csharp/test/Anip.Crypto.Tests/JwksTests.cs`

**Key decisions:**
- Use `System.Security.Cryptography.ECDsa` for P-256 key generation (built-in, no external dep)
- Use `Microsoft.IdentityModel.Tokens` + `System.IdentityModel.Tokens.Jwt` for JWT operations
- Key persistence: JSON file at `keyPath` directory (same format as Go/Java: JWK with private key)
- Detached JWS: Base64url-encode the SHA-256 hash, sign with ES256, return compact JWS with empty payload
- JWKS: Standard `{"keys": [{kty, crv, x, y, kid}]}` format

**KeyManager:**
- `KeyManager(string keyPath)` — load or generate EC P-256 key pair
- Separate signing key and audit key (two key pairs)
- `GetSigningKey()`, `GetAuditKey()`, `GetPublicJwks()`

**JwtSigner:**
- `SignToken(DelegationToken token, string issuer)` → JWT string
- Claims: `sub`, `scope`, `capability`, `purpose`, `iss`, `exp`, `jti`

**JwtVerifier:**
- `VerifyToken(string jwt, ECDsa publicKey, string expectedIssuer)` → parsed claims
- Validates: signature, expiry, issuer

**Tests:** Key generation, key persistence round-trip, JWT sign/verify, JWS sign/verify, JWKS format.

- [ ] Create project with NuGet deps
- [ ] Implement KeyManager
- [ ] Implement JwtSigner + JwtVerifier
- [ ] Implement JwsSigner
- [ ] Implement JwksSerializer
- [ ] Write and run tests
- [ ] Commit: `feat(csharp): add Anip.Crypto with EC P-256 key management and JWT/JWS`

---

## Task 3: Anip.Server

**Goal:** Storage interface, SQLite implementation, delegation engine, audit log, checkpoint manager, Merkle tree.

**Files to create:**
- `packages/csharp/src/Anip.Server/Anip.Server.csproj`
- `packages/csharp/src/Anip.Server/IStorage.cs`
- `packages/csharp/src/Anip.Server/SqliteStorage.cs`
- `packages/csharp/src/Anip.Server/DelegationEngine.cs`
- `packages/csharp/src/Anip.Server/AuditLog.cs`
- `packages/csharp/src/Anip.Server/CheckpointManager.cs`
- `packages/csharp/src/Anip.Server/MerkleTree.cs`
- `packages/csharp/src/Anip.Server/HashChain.cs`
- `packages/csharp/test/Anip.Server.Tests/Anip.Server.Tests.csproj`
- `packages/csharp/test/Anip.Server.Tests/SqliteStorageTests.cs`
- `packages/csharp/test/Anip.Server.Tests/DelegationEngineTests.cs`
- `packages/csharp/test/Anip.Server.Tests/AuditLogTests.cs`
- `packages/csharp/test/Anip.Server.Tests/CheckpointManagerTests.cs`
- `packages/csharp/test/Anip.Server.Tests/MerkleTreeTests.cs`

**Key decisions:**
- `IStorage` interface mirrors Go's `Storage` interface exactly (tokens, audit, checkpoints, retention, leases)
- SQLite via `Microsoft.Data.Sqlite` — WAL mode, synchronized access
- PostgreSQL is NOT in this plan — the `IStorage` interface supports it, but `NpgsqlStorage` is follow-up work
- Merkle tree: RFC 6962 hash scheme (0x00 leaf prefix, 0x01 node prefix, SHA-256)
- HashChain: SHA-256 chain linking audit entries
- DelegationEngine: token issuance, scope validation, scope narrowing
- AuditLog: append with hash chain + signature, query with filters

**IStorage interface:**
```csharp
public interface IStorage : IDisposable
{
    // Tokens
    void StoreToken(DelegationToken token);
    DelegationToken? LoadToken(string tokenId);

    // Audit
    AuditEntry AppendAuditEntry(AuditEntry entry);
    List<AuditEntry> QueryAuditEntries(AuditFilters filters);
    int GetMaxAuditSequence();
    List<AuditEntry> GetAuditEntriesRange(int first, int last);
    void UpdateAuditSignature(int seqNum, string signature);

    // Checkpoints
    void StoreCheckpoint(Checkpoint checkpoint, string signature);
    List<Checkpoint> ListCheckpoints(int limit);
    Checkpoint? GetCheckpointById(string id);

    // Retention
    int DeleteExpiredAuditEntries(string now);

    // Leases
    bool TryAcquireExclusive(string key, string holder, int ttlSeconds);
    void ReleaseExclusive(string key, string holder);
    bool TryAcquireLeader(string role, string holder, int ttlSeconds);
    void ReleaseLeader(string role, string holder);
}
```

**Tests:** SQLite CRUD operations, delegation scope validation, audit chain integrity, Merkle tree construction + inclusion proofs, lease acquisition/release.

- [ ] Create project with NuGet deps
- [ ] Implement IStorage interface
- [ ] Implement SqliteStorage
- [ ] Implement DelegationEngine
- [ ] Implement AuditLog + HashChain
- [ ] Implement CheckpointManager + MerkleTree
- [ ] Write and run tests
- [ ] Commit: `feat(csharp): add Anip.Server with storage, delegation, audit, checkpoints`

---

## Task 4: Anip.Service

**Goal:** Service orchestration — the main `AnipService` class that ties everything together, plus security hardening features.

**Files to create:**
- `packages/csharp/src/Anip.Service/Anip.Service.csproj`
- `packages/csharp/src/Anip.Service/ServiceConfig.cs`
- `packages/csharp/src/Anip.Service/AnipService.cs`
- `packages/csharp/src/Anip.Service/CapabilityDef.cs`
- `packages/csharp/src/Anip.Service/InvocationContext.cs`
- `packages/csharp/src/Anip.Service/InvokeOpts.cs`
- `packages/csharp/src/Anip.Service/ObservabilityHooks.cs`
- `packages/csharp/src/Anip.Service/EventClassification.cs`
- `packages/csharp/src/Anip.Service/RetentionPolicy.cs`
- `packages/csharp/src/Anip.Service/FailureRedaction.cs`
- `packages/csharp/src/Anip.Service/DisclosureControl.cs`
- `packages/csharp/src/Anip.Service/StorageRedaction.cs`
- `packages/csharp/src/Anip.Service/AuditAggregator.cs`
- `packages/csharp/src/Anip.Service/StreamEvent.cs`
- `packages/csharp/src/Anip.Service/StreamResult.cs`
- `packages/csharp/src/Anip.Service/SignedManifest.cs`
- `packages/csharp/test/Anip.Service.Tests/Anip.Service.Tests.csproj`
- `packages/csharp/test/Anip.Service.Tests/AnipServiceTests.cs`
- `packages/csharp/test/Anip.Service.Tests/EventClassificationTests.cs`
- `packages/csharp/test/Anip.Service.Tests/RetentionPolicyTests.cs`
- `packages/csharp/test/Anip.Service.Tests/FailureRedactionTests.cs`
- `packages/csharp/test/Anip.Service.Tests/DisclosureControlTests.cs`
- `packages/csharp/test/Anip.Service.Tests/StorageRedactionTests.cs`
- `packages/csharp/test/Anip.Service.Tests/AuditAggregatorTests.cs`

**Key decisions:**
- `AnipService` is the main class — same API as Go/Java: `Start()`, `Shutdown()`, `Invoke()`, `InvokeStream()`, `IssueToken()`, `QueryAudit()`, `GetDiscovery()`, `GetManifest()`, `GetSignedManifest()`, `GetJwks()`, `DiscoverPermissions()`, `ListCheckpoints()`, `GetCheckpoint()`, `GetHealth()`
- `CapabilityDef` binds a declaration to a `Func<InvocationContext, Dictionary<string, object>, Dictionary<string, object>>` handler
- `Authenticate` config field: `Func<string, string?>` (bearer → principal or null)
- Background workers: retention + checkpoint + aggregator flush via `Task.Run` + `CancellationToken`
- Security hardening (classification, retention, redaction, disclosure, aggregation, storage redaction) — same implementations as Go/Java, ported to C#
- Streaming: `StreamResult` with `Channel<StreamEvent>` (similar to Go channel / Java BlockingQueue)

**Tests:** Service lifecycle, invoke success/failure, token issuance, permissions, audit query, security hardening (classification, retention, redaction, disclosure, aggregation).

- [ ] Create project
- [ ] Implement ServiceConfig + CapabilityDef + InvocationContext
- [ ] Implement security hardening utilities (classification, retention, redaction, disclosure, aggregation, storage redaction)
- [ ] Implement AnipService (core methods)
- [ ] Implement streaming support
- [ ] Implement background workers
- [ ] Write and run tests
- [ ] Commit: `feat(csharp): add Anip.Service with orchestration and security hardening`

---

## Task 5: Anip.AspNetCore

**Goal:** ASP.NET Core binding — 9 ANIP protocol endpoints + health, lifecycle management.

**Files to create:**
- `packages/csharp/src/Anip.AspNetCore/Anip.AspNetCore.csproj`
- `packages/csharp/src/Anip.AspNetCore/AnipController.cs`
- `packages/csharp/src/Anip.AspNetCore/AnipLifecycle.cs`
- `packages/csharp/src/Anip.AspNetCore/AnipServiceExtensions.cs`
- `packages/csharp/test/Anip.AspNetCore.Tests/Anip.AspNetCore.Tests.csproj`
- `packages/csharp/test/Anip.AspNetCore.Tests/AnipControllerTests.cs`

**Key decisions:**
- Use `[ApiController]` + `[Route]` attribute routing
- Endpoints: `GET /.well-known/anip`, `GET /.well-known/jwks.json`, `GET /anip/manifest`, `POST /anip/tokens`, `POST /anip/permissions`, `POST /anip/invoke/{capability}`, `POST /anip/audit`, `GET /anip/checkpoints`, `GET /anip/checkpoints/{id}`, `GET /-/health`
- `AnipServiceExtensions.AddAnip()` — DI registration
- `AnipServiceExtensions.UseAnip()` — middleware + lifecycle
- `AnipLifecycle` implements `IHostedService` for start/shutdown
- SSE streaming: use `Response.Body` with `text/event-stream` content type
- Auth — route-specific policy (critical, do not mix):
  - `POST /anip/tokens` — **bootstrap auth only**: extract Bearer, call `AnipService.AuthenticateBearer(bearer)` → principal string. API keys resolve here. Do NOT accept ANIP JWTs on this endpoint.
  - `POST /anip/permissions`, `POST /anip/invoke/{capability}`, `POST /anip/audit` — **ANIP JWT only**: extract Bearer, call `AnipService.ResolveBearerToken(bearer)` → `DelegationToken`. Do NOT fall back to API key auth on these endpoints.
  - `GET /.well-known/anip`, `GET /.well-known/jwks.json`, `GET /anip/manifest`, `GET /anip/checkpoints`, `GET /anip/checkpoints/{id}` — **no auth required**
  - `GET /-/health` — **no auth required**, conditional on config flag

**Tests:** Use `WebApplicationFactory<>` for integration testing — same coverage as Spring/Quarkus tests.

- [ ] Create project
- [ ] Implement AnipController (all 9 endpoints + health)
- [ ] Implement AnipLifecycle (IHostedService)
- [ ] Implement AnipServiceExtensions (DI + middleware)
- [ ] Write and run tests
- [ ] Commit: `feat(csharp): add Anip.AspNetCore with 9 protocol endpoints`

---

## Task 6: Example Flights App

**Goal:** Working ASP.NET Core app with SearchFlights + BookFlight capabilities that passes conformance.

**Files to create:**
- `packages/csharp/src/Anip.Example.Flights/Anip.Example.Flights.csproj`
- `packages/csharp/src/Anip.Example.Flights/Program.cs`
- `packages/csharp/src/Anip.Example.Flights/SearchFlightsCapability.cs`
- `packages/csharp/src/Anip.Example.Flights/BookFlightCapability.cs`
- `packages/csharp/src/Anip.Example.Flights/FlightData.cs`

**Key decisions:**
- Use Minimal API style (`WebApplication.CreateBuilder` + `builder.Services.AddAnip()` + `app.UseAnip()`). The controller lives in Anip.AspNetCore; the example app just configures services and capabilities.
- API keys: `demo-human-key` → `human:samir@example.com`, `demo-agent-key` → `agent:demo-agent`
- In-memory storage by default, configurable via env vars
- Same flight data as Go/Java/Python examples

- [ ] Create project
- [ ] Implement capabilities
- [ ] Implement Program.cs with DI setup
- [ ] Build and run: `dotnet run`
- [ ] Commit: `feat(csharp): add example flights app`

---

## Task 7: Conformance + CI

**Goal:** Pass the conformance suite, add CI workflow.

- [ ] **Step 1: Run conformance**

```bash
cd packages/csharp/src/Anip.Example.Flights
dotnet run &
sleep 5
pytest conformance/ \
  --base-url=http://localhost:8080 \
  --bootstrap-bearer=demo-human-key \
  --sample-inputs=conformance/samples/flight-service.json \
  -v
```

Expected: 43 passed, 1 skipped

- [ ] **Step 2: Fix any failures and re-run**

- [ ] **Step 3: Create CI workflow**

Create `.github/workflows/ci-csharp.yml`:
- Path filter: `packages/csharp/**`
- .NET 8 matrix
- `dotnet test` for all test projects
- Conformance job: build + start example, run pytest

- [ ] **Step 4: Update .gitignore**

Add .NET build outputs: `bin/`, `obj/`, `*.user`, `.vs/`

- [ ] **Step 5: Commit and create PR**

```bash
git add packages/csharp/ .github/workflows/ci-csharp.yml .gitignore
git commit -m "feat: add C# ANIP runtime (full parity)"
```

---

## Implementation Notes

### NuGet Dependencies

| Project | Dependencies |
|---------|-------------|
| Anip.Core | `System.Text.Json` (built-in) |
| Anip.Crypto | `Microsoft.IdentityModel.Tokens`, `System.IdentityModel.Tokens.Jwt` |
| Anip.Server | `Microsoft.Data.Sqlite` |
| Anip.Service | Anip.Core, Anip.Crypto, Anip.Server |
| Anip.AspNetCore | Anip.Service, `Microsoft.AspNetCore.App` (framework ref) |
| Tests | `xunit`, `xunit.runner.visualstudio`, `Microsoft.NET.Test.Sdk` |

### JSON Serialization Convention

All models use `System.Text.Json` with snake_case naming:
```csharp
var options = new JsonSerializerOptions
{
    PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
    DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
    WriteIndented = false
};
```

### Port

The example app listens on port 8080 to match all other runtimes. Set in `Program.cs` via `builder.WebHost.UseUrls("http://0.0.0.0:8080")`.

### Build Commands

```bash
# Build all
cd packages/csharp && dotnet build

# Run tests
cd packages/csharp && dotnet test

# Run example
cd packages/csharp/src/Anip.Example.Flights && dotnet run

# Publish for deployment
dotnet publish src/Anip.Example.Flights -c Release -o publish/
```
