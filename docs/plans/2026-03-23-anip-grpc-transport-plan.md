# ANIP gRPC Transport Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the ANIP gRPC transport binding — a shared `.proto` file, Python server/client, and Go server/client. All 10 RPCs (9 protocol operations + streaming invoke) with per-call auth via gRPC metadata.

**Architecture:** Shared `proto/anip/v1/anip.proto` defines the `AnipService`. Python uses `grpcio` + `grpcio-tools` for code generation. Go uses `protoc-gen-go-grpc`. Both wrap `ANIPService` in a gRPC servicer/server. ANIP failures stay in response bodies (not gRPC status codes). gRPC status only for transport errors (UNAUTHENTICATED, INTERNAL).

**Tech Stack:** protobuf 3, `grpcio`/`grpcio-tools` (Python), `google.golang.org/grpc` + `google.golang.org/protobuf` (Go).

**Spec:** `docs/specs/2026-03-23-anip-grpc-transport-design.md`

---

## File Structure

```
proto/anip/v1/
└── anip.proto                    # Shared protobuf service definition

packages/python/anip-grpc/
├── pyproject.toml
├── src/anip_grpc/
│   ├── __init__.py               # exports serve_grpc, AnipGrpcClient
│   ├── server.py                 # gRPC servicer wrapping ANIPService
│   ├── client.py                 # gRPC client
│   └── generated/                # protoc output (checked in)
│       ├── anip_pb2.py
│       ├── anip_pb2.pyi
│       └── anip_pb2_grpc.py
└── tests/
    ├── test_server.py
    └── test_client.py

packages/go/grpcapi/
├── server.go                     # gRPC server wrapping Service
├── server_test.go
└── proto/                        # generated Go protobuf code
    └── anip/v1/
        ├── anip.pb.go
        └── anip_grpc.pb.go
```

---

## Task 1: Shared Proto Definition

**Files:**
- Create: `proto/anip/v1/anip.proto`

The canonical protobuf service definition. 10 RPCs, all message types, the AnipFailure shared type.

- [ ] **Step 1: Create the proto file**

Write the complete `anip.proto` matching the spec: AnipService with 10 RPCs (Discovery, Manifest, Jwks, IssueToken, Permissions, Invoke, InvokeStream, QueryAudit, ListCheckpoints, GetCheckpoint). All request/response messages. InvokeEvent with oneof (progress/completed/failed). AnipFailure shared type.

Use JSON string fields for complex responses (discovery, manifest, jwks, audit, checkpoints, permissions) and typed fields for token issuance and invoke (which have stable shapes).

- [ ] **Step 2: Validate proto syntax**

```bash
protoc --proto_path=proto proto/anip/v1/anip.proto --descriptor_set_out=/dev/null
```

If `protoc` is not installed, install it first. On macOS: `brew install protobuf`.

- [ ] **Step 3: Commit**

```bash
git add proto/
git commit -m "feat(grpc): add shared proto/anip/v1/anip.proto service definition"
```

---

## Task 2: Python gRPC Package — Generated Stubs + Server

**Files:**
- Create: `packages/python/anip-grpc/pyproject.toml`
- Create: `packages/python/anip-grpc/src/anip_grpc/__init__.py`
- Create: `packages/python/anip-grpc/src/anip_grpc/server.py`
- Create: `packages/python/anip-grpc/src/anip_grpc/generated/` (protoc output)
- Create: `packages/python/anip-grpc/tests/test_server.py`

- [ ] **Step 1: Generate Python stubs**

```bash
python -m grpc_tools.protoc \
  --proto_path=proto \
  --python_out=packages/python/anip-grpc/src/anip_grpc/generated \
  --pyi_out=packages/python/anip-grpc/src/anip_grpc/generated \
  --grpc_python_out=packages/python/anip-grpc/src/anip_grpc/generated \
  proto/anip/v1/anip.proto
```

Create `__init__.py` in the generated directory.

- [ ] **Step 2: Create pyproject.toml**

Dependencies: `anip-service==0.11.0`, `grpcio>=1.60.0`, `grpcio-tools>=1.60.0`, `protobuf>=4.25.0`.

- [ ] **Step 3: Create server.py**

`AnipGrpcServicer` extending the generated `AnipServiceServicer`. Each method:
1. Extracts auth from `context.invocation_metadata()` (the `authorization` key)
2. Dispatches to the corresponding `ANIPService` method
3. Returns the protobuf response message
4. For auth failures: `context.abort(grpc.StatusCode.UNAUTHENTICATED, message)`
5. For ANIP failures: returns a normal response with `success=false` and the `AnipFailure` message

`serve_grpc(service, port=50051)` — starts gRPC server with the servicer.

Auth extraction helper:
```python
def _extract_bearer(context) -> str | None:
    for key, value in context.invocation_metadata():
        if key == "authorization" and value.startswith("Bearer "):
            return value[7:].strip()
    return None
```

Token issuance auth: try `authenticate_bearer()` first, then `resolve_bearer_token()`. Other protected RPCs: `resolve_bearer_token()` only.

InvokeStream: call `service.invoke()` with `stream=True` and `_progress_sink`, yield `InvokeEvent` messages for progress, then yield the terminal completed/failed event.

- [ ] **Step 4: Write server tests**

Create an `ANIPService` with an echo capability, start a gRPC server in a test fixture, test all 10 RPCs through a real gRPC channel:
- Discovery returns protocol version
- Manifest returns manifest + signature
- Jwks returns keys
- IssueToken with API key works
- Invoke with JWT returns success
- Invoke without auth returns UNAUTHENTICATED
- InvokeStream returns events
- QueryAudit returns entries
- ListCheckpoints returns list
- GetCheckpoint returns detail

Use `grpc.insecure_channel` for test client connections.

- [ ] **Step 5: Run tests**

```bash
cd packages/python/anip-grpc && pytest tests/ -v
```

- [ ] **Step 6: Commit**

```bash
git add packages/python/anip-grpc/
git commit -m "feat(grpc): add Python anip-grpc package with server and tests"
```

---

## Task 3: Python gRPC Client

**Files:**
- Create: `packages/python/anip-grpc/src/anip_grpc/client.py`
- Create: `packages/python/anip-grpc/tests/test_client.py`
- Update: `packages/python/anip-grpc/src/anip_grpc/__init__.py`

- [ ] **Step 1: Create client.py**

`AnipGrpcClient` — wraps a gRPC channel with typed methods:

```python
class AnipGrpcClient:
    def __init__(self, target: str):
        self._channel = grpc.insecure_channel(target)
        self._stub = AnipServiceStub(self._channel)

    def discovery(self) -> dict: ...
    def manifest(self) -> dict: ...
    def jwks(self) -> dict: ...
    def issue_token(self, bearer: str, **kwargs) -> dict: ...
    def permissions(self, bearer: str) -> dict: ...
    def invoke(self, bearer: str, capability: str, parameters: dict) -> dict: ...
    def invoke_stream(self, bearer: str, capability: str, parameters: dict) -> Iterator[dict]: ...
    def query_audit(self, bearer: str, **kwargs) -> dict: ...
    def list_checkpoints(self, limit: int = 10) -> dict: ...
    def get_checkpoint(self, id: str, **kwargs) -> dict: ...
```

Each method:
1. Builds the protobuf request
2. Sets auth metadata: `metadata=[("authorization", f"Bearer {bearer}")]`
3. Calls the stub
4. Parses the response into a dict

`invoke_stream` returns an iterator of dicts (progress events + terminal).

- [ ] **Step 2: Write client tests**

Start a gRPC server with an echo service, test full flow through the client:
- Discovery → token issuance → invoke → audit query

- [ ] **Step 3: Update __init__.py**

Export `AnipGrpcClient`.

- [ ] **Step 4: Run all tests**

```bash
cd packages/python/anip-grpc && pytest tests/ -v
```

- [ ] **Step 5: Commit**

```bash
git add packages/python/anip-grpc/
git commit -m "feat(grpc): add Python gRPC client"
```

---

## Task 4: Go gRPC Package

**Files:**
- Create: `packages/go/grpcapi/server.go`
- Create: `packages/go/grpcapi/server_test.go`
- Create: `packages/go/grpcapi/proto/anip/v1/` (generated Go code)

- [ ] **Step 1: Generate Go stubs**

```bash
protoc --proto_path=proto \
  --go_out=packages/go/grpcapi/proto --go_opt=paths=source_relative \
  --go-grpc_out=packages/go/grpcapi/proto --go-grpc_opt=paths=source_relative \
  proto/anip/v1/anip.proto
```

Install protoc plugins if needed: `go install google.golang.org/protobuf/cmd/protoc-gen-go@latest` and `go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest`.

- [ ] **Step 2: Create server.go**

`AnipGrpcServer` struct implementing the generated `AnipServiceServer` interface. Same pattern as the Python servicer:
- Auth from metadata (`google.golang.org/grpc/metadata`)
- 10 method implementations dispatching to `service.*`
- UNAUTHENTICATED status for missing auth
- ANIP failures in response bodies, not gRPC status

`ServeGrpc(service *service.Service, port int)` — starts the gRPC server.

- [ ] **Step 3: Write tests**

Create a Service with echo capability, start gRPC server on a random port, test all 10 RPCs through a real gRPC client.

- [ ] **Step 4: Update go.mod**

Add gRPC and protobuf dependencies:
```bash
cd packages/go && go get google.golang.org/grpc google.golang.org/protobuf
```

- [ ] **Step 5: Run tests**

```bash
cd packages/go && go test ./grpcapi/ -v
```

- [ ] **Step 6: Commit**

```bash
git add packages/go/grpcapi/ proto/
git commit -m "feat(grpc): add Go grpcapi package with server and tests"
```

---

## Task 5: CI + Release + PR

**Files:**
- Modify: `.github/workflows/release.yml` — add `anip-grpc` to Python validation/publish
- Modify: `.github/workflows/ci-python.yml` — add `anip-grpc` install + test
- Modify: `.github/workflows/ci-go.yml` — Go tests already run `./...` so grpcapi is covered

- [ ] **Step 1: Update Python CI**

Add `anip-grpc` to the install and test steps in `ci-python.yml`.

- [ ] **Step 2: Update release workflow**

Add `anip-grpc` to Python validation and publish loops.

- [ ] **Step 3: Verify Go CI covers grpcapi**

Go CI runs `go test ./...` which includes `grpcapi/`. No changes needed unless protoc-generated files require special handling.

- [ ] **Step 4: End-to-end test**

Start the travel showcase as a gRPC server, run a client test against it:
```python
from anip_grpc import AnipGrpcClient
client = AnipGrpcClient("localhost:50051")
discovery = client.discovery()
assert "anip_discovery" in discovery
```

- [ ] **Step 5: Push and create PR**

```bash
git push -u origin feat/anip-grpc
gh pr create --title "feat: add ANIP gRPC transport binding (Python + Go)"
```
