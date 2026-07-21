"""Pydantic v2 schemas for the Trading Journal API.

These validate inbound request bodies (``TradeCreate``/``TradeUpdate``) and shape
outbound responses (``TradeResponse``/``StatsResponse``). Validators enforce every
Phase-1 business rule (positive tick size/value, contracts >= 1, non-negative
prices/fees, ``side`` in {long, short}, exit not before entry, exit fields
required). Client-supplied derived fields (``ticks``/``gross_pnl``/``net_pnl``)
are ignored — the controller is the only writer of those.

Validator messages are deliberately terse ("must be greater than 0") so the view
can surface them in the API's ``fields`` error map.

Response numeric fields are typed as ``float`` so the JSON serializes as plain
numbers (matching the spec's example bodies). The exact ``Decimal`` values remain
the source of truth in the database; floats are display-only here.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import (
    BaseModel,
    ConfigDict,
    field_validator,
    model_validator,
)


class TradeCreate(BaseModel):
    """Validated payload for creating (or fully replacing) a trade."""

    # Ignore unknown/derived fields (ticks, gross_pnl, net_pnl) sent by a client.
    model_config = ConfigDict(extra='ignore')

    symbol: str
    product_name: str | None = None
    side: str
    contracts: int
    entry_price: Decimal
    exit_price: Decimal
    tick_size: Decimal
    tick_value: Decimal
    entry_at: datetime
    exit_at: datetime
    fees: Decimal = Decimal('0')
    strategy: str | None = None
    notes: str | None = None

    @field_validator('symbol')
    @classmethod
    def _validate_symbol(cls, value: str) -> str:
        cleaned = value.strip().upper()
        if not cleaned:
            raise ValueError('must not be empty')
        if len(cleaned) > 16:
            raise ValueError('must be at most 16 characters')
        return cleaned

    @field_validator('product_name', 'strategy', 'notes')
    @classmethod
    def _blank_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator('side')
    @classmethod
    def _validate_side(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in ('long', 'short'):
            raise ValueError("must be 'long' or 'short'")
        return normalized

    @field_validator('contracts')
    @classmethod
    def _validate_contracts(cls, value: int) -> int:
        if value < 1:
            raise ValueError('must be at least 1')
        return value

    @field_validator('entry_price', 'exit_price')
    @classmethod
    def _validate_price(cls, value: Decimal) -> Decimal:
        if value < 0:
            raise ValueError('must be greater than or equal to 0')
        return value

    @field_validator('tick_size', 'tick_value')
    @classmethod
    def _validate_positive(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError('must be greater than 0')
        return value

    @field_validator('fees')
    @classmethod
    def _validate_fees(cls, value: Decimal) -> Decimal:
        if value < 0:
            raise ValueError('must be greater than or equal to 0')
        return value

    @model_validator(mode='after')
    def _validate_exit_after_entry(self) -> 'TradeCreate':
        if self.exit_at < self.entry_at:
            raise ValueError('exit_at must be greater than or equal to entry_at')
        return self


class TradeUpdate(TradeCreate):
    """Full-replace update payload — identical shape/rules to create."""


class TradeResponse(BaseModel):
    """Serialized trade, including the stored/derived P&L columns."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    product_name: str | None
    side: str
    contracts: int
    entry_price: float
    exit_price: float
    tick_size: float
    tick_value: float
    entry_at: datetime
    exit_at: datetime
    fees: float
    ticks: float
    gross_pnl: float
    net_pnl: float
    strategy: str | None
    notes: str | None
    # Phase 2 source/dedupe fields (manual trades: 'manual'/None/'ok'/None).
    source: str
    external_id: str | None
    review_status: str
    duplicate_of: int | None
    created_at: datetime
    updated_at: datetime


class StatsResponse(BaseModel):
    """Aggregate summary statistics across all trades."""

    num_trades: int
    total_net_pnl: float
    total_gross_pnl: float
    total_fees: float
    total_ticks: float
    wins: int
    losses: int
    scratches: int
    win_rate: float
    average_win: float
    average_loss: float
