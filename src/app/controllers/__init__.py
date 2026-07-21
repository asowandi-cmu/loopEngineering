"""Controllers package.

Business logic layer that sits between views (routes) and models.
Controllers handle data manipulation and business rules as plain functions.
"""
from .instrument import (
    get_spec,
    list_instruments,
    seed_default_instruments,
    upsert_instrument,
)
from .reconciliation import (
    ReconcileResult,
    RoundTrip,
    aggregate_round_trips,
    ingest_fills,
    reconcile_all,
)
from .sync import (
    credentials_configured,
    get_sync_state,
    import_csv,
    load_credentials,
    record_status,
    save_credentials,
    set_enabled,
    status_counts,
)
from .trade import (
    compute_pnl,
    compute_stats,
    create_trade,
    delete_trade,
    get_trade,
    list_trades,
    update_trade,
)

__all__ = [
    'compute_pnl',
    'compute_stats',
    'create_trade',
    'update_trade',
    'delete_trade',
    'get_trade',
    'list_trades',
    # instruments
    'get_spec',
    'list_instruments',
    'seed_default_instruments',
    'upsert_instrument',
    # reconciliation
    'ReconcileResult',
    'RoundTrip',
    'aggregate_round_trips',
    'ingest_fills',
    'reconcile_all',
    # sync
    'credentials_configured',
    'get_sync_state',
    'import_csv',
    'load_credentials',
    'record_status',
    'save_credentials',
    'set_enabled',
    'status_counts',
]
