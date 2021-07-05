from sqlalchemy import Column, VARCHAR, Integer, ForeignKey, Float, TEXT, TIMESTAMP
# local imports
from .base import Base


class TablePerks(Base):
    """perks table"""
    __tablename__ = 'perks'

    id = Column(Integer, primary_key=True, autoincrement=True)
    level = Column(Integer, nullable=False)
    desc = Column(TEXT)
