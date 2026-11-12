# ANIP Implementation Guide

> Where to find a real ANIP service in each language, how one is put together, and why the protocol is designed the way it is.

Read the [README](README.md) first for the big picture, and the [Spec](SPEC.md) when you need the formal contract.

---

## Start by running one

The [quickstart](https://anip.dev/docs/getting-started/quickstart) gives you a running service in about ten minutes: two files and one command, in any of the five languages. Its files live in [`website/snippets/quickstart/`](website/snippets/quickstart/), and CI runs them against the published packages.

## Reference services

Each runtime has a flight-booking example with the same two capabilities, `search_flights` (read) and `book_flight` (irreversible, financial). The conformance suite runs against all of them.

| Language | Where | Start it |
|---|---|---|
| Python | [`examples/anip/`](examples/anip/) | `pip install -e ".[dev]"`, then `uvicorn app:app --port 9100` |
| TypeScript | [`examples/anip-ts/`](examples/anip-ts/) | `npm ci && npm run build && node dist/main.js` |
| Go | [`packages/go/examples/flights/`](packages/go/examples/flights/) | `cd packages/go && PORT=9200 go run ./examples/flights` |
| Java (Spring) | [`packages/java/anip-example-flights/`](packages/java/anip-example-flights/) | `mvn package -pl anip-example-flights -am -DskipTests`, then run the jar |
| Java (Quarkus) | [`packages/java/anip-example-flights-quarkus/`](packages/java/anip-example-flights-quarkus/) | `mvn package -pl anip-example-flights-quarkus -am -DskipTests`, then run `quarkus-run.jar` |
| C# | [`packages/csharp/src/Anip.Example.Flights/`](packages/csharp/src/Anip.Example.Flights/) | `dotnet run` |

Larger examples are in [`examples/showcase/`](examples/showcase/).

## How a service is put together

Every example has the same four parts. The Python one is the shortest to read.

1. **Business logic** that knows nothing about ANIP: [`anip_flight_demo/domain/flights.py`](examples/anip/anip_flight_demo/domain/flights.py).
2. **Capabilities**: a declaration (inputs, output, side effect, minimum scope, cost) and a handler that calls the business logic. See [`capabilities/search_flights.py`](examples/anip/anip_flight_demo/capabilities/search_flights.py) and [`capabilities/book_flight.py`](examples/anip/anip_flight_demo/capabilities/book_flight.py).
3. **The service**: the capabilities, a storage backend, a trust level, and an `authenticate` function that maps your own credentials to a principal. See [`app.py`](examples/anip/app.py).
4. **A mount** on a web framework, which adds the protocol endpoints.

The runtime does the rest. In the Python packages:

| What | Where |
|---|---|
| Models for every protocol type | [`anip-core`](packages/python/anip-core/src/anip_core/models.py) |
| Token issuance, delegation rules, scope and budget narrowing | [`anip-server/delegation.py`](packages/python/anip-server/src/anip_server/delegation.py) |
| Permission discovery | [`anip-server/permissions.py`](packages/python/anip-server/src/anip_server/permissions.py) |
| Discovery, manifest, invocation checks, audit | [`anip-service/service.py`](packages/python/anip-service/src/anip_service/service.py) |
| HTTP routes | [`anip-fastapi/routes.py`](packages/python/anip-fastapi/src/anip_fastapi/routes.py) |

The other four runtimes are laid out the same way under [`packages/`](packages/).

## Check an implementation

The conformance suite is a set of HTTP tests that run against any ANIP service, whatever it is written in:

```bash
pip install -e ./conformance
pytest conformance/ --base-url=http://localhost:9100 \
  --bootstrap-bearer=demo-human-key \
  --sample-inputs=conformance/samples/flight-service.json
```

What it covers, and what it does not yet cover, is listed in the [Spec's status table](SPEC.md#13-roadmap-v01--v1).

---

## Design Decisions Worth Understanding

### Why Not Just Extend OpenAPI?

OpenAPI describes HTTP endpoints for human developers to build client libraries. ANIP describes *capabilities* for AI agents to reason about. The gap isn't syntax — it's semantics. OpenAPI has no concept of delegation chains, side-effect types, cost signaling, or capability prerequisites. You could encode these as OpenAPI extensions, but you'd be fighting the abstraction rather than building on it.

ANIP is complementary to OpenAPI, not competitive. A service can expose both an OpenAPI spec (for human developers) and an ANIP manifest (for agent consumers) over the same underlying functionality.

### Why Trust-on-Declaration?

Because the alternative — requiring cryptographic verification for every declaration — would make ANIP impossible to adopt. No service would implement it if the barrier to entry was "also build a certificate authority." Trust-on-declaration mirrors the web's early approach: `robots.txt` is trust-on-declaration, and it worked well enough to bootstrap an ecosystem. The spec is explicit about this tradeoff and about how far verification has got since ([Spec §7](SPEC.md)).

### Why Separate Tokens Per Capability?

Purpose binding is more restrictive than OAuth2's scope-based model. An OAuth2 token with `travel:write` scope works for any write operation in the travel domain. An ANIP delegation token with `purpose.capability: "book_flight"` works only for booking flights.

The tradeoff is more tokens. The benefit is smaller blast radius — a compromised or misused token can only do what it was issued for, not everything its scope permits. For autonomous agents operating without real-time human oversight, this tradeoff is correct.

### Why `cost_actual` in the Response?

Because declared costs are estimates. The only way to build trust in cost signaling is to let agents compare `cost.estimated` (what the service said it would cost) against `cost_actual` (what it actually cost). Over time, services with consistently accurate estimates build reputation; services with consistently wrong estimates lose it.

---

## Next Steps

- Read the [Spec](SPEC.md) for formal definitions of all primitives
- Read the [agent skills](skills/) for machine-optimized interaction guides
- Check [Open Questions](SPEC.md#14-open-questions) for areas where community input is needed
- See [CONTRIBUTING.md](CONTRIBUTING.md) for how to get involved
