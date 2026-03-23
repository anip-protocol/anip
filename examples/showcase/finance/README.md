# ANIP Financial Operations Showcase

A governance-focused demonstration of ANIP's protocol features using a financial operations domain. The centerpiece is the **disclosure policy** — showing how the same failure looks different depending on the caller's trust class.

## What This Demonstrates

| ANIP Feature | How It Appears |
|---|---|
| **Disclosure policy** (centerpiece) | Same scope_insufficient failure returns full/reduced/redacted detail based on caller_class (internal vs partner vs default) |
| Retention tiers | Audit entries classified by event_class with tiered retention (long/medium/short/aggregate_only) |
| Checkpoint proofs | Anchored trust level with scheduled checkpoints (may require ~30s for first checkpoint to appear) |
| Multi-hop delegation | Compliance officer -> trader -> execution agent, each narrowing scope |
| Cost signaling | Trade cost estimated via `get_market_data`, confirmed via `cost_actual` |
| Scope enforcement | Read-only token blocked from executing trades, with structured resolution |
| Side-effect typing | read (portfolio, market data), irreversible (trade), transactional (transfer), write (report) |

## Capabilities

- `query_portfolio` — read. Query current portfolio holdings and valuations.
- `get_market_data` — read, streaming. Real-time bid/ask data for a ticker symbol.
- `execute_trade` — irreversible, financial cost. Execute a buy/sell trade. Requires prior `get_market_data`.
- `transfer_funds` — transactional, 1h rollback window, fixed $25 fee. Transfer funds between accounts.
- `generate_report` — write. Generate daily summary, holdings, or transaction reports.

## Running

```bash
# Install dependencies (from repo root)
pip install -r examples/showcase/finance/requirements.txt

# Start the service
cd examples/showcase/finance
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

## API Keys

| Key | Principal |
|---|---|
| `compliance-key` | `human:compliance-officer@example.com` |
| `trader-key` | `human:trader@example.com` |
| `partner-key` | `partner:external-fund@example.com` |

**Note:** Caller class is NOT determined by the API key — it is set explicitly on each token at issuance time via the `caller_class` field. The demo sets `caller_class="internal"` for compliance tokens, `caller_class="partner"` for partner tokens, and omits it (defaults to `"default"` → redacted disclosure) to show all three levels.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `ANIP_STORAGE` | `:memory:` | Storage DSN (`:memory:` or `sqlite:///path.db`) |
| `ANIP_TRUST_LEVEL` | `anchored` | Trust level (`signed` or `anchored`) |
| `ANIP_KEY_PATH` | `./anip-keys` | Key directory |
| `PORT` | `8000` | HTTP port |

## Disclosure Policy

The service is configured with `disclosure_level="policy"` and the following policy:

```python
{
    "internal": "full",       # Full failure detail + resolution guidance
    "partner": "reduced",     # Failure type + limited detail, no resolution
    "default": "redacted",    # Minimal information, type only
}
```

The `caller_class` is set at token issuance time and carried in the JWT. When a capability invocation fails, the service resolves which disclosure level to apply based on the token's caller class.
