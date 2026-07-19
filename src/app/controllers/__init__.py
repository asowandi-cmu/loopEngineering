"""Controllers package.

Business logic layer that sits between views (routes) and models.
Controllers handle data manipulation and business rules as plain functions.
"""
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
]
