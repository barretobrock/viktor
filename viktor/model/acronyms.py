import enum
from sqlalchemy import Column, Integer, TEXT, Enum
# local imports
from .base import Base


class AcronymTypes(enum.Enum):
    standard = 'standard'
    fun = 'fun'
    work = 'work'
    urban = 'urban'


class TableAcronyms(Base):
    """response table - stores various responses"""
    __tablename__ = 'acronyms'

    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(Enum(AcronymTypes), default=AcronymTypes.standard, nullable=False)
    text = Column(TEXT, nullable=False)
