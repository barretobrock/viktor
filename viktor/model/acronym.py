import enum
from sqlalchemy import (
    Column,
    Integer,
    TEXT,
    Enum
)
# local imports
from viktor.model.base import Base


class AcronymType(enum.Enum):
    standard = enum.auto()
    fun = enum.auto()
    work = enum.auto()
    urban = enum.auto()


class TableAcronym(Base):
    """response table - stores various responses"""

    acronym_id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(Enum(AcronymType), default=AcronymType.standard, nullable=False)
    text = Column(TEXT, nullable=False)

    def __init__(self, acro_type: AcronymType, text: str):
        self.type = acro_type
        self.text = text

    def __repr__(self) -> str:
        return f'<TableAcronym(type={self.type.name}, text={self.text[:10]})>'
