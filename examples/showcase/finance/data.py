"""Mock financial data and in-memory transaction store for the finance showcase."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Holding:
    """A portfolio holding."""
    symbol: str
    shares: int
    current_price: float
    currency: str = "USD"


@dataclass
class MarketData:
    """Bid/ask market data for a symbol."""
    symbol: str
    bid: float
    ask: float
    last: float
    volume: int
    currency: str = "USD"


@dataclass
class Trade:
    """A completed trade."""
    trade_id: str
    symbol: str
    side: str  # "buy" or "sell"
    quantity: int
    price: float
    fee: float
    total_cost: float
    currency: str
    trader: str
    on_behalf_of: str
    status: str = "filled"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class Transfer:
    """A completed fund transfer."""
    transfer_id: str
    from_account: str
    to_account: str
    amount: float
    fee: float
    currency: str
    initiated_by: str
    on_behalf_of: str
    status: str = "completed"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# Static portfolio and market data
# ---------------------------------------------------------------------------

PORTFOLIO: list[Holding] = [
    Holding("AAPL", 150, 178.50),
    Holding("GOOGL", 80, 141.25),
    Holding("MSFT", 200, 415.60),
    Holding("AMZN", 60, 185.30),
]

_HOLDING_INDEX: dict[str, Holding] = {h.symbol: h for h in PORTFOLIO}

MARKET_DATA: dict[str, MarketData] = {
    "AAPL": MarketData("AAPL", bid=178.40, ask=178.60, last=178.50, volume=52_340_000),
    "GOOGL": MarketData("GOOGL", bid=141.10, ask=141.40, last=141.25, volume=28_150_000),
    "MSFT": MarketData("MSFT", bid=415.40, ask=415.80, last=415.60, volume=18_720_000),
    "AMZN": MarketData("AMZN", bid=185.10, ask=185.50, last=185.30, volume=45_600_000),
}

TRADING_FEE = 9.95  # fixed per-trade commission
TRANSFER_FEE = 25.00  # fixed wire/transfer fee

# In-memory transaction stores
_TRADES: dict[str, Trade] = {}
_TRANSFERS: dict[str, Transfer] = {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_portfolio() -> list[dict]:
    """Return current portfolio holdings."""
    return [
        {
            "symbol": h.symbol,
            "shares": h.shares,
            "current_price": h.current_price,
            "market_value": round(h.shares * h.current_price, 2),
            "currency": h.currency,
        }
        for h in PORTFOLIO
    ]


def get_market_data(symbol: str) -> dict | None:
    """Return bid/ask market data for a symbol."""
    md = MARKET_DATA.get(symbol.upper())
    if md is None:
        return None
    return {
        "symbol": md.symbol,
        "bid": md.bid,
        "ask": md.ask,
        "last": md.last,
        "spread": round(md.ask - md.bid, 2),
        "volume": md.volume,
        "currency": md.currency,
    }


def execute_trade(
    symbol: str,
    side: str,
    quantity: int,
    price: float | None = None,
    trader: str = "",
    on_behalf_of: str = "",
) -> Trade:
    """Execute a trade, returning the filled Trade."""
    symbol = symbol.upper()
    md = MARKET_DATA.get(symbol)
    if md is None:
        raise ValueError(f"Unknown symbol: {symbol}")
    if side not in ("buy", "sell"):
        raise ValueError(f"Invalid side: {side}; must be 'buy' or 'sell'")
    if quantity <= 0:
        raise ValueError("Quantity must be positive")

    exec_price = price if price is not None else (md.ask if side == "buy" else md.bid)
    total = round(exec_price * quantity + TRADING_FEE, 2)

    # Update holdings
    holding = _HOLDING_INDEX.get(symbol)
    if side == "sell":
        if holding is None or holding.shares < quantity:
            raise ValueError(f"Insufficient shares of {symbol} to sell")
        holding.shares -= quantity
    else:
        if holding is not None:
            holding.shares += quantity
        else:
            new_holding = Holding(symbol, quantity, exec_price)
            PORTFOLIO.append(new_holding)
            _HOLDING_INDEX[symbol] = new_holding

    trade = Trade(
        trade_id=f"TR-{uuid.uuid4().hex[:8].upper()}",
        symbol=symbol,
        side=side,
        quantity=quantity,
        price=exec_price,
        fee=TRADING_FEE,
        total_cost=total,
        currency=md.currency,
        trader=trader,
        on_behalf_of=on_behalf_of,
    )
    _TRADES[trade.trade_id] = trade
    return trade


def transfer_funds(
    from_account: str,
    to_account: str,
    amount: float,
    initiated_by: str = "",
    on_behalf_of: str = "",
) -> Transfer:
    """Transfer funds between accounts."""
    if amount <= 0:
        raise ValueError("Amount must be positive")
    if from_account == to_account:
        raise ValueError("Source and destination accounts must differ")

    transfer = Transfer(
        transfer_id=f"TF-{uuid.uuid4().hex[:8].upper()}",
        from_account=from_account,
        to_account=to_account,
        amount=amount,
        fee=TRANSFER_FEE,
        currency="USD",
        initiated_by=initiated_by,
        on_behalf_of=on_behalf_of,
    )
    _TRANSFERS[transfer.transfer_id] = transfer
    return transfer


def generate_report(report_type: str) -> dict:
    """Generate a financial report."""
    if report_type == "daily_summary":
        total_value = sum(h.shares * h.current_price for h in PORTFOLIO)
        return {
            "report_type": "daily_summary",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "portfolio_value": round(total_value, 2),
            "holdings_count": len(PORTFOLIO),
            "trades_today": len(_TRADES),
            "transfers_today": len(_TRANSFERS),
            "currency": "USD",
        }
    elif report_type == "holdings":
        return {
            "report_type": "holdings",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "holdings": get_portfolio(),
        }
    elif report_type == "transactions":
        return {
            "report_type": "transactions",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "trades": [
                {
                    "trade_id": t.trade_id,
                    "symbol": t.symbol,
                    "side": t.side,
                    "quantity": t.quantity,
                    "price": t.price,
                    "fee": t.fee,
                    "total_cost": t.total_cost,
                }
                for t in _TRADES.values()
            ],
            "transfers": [
                {
                    "transfer_id": t.transfer_id,
                    "from_account": t.from_account,
                    "to_account": t.to_account,
                    "amount": t.amount,
                    "fee": t.fee,
                }
                for t in _TRANSFERS.values()
            ],
        }
    else:
        raise ValueError(f"Unknown report type: {report_type}")
