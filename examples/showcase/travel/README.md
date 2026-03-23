# ANIP Travel Booking Showcase

A rich demonstration of ANIP's core protocol features using a travel booking domain.

## What This Demonstrates

| ANIP Feature | How It Appears |
|---|---|
| Cost estimation vs actual | Search shows price estimates; booking confirms actual cost |
| Budget enforcement | Agent has a $300 budget; nonstop flights exceed it |
| Scope narrowing | Broad travel token → narrowed search-only and booking-only child tokens |
| Capability prerequisites | `book_flight` requires prior `search_flights` |
| Permission discovery | Agent checks what it can do before acting |
| Delegation chain | Human delegates to agent with bounded authority |
| Audit trail | Full invocation history with event classification |
| Side-effect typing | read (search), irreversible (book), transactional (cancel) |
| Streaming | Search results arrive as progressive SSE events |

## Capabilities

- `search_flights` — read, streaming. Search by origin/destination.
- `check_availability` — read. Check seats and price for a specific flight.
- `book_flight` — irreversible, financial cost. Book a confirmed reservation.
- `cancel_booking` — transactional, 24h rollback window. Cancel within window.

## Running

```bash
# Install dependencies (from repo root)
pip install -r examples/showcase/travel/requirements.txt

# Start the service
cd examples/showcase/travel
python app.py

# In another terminal: run the demo
python demo.py
```

## Endpoints

- **ANIP Protocol:** `http://localhost:8000/.well-known/anip`
- **REST API:** `http://localhost:8000/rest/openapi.json`
- **GraphQL:** `http://localhost:8000/graphql`
- **MCP:** `http://localhost:8000/mcp`
- **Health:** `http://localhost:8000/-/health`

## Configuration

| Variable | Default | Description |
|---|---|---|
| `ANIP_STORAGE` | `:memory:` | Storage DSN (`:memory:` or `sqlite:///path.db`) |
| `ANIP_TRUST_LEVEL` | `signed` | Trust level (`signed` or `anchored`) |
| `ANIP_KEY_PATH` | `./anip-keys` | Key directory |
| `PORT` | `8000` | HTTP port |
