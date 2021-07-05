from sqlalchemy import Column, VARCHAR, Integer
# local imports
from .base import Base


class TableUwu(Base):
    """emoji table - stores new emoji info"""
    __tablename__ = 'uwu_graphics'

    id = Column(Integer, primary_key=True, autoincrement=True)
    graphic = Column(VARCHAR, nullable=False)
