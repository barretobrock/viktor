import enum

from sqlalchemy import (
    TEXT,
    Column,
    Enum,
    Integer,
)

# local imports
from viktor.model.base import Base


class AcronymType(enum.Enum):
    STANDARD = enum.auto()
    FUN = enum.auto()
    WORK = enum.auto()
    URBAN = enum.auto()


class TableAcronym(Base):
    """response table - stores various responses"""

    acronym_id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(Enum(AcronymType), default=AcronymType.STANDARD, nullable=False)
    text = Column(TEXT, nullable=False)

    def __init__(self, acro_type: AcronymType, text: str):
        self.type = acro_type
        self.text = text

    def __repr__(self) -> str:
        return f'<TableAcronym(type={self.type.name}, text={self.text[:10]})>'
