"""Unit tests for the P&L math (``controllers/trade.py: compute_pnl``).

``compute_pnl`` is the single source of truth for futures P&L, so these tests
pin the exact convention the whole app depends on: ``ticks`` is per-contract
signed movement, and the contract multiplier applies to dollars only. They cover
the spec's edge cases (long/short sign flip, multi-contract, fees, fractional
ticks, large contract counts, precision) so a regression here surfaces before it
can silently corrupt stored rows or the frontend preview.
"""
from __future__ import annotations

from decimal import Decimal

from app.controllers.trade import compute_pnl


def _pnl(**kwargs: object) -> tuple[Decimal, Decimal, Decimal]:
    base: dict[str, object] = {
        'side': 'long',
        'contracts': 1,
        'entry_price': Decimal('5000'),
        'exit_price': Decimal('5010'),
        'tick_size': Decimal('0.25'),
        'tick_value': Decimal('12.5'),
        'fees': Decimal('0'),
    }
    base.update(kwargs)
    return compute_pnl(**base)  # type: ignore[arg-type]


def test_long_es_multi_contract_with_fees() -> None:
    """The canonical ES long example from the spec."""
    ticks, gross, net = _pnl(contracts=2, fees=Decimal('4.5'))
    assert ticks == Decimal('40.0000')
    assert gross == Decimal('1000.0000')
    assert net == Decimal('995.5000')


def test_short_is_sign_flipped_equivalent() -> None:
    """A short with entry/exit swapped yields the same positive P&L."""
    ticks, gross, net = _pnl(
        side='short',
        entry_price=Decimal('5010'),
        exit_price=Decimal('5000'),
        contracts=2,
        fees=Decimal('4.5'),
    )
    assert ticks == Decimal('40.0000')
    assert gross == Decimal('1000.0000')
    assert net == Decimal('995.5000')


def test_long_losing_trade_is_negative() -> None:
    ticks, gross, net = _pnl(entry_price=Decimal('5010'), exit_price=Decimal('5000'))
    assert ticks == Decimal('-40.0000')
    assert gross == Decimal('-500.0000')
    assert net == Decimal('-500.0000')


def test_short_losing_when_price_rises() -> None:
    ticks, gross, net = _pnl(
        side='short', entry_price=Decimal('18000'), exit_price=Decimal('18010'),
        tick_size=Decimal('0.25'), tick_value=Decimal('5'),
    )
    assert ticks == Decimal('-40.0000')
    assert gross == Decimal('-200.0000')


def test_nq_short_winner() -> None:
    """Spec edge case: NQ short 18000 -> 17990, tick 0.25, $5/tick, 1 contract."""
    ticks, gross, net = _pnl(
        side='short', entry_price=Decimal('18000'), exit_price=Decimal('17990'),
        tick_size=Decimal('0.25'), tick_value=Decimal('5'),
    )
    assert ticks == Decimal('40.0000')
    assert gross == Decimal('200.0000')
    assert net == Decimal('200.0000')


def test_fees_greater_than_gross_gives_negative_net() -> None:
    ticks, gross, net = _pnl(fees=Decimal('600'))
    assert gross == Decimal('500.0000')
    assert net == Decimal('-100.0000')


def test_fractional_ticks_preserve_precision() -> None:
    """CL: tick 0.01, $10/tick; a 0.015 move = 1.5 ticks."""
    ticks, gross, net = _pnl(
        entry_price=Decimal('75.000'), exit_price=Decimal('75.015'),
        tick_size=Decimal('0.01'), tick_value=Decimal('10'),
    )
    assert ticks == Decimal('1.5000')
    assert gross == Decimal('15.0000')


def test_large_contract_count_no_overflow() -> None:
    ticks, gross, net = _pnl(contracts=1000)
    assert ticks == Decimal('40.0000')
    assert gross == Decimal('500000.0000')
    assert net == Decimal('500000.0000')


def test_net_equals_gross_minus_fees_invariant() -> None:
    ticks, gross, net = _pnl(contracts=3, fees=Decimal('7.25'))
    assert net == gross - Decimal('7.25')
