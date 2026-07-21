"""Trade-source adapter layer.

All fill origins (live DXtrade, CSV/statement export, test stub) implement the
same ``TradeSource`` interface and emit a normalized ``Fill``, so a single
reconciliation pipeline serves every path. The live ``DXtradeSource`` is imported
lazily (it pulls in optional ``httpx``/``websockets``) so the pure adapters and
the pipeline import cleanly without those dependencies installed.
"""
from .base import Fill, TradeSource, TradeSourceError
from .csv_statement import CsvStatementSource, parse_fills
from .stub import StubTradeSource, fill_from_dict

__all__ = [
    'Fill',
    'TradeSource',
    'TradeSourceError',
    'StubTradeSource',
    'fill_from_dict',
    'CsvStatementSource',
    'parse_fills',
]
