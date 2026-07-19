"""Trade controller — business logic as plain functions (no decorators).

This module is the single source of truth for the tick-based P&L math and the
only write path to the derived columns. Every create/update recomputes
``ticks``/``gross_pnl``/``net_pnl`` from the raw inputs via ``compute_pnl`` and
persists them, so stored values can never drift from their inputs.

P&L convention (mirrored exactly in ``frontend/src/journal/pnl.ts``):

    direction   = +1 if side == "long" else -1
    ticks_moved = (exit_price - entry_price) / tick_size   # signed by price
    ticks       = ticks_moved * direction                  # signed by P&L, per contract
    gross_pnl   = ticks * tick_value * contracts           # multiplier hits dollars only
    net_pnl     = gross_pnl - fees

``ticks`` is per-contract signed movement ("the trade moved 40 ticks in my
favor"); the contract multiplier applies to dollars, never to ``ticks``. All math
uses ``Decimal`` and is quantized to the column scales on write.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import case, func, select

from ..models import Trade, db
from ..schemas.trade import TradeCreate, TradeUpdate

# Column-scale quantizers (match src/app/models/trade.py Numeric scales).
_TICKS_Q = Decimal('0.0001')
_MONEY_Q = Decimal('0.0001')


def compute_pnl(
    *,
    side: str,
    contracts: int,
    entry_price: Decimal,
    exit_price: Decimal,
    tick_size: Decimal,
    tick_value: Decimal,
    fees: Decimal,
) -> tuple[Decimal, Decimal, Decimal]:
    """Compute ``(ticks, gross_pnl, net_pnl)`` for a trade.

    The single source of truth for futures P&L. ``tick_size`` must be > 0 (the
    schema layer enforces this before we ever get here). Returns Decimals
    quantized to the stored column scales.
    """
    direction = Decimal(1) if side == 'long' else Decimal(-1)
    ticks_moved = (exit_price - entry_price) / tick_size
    ticks = ticks_moved * direction
    gross_pnl = ticks * tick_value * Decimal(contracts)
    net_pnl = gross_pnl - fees
    return (
        ticks.quantize(_TICKS_Q),
        gross_pnl.quantize(_MONEY_Q),
        net_pnl.quantize(_MONEY_Q),
    )


def _dec(value: Any) -> Decimal:
    """Coerce a SQL aggregate result to Decimal without float noise.

    SQLite returns ``float``/``int`` from ``SUM`` over ``Numeric`` columns;
    PostgreSQL returns ``Decimal``. Routing through ``str`` keeps both exact.
    """
    if value is None:
        return Decimal(0)
    return Decimal(str(value))


def _to_naive_utc(value: datetime) -> datetime:
    """Normalize an (aware or naive) datetime to naive UTC for storage."""
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _apply_inputs(trade: Trade, data: TradeCreate | TradeUpdate) -> None:
    """Copy validated inputs onto a trade and (re)compute derived columns."""
    trade.symbol = data.symbol
    trade.product_name = data.product_name
    trade.side = data.side
    trade.contracts = data.contracts
    trade.entry_price = data.entry_price
    trade.exit_price = data.exit_price
    trade.tick_size = data.tick_size
    trade.tick_value = data.tick_value
    trade.entry_at = _to_naive_utc(data.entry_at)
    trade.exit_at = _to_naive_utc(data.exit_at)
    trade.fees = data.fees
    trade.strategy = data.strategy
    trade.notes = data.notes

    ticks, gross_pnl, net_pnl = compute_pnl(
        side=data.side,
        contracts=data.contracts,
        entry_price=data.entry_price,
        exit_price=data.exit_price,
        tick_size=data.tick_size,
        tick_value=data.tick_value,
        fees=data.fees,
    )
    trade.ticks = ticks
    trade.gross_pnl = gross_pnl
    trade.net_pnl = net_pnl


def create_trade(data: TradeCreate) -> Trade:
    """Create and persist a new trade with computed derived columns."""
    trade = Trade()
    _apply_inputs(trade, data)
    db.session.add(trade)
    db.session.commit()
    return trade


def update_trade(trade_id: int, data: TradeUpdate) -> Trade | None:
    """Full-replace an existing trade, recomputing derived columns.

    Returns the updated trade, or ``None`` if no trade has that id.
    """
    trade = get_trade(trade_id)
    if trade is None:
        return None
    _apply_inputs(trade, data)
    db.session.commit()
    return trade


def delete_trade(trade_id: int) -> bool:
    """Delete a trade. Returns ``True`` if a row was removed, else ``False``."""
    trade = get_trade(trade_id)
    if trade is None:
        return False
    db.session.delete(trade)
    db.session.commit()
    return True


def get_trade(trade_id: int) -> Trade | None:
    """Fetch a single trade by id, or ``None`` if missing."""
    return db.session.get(Trade, trade_id)


def list_trades() -> list[Trade]:
    """Return all trades, newest first (by entry time, then id)."""
    stmt = select(Trade).order_by(Trade.entry_at.desc(), Trade.id.desc())
    return list(db.session.execute(stmt).scalars().all())


def compute_stats() -> dict[str, Any]:
    """Aggregate summary statistics across all trades in SQL.

    Returns all-zero stats (never dividing by zero) for an empty journal. A
    scratch trade (``net_pnl == 0``) counts as neither a win nor a loss, but its
    denominator role in ``win_rate`` is the total number of trades.
    """
    net = Trade.net_pnl
    row = db.session.execute(
        select(
            func.count(Trade.id),
            func.coalesce(func.sum(Trade.net_pnl), 0),
            func.coalesce(func.sum(Trade.gross_pnl), 0),
            func.coalesce(func.sum(Trade.fees), 0),
            func.coalesce(func.sum(Trade.ticks), 0),
            func.coalesce(func.sum(case((net > 0, 1), else_=0)), 0),
            func.coalesce(func.sum(case((net < 0, 1), else_=0)), 0),
            func.coalesce(func.sum(case((net == 0, 1), else_=0)), 0),
            func.coalesce(func.sum(case((net > 0, net), else_=0)), 0),
            func.coalesce(func.sum(case((net < 0, net), else_=0)), 0),
        )
    ).one()

    (
        num_trades,
        total_net,
        total_gross,
        total_fees,
        total_ticks,
        wins,
        losses,
        _scratches_via_diff,
        sum_wins,
        sum_losses,
    ) = row

    num_trades = int(num_trades)
    wins = int(wins)
    losses = int(losses)
    scratches = num_trades - wins - losses

    win_rate = (Decimal(wins) / Decimal(num_trades)) if num_trades else Decimal(0)
    average_win = (_dec(sum_wins) / Decimal(wins)) if wins else Decimal(0)
    average_loss = (_dec(sum_losses) / Decimal(losses)) if losses else Decimal(0)

    return {
        'num_trades': num_trades,
        'total_net_pnl': _dec(total_net),
        'total_gross_pnl': _dec(total_gross),
        'total_fees': _dec(total_fees),
        'total_ticks': _dec(total_ticks),
        'wins': wins,
        'losses': losses,
        'scratches': scratches,
        'win_rate': win_rate.quantize(Decimal('0.0001')),
        'average_win': average_win.quantize(_MONEY_Q),
        'average_loss': average_loss.quantize(_MONEY_Q),
    }
