import enum
from sqlalchemy import Column, VARCHAR, Integer, Boolean, TIMESTAMP
from sqlalchemy.sql import func
# local imports
from .base import Base


class TableEmojis(Base):
    """emoji table - stores new emoji info"""
    __tablename__ = 'emojis'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(VARCHAR, nullable=False)
    is_denylisted = Column(Boolean, default=False, nullable=False)
    created_date = Column(TIMESTAMP, server_default=func.now())
