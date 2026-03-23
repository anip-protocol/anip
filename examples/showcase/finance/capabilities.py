"""Financial operations capabilities — ANIP capability declarations and handlers."""
from anip_service import Capability, InvocationContext, ANIPError
from anip_core import (
    CapabilityDeclaration, CapabilityInput, CapabilityOutput, CapabilityRequirement,
    Cost, CostCertainty, ObservabilityContract, ResponseMode, SessionInfo,
    SideEffect, SideEffectType,
)
import data


# ---------------------------------------------------------------------------
# 1. query_portfolio — read-only, scope: finance.read
# ---------------------------------------------------------------------------

_PORTFOLIO_DECL = CapabilityDeclaration(
    name="query_portfolio",
    description="Query current portfolio holdings and valuations",
    contract_version="1.0",
    inputs=[],
    output=CapabilityOutput(
        type="portfolio_summary",
        fields=["holdings", "total_value", "currency"],
    ),
    side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
    minimum_scope=["finance.read"],
    cost=Cost(certainty=CostCertainty.FIXED, financial=None, compute={"latency_p50": "100ms", "tokens": 400}),
    session=SessionInfo(),
    observability=ObservabilityContract(
        logged=True, retention="P7D",
        fields_logged=["capability", "parameters", "result_count"],
        audit_accessible_by=["delegation.root_principal"],
    ),
)


def _handle_query_portfolio(ctx: InvocationContext, params: dict) -> dict:
    holdings = data.get_portfolio()
    total_value = sum(h["market_value"] for h in holdings)
    return {
        "holdings": holdings,
        "total_value": round(total_value, 2),
        "currency": "USD",
    }


query_portfolio = Capability(declaration=_PORTFOLIO_DECL, handler=_handle_query_portfolio)


# ---------------------------------------------------------------------------
# 2. get_market_data — read-only, streaming, scope: finance.read
# ---------------------------------------------------------------------------

_MARKET_DECL = CapabilityDeclaration(
    name="get_market_data",
    description="Get real-time market data for a given symbol",
    contract_version="1.0",
    inputs=[
        CapabilityInput(name="symbol", type="string", description="Ticker symbol (e.g. AAPL)"),
    ],
    output=CapabilityOutput(
        type="market_data",
        fields=["symbol", "bid", "ask", "last", "spread", "volume"],
    ),
    side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
    minimum_scope=["finance.read"],
    cost=Cost(certainty=CostCertainty.FIXED, financial=None, compute={"latency_p50": "80ms", "tokens": 300}),
    session=SessionInfo(),
    response_modes=[ResponseMode.UNARY, ResponseMode.STREAMING],
    observability=ObservabilityContract(
        logged=True, retention="P7D",
        fields_logged=["capability", "parameters", "result"],
        audit_accessible_by=["delegation.root_principal"],
    ),
)


def _handle_get_market_data(ctx: InvocationContext, params: dict) -> dict:
    symbol = params.get("symbol")
    if not symbol:
        raise ANIPError("invalid_parameters", "symbol is required")

    md = data.get_market_data(symbol)
    if md is None:
        raise ANIPError("capability_unavailable", f"No market data for symbol {symbol}")
    return md


get_market_data = Capability(declaration=_MARKET_DECL, handler=_handle_get_market_data)


# ---------------------------------------------------------------------------
# 3. execute_trade — irreversible, financial cost, requires: get_market_data
# ---------------------------------------------------------------------------

_TRADE_DECL = CapabilityDeclaration(
    name="execute_trade",
    description="Execute a buy or sell trade for a given symbol",
    contract_version="1.0",
    inputs=[
        CapabilityInput(name="symbol", type="string", description="Ticker symbol to trade"),
        CapabilityInput(name="side", type="string", required=False, default="buy", description="Trade side: buy or sell"),
        CapabilityInput(name="quantity", type="integer", description="Number of shares to trade"),
    ],
    output=CapabilityOutput(
        type="trade_confirmation",
        fields=["trade_id", "symbol", "side", "quantity", "price", "fee", "total_cost"],
    ),
    side_effect=SideEffect(type=SideEffectType.IRREVERSIBLE, rollback_window="none"),
    minimum_scope=["finance.trade"],
    cost=Cost(
        certainty=CostCertainty.ESTIMATED,
        financial={
            "range_min": 10,
            "range_max": 50000,
            "typical": 1800,
            "currency": "USD",
        },
        determined_by="get_market_data",
        compute={"latency_p50": "500ms", "tokens": 800},
    ),
    requires=[
        CapabilityRequirement(
            capability="get_market_data",
            reason="must check current market price before executing trade",
        ),
    ],
    session=SessionInfo(),
    observability=ObservabilityContract(
        logged=True, retention="P365D",
        fields_logged=["capability", "delegation_chain", "parameters", "result", "cost_actual"],
        audit_accessible_by=["delegation.root_principal"],
    ),
)


def _handle_execute_trade(ctx: InvocationContext, params: dict) -> dict:
    symbol = params.get("symbol")
    side = params.get("side", "buy")
    quantity = params.get("quantity")

    if not symbol:
        raise ANIPError("invalid_parameters", "symbol is required")
    if quantity is None or (isinstance(quantity, int) and quantity <= 0):
        raise ANIPError("invalid_parameters", "quantity must be a positive integer")

    try:
        trade = data.execute_trade(
            symbol=symbol,
            side=side,
            quantity=int(quantity),
            trader=ctx.subject,
            on_behalf_of=ctx.root_principal,
        )
    except ValueError as exc:
        raise ANIPError("invalid_parameters", str(exc))

    ctx.set_cost_actual({"financial": {"amount": trade.total_cost, "currency": trade.currency}})

    return {
        "trade_id": trade.trade_id,
        "symbol": trade.symbol,
        "side": trade.side,
        "quantity": trade.quantity,
        "price": trade.price,
        "fee": trade.fee,
        "total_cost": trade.total_cost,
        "currency": trade.currency,
    }


execute_trade = Capability(declaration=_TRADE_DECL, handler=_handle_execute_trade)


# ---------------------------------------------------------------------------
# 4. transfer_funds — transactional, rollback PT1H, financial cost (fixed fee)
# ---------------------------------------------------------------------------

_TRANSFER_DECL = CapabilityDeclaration(
    name="transfer_funds",
    description="Transfer funds between accounts",
    contract_version="1.0",
    inputs=[
        CapabilityInput(name="from_account", type="string", description="Source account name"),
        CapabilityInput(name="to_account", type="string", description="Destination account name"),
        CapabilityInput(name="amount", type="number", description="Amount to transfer in USD"),
    ],
    output=CapabilityOutput(
        type="transfer_confirmation",
        fields=["transfer_id", "from_account", "to_account", "amount", "fee", "status"],
    ),
    side_effect=SideEffect(type=SideEffectType.TRANSACTIONAL, rollback_window="PT1H"),
    minimum_scope=["finance.transfer"],
    cost=Cost(
        certainty=CostCertainty.FIXED,
        financial={
            "range_min": 25,
            "range_max": 25,
            "typical": 25,
            "currency": "USD",
        },
        compute={"latency_p50": "800ms", "tokens": 500},
    ),
    session=SessionInfo(),
    observability=ObservabilityContract(
        logged=True, retention="P365D",
        fields_logged=["capability", "delegation_chain", "parameters", "result", "cost_actual"],
        audit_accessible_by=["delegation.root_principal"],
    ),
)


def _handle_transfer_funds(ctx: InvocationContext, params: dict) -> dict:
    from_account = params.get("from_account")
    to_account = params.get("to_account")
    amount = params.get("amount")

    if not from_account:
        raise ANIPError("invalid_parameters", "from_account is required")
    if not to_account:
        raise ANIPError("invalid_parameters", "to_account is required")
    if amount is None or (isinstance(amount, (int, float)) and amount <= 0):
        raise ANIPError("invalid_parameters", "amount must be a positive number")

    try:
        transfer = data.transfer_funds(
            from_account=from_account,
            to_account=to_account,
            amount=float(amount),
            initiated_by=ctx.subject,
            on_behalf_of=ctx.root_principal,
        )
    except ValueError as exc:
        raise ANIPError("invalid_parameters", str(exc))

    ctx.set_cost_actual({"financial": {"amount": transfer.fee, "currency": transfer.currency}})

    return {
        "transfer_id": transfer.transfer_id,
        "from_account": transfer.from_account,
        "to_account": transfer.to_account,
        "amount": transfer.amount,
        "fee": transfer.fee,
        "status": transfer.status,
        "currency": transfer.currency,
    }


transfer_funds = Capability(declaration=_TRANSFER_DECL, handler=_handle_transfer_funds)


# ---------------------------------------------------------------------------
# 5. generate_report — write, scope: finance.read
# ---------------------------------------------------------------------------

_REPORT_DECL = CapabilityDeclaration(
    name="generate_report",
    description="Generate a financial report (daily summary, holdings, or transactions)",
    contract_version="1.0",
    inputs=[
        CapabilityInput(name="report_type", type="string", description="Type of report: daily_summary, holdings, or transactions"),
    ],
    output=CapabilityOutput(
        type="financial_report",
        fields=["report_type", "generated_at"],
    ),
    side_effect=SideEffect(type=SideEffectType.WRITE, rollback_window="not_applicable"),
    minimum_scope=["finance.read"],
    cost=Cost(certainty=CostCertainty.FIXED, financial=None, compute={"latency_p50": "200ms", "tokens": 600}),
    session=SessionInfo(),
    observability=ObservabilityContract(
        logged=True, retention="P90D",
        fields_logged=["capability", "parameters", "result"],
        audit_accessible_by=["delegation.root_principal"],
    ),
)


def _handle_generate_report(ctx: InvocationContext, params: dict) -> dict:
    report_type = params.get("report_type")
    if not report_type:
        raise ANIPError("invalid_parameters", "report_type is required")

    try:
        report = data.generate_report(report_type)
    except ValueError as exc:
        raise ANIPError("invalid_parameters", str(exc))

    return report


generate_report = Capability(declaration=_REPORT_DECL, handler=_handle_generate_report)
