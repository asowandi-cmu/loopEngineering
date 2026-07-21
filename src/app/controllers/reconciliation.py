"""Reconciliation pipeline — broker fills → closed round-trip ``trades`` rows.

This is the heart of Phase 2. It has two layers:

- ``aggregate_round_trips(fills)`` — a **pure** function (no DB, no I/O) that walks
  per-``(account, symbol)`` fills, tracks signed position, and emits one
  ``RoundTrip`` each time position returns to exactly flat. Entry legs (position-
  increasing) give a contracts-weighted average entry price; exit legs a weighted
  average exit. Because a closed round-trip has equal total entry and exit
  quantity ``Q``, the weighted-average method is **exact** for realized P&L, so
  feeding ``(avg_entry, avg_exit, Q)`` into Phase 1's ``compute_pnl`` reproduces
  true realized dollars. Partial fills and scale-in/out fall out naturally; a fill
  that **crosses zero** is split — the portion to 0 closes the current round-trip,
  the remainder opens the next — and its exec id is recorded on both.

- ``ingest_fills(fills, source)`` / ``reconcile_all()`` — the impure orchestrators.
  They persist each raw fill once (idempotent by ``external_exec_id``), re-derive
  round-trips over **all** stored fills for the affected groups (so a late closing
  fill completes an earlier-opened round-trip), and upsert ``trades`` keyed by a
  deterministic ``external_id``. Re-running is therefore a no-op: existing rows are
  skipped or updated in place, never duplicated. Imports that look like a
  pre-existing manual trade are flagged (``needs_review`` + ``duplicate_of``),
  never merged or deleted.

``compute_pnl`` is reused verbatim (the P&L single source of truth). ``create_trade``
is *not* reused: imported rows set ``source``/``external_id``/``review_status`` and
support the unknown-tick-spec path (tick_size=0, P&L pending) that ``TradeCreate``
validation forbids — so the ``Trade`` row is built directly here while the P&L math
stays in ``compute_pnl``.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from ..models import BrokerFill, Trade, db
from . import instrument as instrument_controller
from .trade import _to_naive_utc, compute_pnl

# Column-scale quantizers (match models/trade.py + broker_fill.py Numeric scales).
_PRICE_Q = Decimal('0.000001')
_MONEY_Q = Decimal('0.0001')

# How close (in time) an imported round-trip must be to a manual trade — with
# identical symbol/side/contracts/prices — to be flagged as a likely duplicate.
_OVERLAP_TOLERANCE = timedelta(seconds=90)


@dataclass
class RoundTrip:
    """One fully-closed round-trip aggregated from constituent fills."""

    account: str | None
    symbol: str
    side: str  # 'long' | 'short'
    contracts: int
    entry_price: Decimal
    exit_price: Decimal
    entry_at: datetime
    exit_at: datetime
    fees: Decimal
    exec_ids: list[str]

    @property
    def external_id(self) -> str:
        """Deterministic id from the sorted constituent exec ids (stable dedupe)."""
        joined = ','.join(sorted(set(self.exec_ids)))
        digest = hashlib.sha1(joined.encode('utf-8')).hexdigest()[:24]
        return f'dxt:{digest}'


@dataclass
class ReconcileResult:
    """Counts returned by an ingest/reconcile run (all default to 0)."""

    created: int = 0
    updated: int = 0
    skipped_duplicates: int = 0
    flagged: int = 0
    open_positions: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            'created': self.created,
            'updated': self.updated,
            'skipped_duplicates': self.skipped_duplicates,
            'flagged': self.flagged,
            'open_positions': self.open_positions,
        }


@dataclass
class _Leg:
    """Accumulator for the entry *or* exit side of the current round-trip."""

    qty: int = 0
    notional: Decimal = Decimal('0')

    def add(self, qty: int, price: Decimal) -> None:
        self.qty += qty
        self.notional += price * Decimal(qty)

    def avg(self) -> Decimal:
        return (self.notional / Decimal(self.qty)) if self.qty else Decimal('0')


@dataclass
class _OpenRT:
    """The in-progress round-trip being built while walking a group's fills."""

    open_dir: int = 0  # +1 long, -1 short
    entry: _Leg = field(default_factory=_Leg)
    exit: _Leg = field(default_factory=_Leg)
    fees: Decimal = Decimal('0')
    entry_at: datetime | None = None
    exit_at: datetime | None = None
    exec_ids: list[str] = field(default_factory=list)

    def note_exec(self, exec_id: str) -> None:
        if exec_id not in self.exec_ids:
            self.exec_ids.append(exec_id)


# --- Pure aggregation ---------------------------------------------------------


def _group_key(fill: object) -> tuple[str | None, str]:
    return (getattr(fill, 'account', None), instrument_controller.normalize_symbol(
        getattr(fill, 'symbol')))


def aggregate_round_trips(fills: list[Any]) -> list[RoundTrip]:
    """Pure: aggregate normalized fills into closed round-trips.

    ``fills`` may be ``Fill`` dataclasses or ``BrokerFill`` rows — anything with
    ``external_exec_id``/``symbol``/``action``/``quantity``/``price``/
    ``executed_at``/``fee``/``account``. Open (non-flat) positions emit nothing.
    """
    groups: dict[tuple[str | None, str], list[Any]] = {}
    for fill in fills:
        groups.setdefault(_group_key(fill), []).append(fill)

    round_trips: list[RoundTrip] = []
    for (account, symbol), group in groups.items():
        group.sort(key=lambda f: (f.executed_at, f.external_exec_id))
        round_trips.extend(_walk_group(account, symbol, group))
    return round_trips


def _walk_group(account: str | None, symbol: str, group: list[Any]) -> list[RoundTrip]:
    round_trips: list[RoundTrip] = []
    position = 0
    rt = _OpenRT()

    def emit() -> None:
        nonlocal rt
        assert rt.entry_at is not None and rt.exit_at is not None
        round_trips.append(RoundTrip(
            account=account,
            symbol=symbol,
            side='long' if rt.open_dir > 0 else 'short',
            contracts=rt.entry.qty,
            entry_price=rt.entry.avg(),
            exit_price=rt.exit.avg(),
            entry_at=rt.entry_at,
            exit_at=rt.exit_at,
            fees=rt.fees,
            exec_ids=list(rt.exec_ids),
        ))
        rt = _OpenRT()

    for fill in group:
        signed = 1 if fill.action == 'buy' else -1
        remaining = int(fill.quantity)
        fill_fee = Decimal(str(fill.fee)) if fill.fee is not None else Decimal('0')
        price = Decimal(str(fill.price))

        while remaining > 0:
            if position == 0 or (position > 0) == (signed > 0):
                # Opening (from flat) or scaling into the same direction → entry.
                if position == 0 and rt.open_dir == 0:
                    rt.open_dir = signed
                take = remaining
                rt.entry.add(take, price)
                if rt.entry_at is None:
                    rt.entry_at = fill.executed_at
                rt.fees += fill_fee * Decimal(take) / Decimal(fill.quantity)
                rt.note_exec(fill.external_exec_id)
                position += signed * take
                remaining = 0
            else:
                # Opposite direction → exit, possibly crossing zero.
                take = min(remaining, abs(position))
                rt.exit.add(take, price)
                rt.exit_at = fill.executed_at
                rt.fees += fill_fee * Decimal(take) / Decimal(fill.quantity)
                rt.note_exec(fill.external_exec_id)
                position += signed * take
                remaining -= take
                if position == 0:
                    emit()  # round-trip closed; remainder (if any) opens next

    return round_trips


def net_position(fills: list[Any]) -> int:
    """Signed net contracts across a set of fills (0 == flat)."""
    return sum((1 if f.action == 'buy' else -1) * int(f.quantity) for f in fills)


# --- Impure orchestration -----------------------------------------------------


def _upsert_broker_fill(fill: Any, source: str) -> BrokerFill:
    """Persist a fill once by ``external_exec_id`` (existing → returned as-is)."""
    existing = db.session.execute(
        select(BrokerFill).where(
            BrokerFill.external_exec_id == fill.external_exec_id
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    bf = BrokerFill(
        external_exec_id=fill.external_exec_id,
        external_order_id=fill.external_order_id,
        account=fill.account,
        symbol=instrument_controller.normalize_symbol(fill.symbol),
        action=fill.action,
        quantity=int(fill.quantity),
        price=Decimal(str(fill.price)),
        fee=Decimal(str(fill.fee)) if fill.fee is not None else Decimal('0'),
        executed_at=_to_naive_utc(fill.executed_at),
        source=source,
        raw=fill.raw,
        processed=False,
    )
    db.session.add(bf)
    return bf


def _stored_fills_for(account: str | None, symbol: str) -> list[BrokerFill]:
    stmt = (
        select(BrokerFill)
        .where(BrokerFill.account.is_(account) if account is None
               else BrokerFill.account == account)
        .where(BrokerFill.symbol == symbol)
        .order_by(BrokerFill.executed_at.asc(), BrokerFill.external_exec_id.asc())
    )
    return list(db.session.execute(stmt).scalars().all())


def _find_manual_overlap(rt: RoundTrip, entry_price: Decimal,
                         exit_price: Decimal) -> Trade | None:
    """Return a manual trade this round-trip likely duplicates, else ``None``."""
    candidates = db.session.execute(
        select(Trade).where(
            Trade.source == 'manual',
            Trade.symbol == rt.symbol,
            Trade.side == rt.side,
            Trade.contracts == rt.contracts,
        )
    ).scalars().all()
    for cand in candidates:
        if (Decimal(str(cand.entry_price)).quantize(_PRICE_Q) == entry_price
                and Decimal(str(cand.exit_price)).quantize(_PRICE_Q) == exit_price
                and abs(cand.entry_at - rt.entry_at) <= _OVERLAP_TOLERANCE
                and abs(cand.exit_at - rt.exit_at) <= _OVERLAP_TOLERANCE):
            return cand
    return None


def _persist_round_trip(rt: RoundTrip, bf_by_exec: dict[str, BrokerFill],
                        result: ReconcileResult) -> None:
    entry_price = rt.entry_price.quantize(_PRICE_Q)
    exit_price = rt.exit_price.quantize(_PRICE_Q)
    fees = rt.fees.quantize(_MONEY_Q)
    entry_at = _to_naive_utc(rt.entry_at)
    exit_at = _to_naive_utc(rt.exit_at)

    spec = instrument_controller.get_spec(rt.symbol)
    if spec is None:
        # Unknown tick spec: create the row but leave P&L pending for review.
        tick_size = Decimal('0')
        tick_value = Decimal('0')
        ticks = gross = net = Decimal('0')
        review_status = 'needs_review'
    else:
        tick_size = Decimal(str(spec.tick_size))
        tick_value = Decimal(str(spec.tick_value))
        ticks, gross, net = compute_pnl(
            side=rt.side, contracts=rt.contracts,
            entry_price=entry_price, exit_price=exit_price,
            tick_size=tick_size, tick_value=tick_value, fees=fees,
        )
        review_status = 'ok'

    # Manual-overlap flag (never merge/delete the manual row).
    duplicate_of = None
    overlap = _find_manual_overlap(rt, entry_price, exit_price)
    if overlap is not None:
        duplicate_of = overlap.id
        review_status = 'needs_review'
        result.flagged += 1

    existing = db.session.execute(
        select(Trade).where(Trade.external_id == rt.external_id)
    ).scalar_one_or_none()

    fields = dict(
        symbol=rt.symbol, product_name=(spec.description if spec else None),
        side=rt.side, contracts=rt.contracts,
        entry_price=entry_price, exit_price=exit_price,
        tick_size=tick_size, tick_value=tick_value,
        entry_at=entry_at, exit_at=exit_at, fees=fees,
        ticks=ticks, gross_pnl=gross, net_pnl=net,
        source='dxtrade', review_status=review_status, duplicate_of=duplicate_of,
    )

    if existing is None:
        trade = Trade(external_id=rt.external_id, **fields)
        db.session.add(trade)
        db.session.flush()  # assign id for broker_fill links
        result.created += 1
    else:
        changed = any(
            _norm(getattr(existing, k)) != _norm(v) for k, v in fields.items()
        )
        for k, v in fields.items():
            setattr(existing, k, v)
        trade = existing
        if changed:
            result.updated += 1
        else:
            result.skipped_duplicates += 1

    for exec_id in rt.exec_ids:
        bf = bf_by_exec.get(exec_id)
        if bf is not None:
            bf.processed = True
            bf.trade_id = trade.id


def _norm(value: object) -> object:
    """Normalize a stored/candidate value for change comparison."""
    if isinstance(value, Decimal):
        return value.normalize()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return Decimal(str(value)).normalize()
    return value


def _reconcile_groups(groups: set[tuple[str | None, str]]) -> ReconcileResult:
    result = ReconcileResult()
    for account, symbol in groups:
        stored = _stored_fills_for(account, symbol)
        if not stored:
            continue
        bf_by_exec = {bf.external_exec_id: bf for bf in stored}
        for rt in aggregate_round_trips(stored):
            _persist_round_trip(rt, bf_by_exec, result)
        if net_position(stored) != 0:
            result.open_positions += 1
    db.session.commit()
    return result


def ingest_fills(fills: list[Any], source: str = 'dxtrade') -> ReconcileResult:
    """Persist raw fills idempotently, then reconcile the affected groups."""
    affected: set[tuple[str | None, str]] = set()
    for fill in fills:
        _upsert_broker_fill(fill, source)
        affected.add(
            (fill.account, instrument_controller.normalize_symbol(fill.symbol))
        )
    db.session.flush()
    return _reconcile_groups(affected)


def reconcile_all() -> ReconcileResult:
    """Re-derive every trade from all stored fills (backfill / after a spec fix)."""
    rows = db.session.execute(
        select(BrokerFill.account, BrokerFill.symbol).distinct()
    ).all()
    groups = {(account, symbol) for account, symbol in rows}
    return _reconcile_groups(groups)
