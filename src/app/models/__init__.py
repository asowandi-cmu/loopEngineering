"""Database models package.

Exports all models for easy importing throughout the application. Importing the
models here also registers them on the shared metadata so ``db.create_all()``
(used by the test fixtures) and Alembic autogenerate can see every table.
"""
from .base import db
from .trade import Trade

__all__ = ['db', 'Trade']
