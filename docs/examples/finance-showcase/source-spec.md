# Finance Operations Showcase Source Specification

This is the Studio source document for the Finance Operations Showcase example package.
It is intentionally compact: the example is for learning ANIP contracts, registry packages,
and generated code, not for production business completeness.

## Purpose

Finance example focused on read scopes, trade authority, transfer authority, and high-risk financial side effects.

## Service Boundary

- Service ID: `finance-ops-service`
- Service name: Finance Operations Service
- Legacy implementation reference: `examples/showcase/finance`

The generated ANIP substrate should expose the contract and leave domain-specific behavior in
implementation material or backend adapters.

## Capabilities

- `finance.query_portfolio`: Query current holdings and valuations. Scope: `finance.read`. Side effect: `read`.
- `finance.get_market_data`: Get current market data for a ticker symbol. Scope: `finance.read`. Side effect: `read`.
- `finance.execute_trade`: Execute a buy or sell trade after current market data is available. Scope: `finance.trade`. Side effect: `irreversible`.
- `finance.transfer_funds`: Transfer funds between accounts with transactional recovery posture. Scope: `finance.transfer`. Side effect: `transactional`.
- `finance.generate_report`: Generate a daily, holdings, or transaction report. Scope: `finance.read`. Side effect: `write`.

## Review Decisions

- Keep the example single-service unless a tutorial explicitly demonstrates cross-service behavior.
- Treat write, transactional, irreversible, and approval-gated operations as authority-sensitive.
- Require explicit business inputs rather than guessing missing identifiers, account names, service names, quote IDs, or quantities.
- Preserve the old hand-built app as reference implementation material, not as the signed behavior contract.
