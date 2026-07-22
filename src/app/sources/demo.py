"""Demo trade source — a fixed, realistic fill batch for the *test account*.

Phase 2's automated sync normally streams from a live DXtrade socket, but there
is no broker in dev/demo/E2E. This module backs the **"Use test account"** button:
a canned set of normalized fills that, run through the *real* reconciliation
pipeline, populate the journal with a representative spread — a long winner, a
short winner, a loser, and one still-open position — so the whole sync surface
(source badges, live counts, stats header, dedupe on replay) can be exercised end
to end with no credentials and no network.

The fills carry stable ``DEMO-*`` execution ids, so the batch is **idempotent**:
re-running the test account never creates duplicate trades — it reports
``skipped_duplicates`` instead, which is exactly Phase 2's core promise.
"""
from __future__ import annotations

from typing import Any

from .stub import StubTradeSource

#: Fake credentials persisted when the user activates the test account, so the
#: status pill reads *configured* and Connect/Disconnect behave coherently. These
#: are obviously non-secret placeholders — the demo source ignores them entirely.
DEMO_CREDENTIALS: dict[str, str] = {
    'username': 'demo',
    'password': 'demo-test-account',
    'domain': 'demo',
}

#: A representative fill batch (2026-07-20 → 07-22). Three closed round-trips plus
#: one open ES long, spanning ES/NQ/CL so the stats header shows a real win rate.
DEMO_FILLS: list[dict[str, Any]] = [
    # ES long winner: buy 2 @ 5000 → sell 2 @ 5010 (+40 ticks × $12.50 − fees).
    {
        'external_exec_id': 'DEMO-ES-1', 'external_order_id': 'DEMO-O1',
        'account': 'DEMO', 'symbol': 'ES', 'action': 'buy', 'quantity': 2,
        'price': '5000.00', 'fee': '2.25', 'executed_at': '2026-07-20T13:30:00Z',
    },
    {
        'external_exec_id': 'DEMO-ES-2', 'external_order_id': 'DEMO-O2',
        'account': 'DEMO', 'symbol': 'ES', 'action': 'sell', 'quantity': 2,
        'price': '5010.00', 'fee': '2.25', 'executed_at': '2026-07-20T14:05:00Z',
    },
    # NQ long loser: buy 1 @ 18000 → sell 1 @ 17950 (−200 ticks × $5.00 − fees).
    {
        'external_exec_id': 'DEMO-NQ-1', 'external_order_id': 'DEMO-O3',
        'account': 'DEMO', 'symbol': 'NQ', 'action': 'buy', 'quantity': 1,
        'price': '18000.00', 'fee': '2.10', 'executed_at': '2026-07-21T09:45:00Z',
    },
    {
        'external_exec_id': 'DEMO-NQ-2', 'external_order_id': 'DEMO-O4',
        'account': 'DEMO', 'symbol': 'NQ', 'action': 'sell', 'quantity': 1,
        'price': '17950.00', 'fee': '2.10', 'executed_at': '2026-07-21T10:30:00Z',
    },
    # CL short winner: sell 1 @ 78.50 → buy 1 @ 78.20 (+30 ticks − fees).
    {
        'external_exec_id': 'DEMO-CL-1', 'external_order_id': 'DEMO-O5',
        'account': 'DEMO', 'symbol': 'CL', 'action': 'sell', 'quantity': 1,
        'price': '78.50', 'fee': '1.50', 'executed_at': '2026-07-21T11:00:00Z',
    },
    {
        'external_exec_id': 'DEMO-CL-2', 'external_order_id': 'DEMO-O6',
        'account': 'DEMO', 'symbol': 'CL', 'action': 'buy', 'quantity': 1,
        'price': '78.20', 'fee': '1.50', 'executed_at': '2026-07-21T11:40:00Z',
    },
    # ES long still open (no matching close) → counted as an open position.
    {
        'external_exec_id': 'DEMO-ES-3', 'external_order_id': 'DEMO-O7',
        'account': 'DEMO', 'symbol': 'ES', 'action': 'buy', 'quantity': 1,
        'price': '5008.00', 'fee': '2.25', 'executed_at': '2026-07-22T10:00:00Z',
    },
]


def demo_source() -> StubTradeSource:
    """Build the canned demo source (a ``StubTradeSource`` over ``DEMO_FILLS``)."""
    return StubTradeSource.from_dicts(DEMO_FILLS)
