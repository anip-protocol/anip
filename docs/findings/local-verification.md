# Running each language's checks locally, the way CI does

Commands that were run and worked while preparing 0.24.18
([#316](https://github.com/anip-protocol/anip/pull/316)) and the Python MCP port
([#318](https://github.com/anip-protocol/anip/pull/318)). CI definitions are in
`.github/workflows/ci-*.yml`; when this file and a workflow disagree, the
workflow is right and this file needs fixing.

Run from a **full checkout**. Some tests read shared fixtures from other parts
of the repository and fail in a copy that only has one language's folder
(TypeScript `agent-consumption.test.ts`, Java `AgentConsumptionTest`).
**Status:** verified.

## What CI does and does not run

- Each language job runs only when that language's files change. A skipped job
  still reports success. **Status:** verified.
- Every language also runs weekly and on demand:
  `gh workflow run ci-python.yml --ref main` (likewise `ci-typescript`,
  `ci-go`, `ci-java`, `ci-csharp`, `ci-conformance`). **Status:** verified.
- The Studio "assets are stale" check sometimes fails on identical input and
  passes when re-run. Cause unknown. **Status:** observed once.

## Python (CI: 3.11 and 3.12)

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python \
  -e "packages/python/anip-core[dev]" -e "packages/python/anip-crypto[dev]" \
  -e "packages/python/anip-server[dev]" -e "packages/python/anip-service[dev]" \
  -e "packages/python/anip-fastapi[dev]" -e "packages/python/anip-mcp[dev]" \
  -e "packages/python/anip-rest[dev]" -e "packages/python/anip-graphql[dev]" \
  -e packages/python/anip-stdio -e packages/python/anip-grpc pytest-asyncio
.venv/bin/python -m pytest packages/python/anip-service/tests/ -q   # one package at a time
```

**Status:** verified on 3.11 and 3.12.

## TypeScript (CI: Node 20 and 22)

```bash
cd packages/typescript
npm ci && npm run build --workspaces && npm test --workspaces --if-present
```

- Use Node 20, 22 or 24. On Node 26 the SQLite native module does not build and
  the storage tests fail for that reason alone. **Status:** verified.
- To match CI exactly, run the same commands in `node:22-bookworm` or
  `node:20-bookworm` with the checkout mounted. **Status:** verified.

## Go (CI: 1.24 and 1.25; `go.mod` requires 1.25)

```bash
cd packages/go
GOTOOLCHAIN=go1.25.0 go test ./...
```

**Status:** verified.

## Java (CI: 17 and 21)

```bash
cd packages/java
mvn -B verify
```

- `mvn -o` (offline) fails unless the test runner is already in the local
  Maven repository. **Status:** verified.
- To match CI's Java version, run in `maven:3.9-eclipse-temurin-17` or `-21`.
  **Status:** verified.
- Old jars stay in `target/` and all jars carry the same fixed timestamp, so
  pick the example jar by its version in the file name, never by "newest".
  **Status:** verified.

## C# (CI: .NET 10, with Postgres 16)

```bash
cd packages/csharp
dotnet build && dotnet test --no-build
```

- Without `POSTGRES_DSN` the 14 Postgres storage tests are skipped. To run them:

  ```bash
  docker run -d --rm --name anip-ci-pg -e POSTGRES_USER=anip -e POSTGRES_PASSWORD=anip \
    -e POSTGRES_DB=anip_test -p 55432:5432 postgres:16
  POSTGRES_DSN="Host=localhost;Port=55432;Database=anip_test;Username=anip;Password=anip" \
    dotnet test --no-build
  docker stop anip-ci-pg
  ```

  **Status:** verified.
- A `System.MissingMethodException` from `Microsoft.Build` during `dotnet run`
  or `dotnet test` is a stale build server, not a code problem:
  `dotnet build-server shutdown`, then retry. **Status:** observed once.

## Conformance suite

Start an example service, then:

```bash
pip install -e ./conformance
pytest conformance/ --base-url=http://localhost:<port> \
  --bootstrap-bearer=demo-human-key \
  --sample-inputs=conformance/samples/flight-service.json
```

| Example | How to start | Port |
|---|---|---|
| Python | `cd examples/anip && python -m uvicorn app:app --port <port>` | your choice |
| TypeScript | `cd examples/anip-ts && npm ci && npm run build && node dist/main.js` | 4100 |
| Go (net/http) | `cd packages/go && PORT=9200 go run ./examples/flights` | `PORT` |
| Go (gin) | `cd packages/go && PORT=9206 go run ./examples/flights-gin` | `PORT` |
| Java (Spring) | `mvn package -pl anip-example-flights -am -DskipTests`, then `java -jar anip-example-flights/target/anip-example-flights-<version>.jar` | 9201 |
| Java (Quarkus) | `mvn package -pl anip-example-flights-quarkus -am -DskipTests`, then `java -jar anip-example-flights-quarkus/target/quarkus-app/quarkus-run.jar` | 9202 |
| C# | `cd packages/csharp/src/Anip.Example.Flights && dotnet run` | 9203 |

- The Python example also needs `httpx` and `PyJWT[crypto]`
  (`pip install -e "examples/anip[dev]"`). **Status:** verified.
- Go skips one more test than the others (`verify_via`): it omits an empty list
  where the others send `[]`. Both are valid. **Status:** verified.

## Generated-project tests

```bash
cd packages/go
ANIP_GENERATOR_EXECUTABLE_CONFORMANCE=1 ANIP_GENERATOR_EXECUTABLE_CONFORMANCE_SKIP="" \
  go test ./generator -count=1 -v -timeout=20m \
  -run '^TestGeneratorConformance(Generated|BackendOnly)ProjectsExecute$/<target>$'
```

`<target>` is `go`, `python`, `typescript`, `java` or `csharp`. What each one
tests against:

- **go, csharp:** the local source, directly. **Status:** verified.
- **python:** whatever SDK is installed in the `python` on `PATH`. Install the
  local packages there first. **Status:** verified.
- **typescript:** the local packages' built output. First run
  `npm ci --ignore-scripts` in `packages/typescript`, then
  `npx tsc -p <pkg>/tsconfig.json` for `core`, `crypto`, `server`, `service`,
  `hono` and `stdio`. **Status:** verified.
- **java:** the `dev.anip` artifacts in the Maven repository, which by default
  means the *published* ones. To test local Java code, install it into a
  scratch repository and point the test at it:

  ```bash
  (cd ../java && mvn -q -Dmaven.repo.local=/path/to/m2 install -DskipTests)
  MAVEN_ARGS="-Dmaven.repo.local=/path/to/m2" <the go test command above>
  ```

  **Status:** verified.

## Releases

- After a successful release run, NuGet and Maven Central can take up to about
  an hour to list the new version, and single npm packages a few minutes.
  Check before announcing. **Status:** verified over five releases.
- A release that fails partway can be finished by re-running with
  `allow_already_published=true`. **Status:** verified.
