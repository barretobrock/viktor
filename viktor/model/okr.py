from sqlalchemy import Column, VARCHAR, Integer, ForeignKey, Float, TEXT, TIMESTAMP, Boolean, func
# local imports
from .base import Base


class TablePerks(Base):
    """perks table"""
    __tablename__ = 'perks'

    id = Column(Integer, primary_key=True, autoincrement=True)
    level = Column(Integer, nullable=False)
    desc = Column(TEXT)


class TableQuotes(Base):
    """quotes table"""
    __tablename__ = 'quotes'

    id = Column(Integer, primary_key=True, autoincrement=True)
    author = Column(Integer, ForeignKey('users.id'), nullable=False)
    channel = Column(VARCHAR, nullable=False)
    pinner = Column(Integer, ForeignKey('users.id'), nullable=False)
    text = Column(TEXT, nullable=False)
    link = Column(VARCHAR)
    message_date = Column(TIMESTAMP, nullable=False)
    pin_date = Column(TIMESTAMP, nullable=False)
    created_date = Column(TIMESTAMP, server_default=func.now(), nullable=False)
