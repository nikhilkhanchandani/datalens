"""Shared SQLAlchemy declarative base.

Every ORM model in `app/models/` inherits from this `Base`. Importing all
model modules before calling `Base.metadata.create_all()` (see
`app/db/session.py`) is what lets SQLAlchemy discover and create every
table in one call.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
