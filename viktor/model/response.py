import enum
from sqlalchemy import (
    Column,
    Integer,
    TEXT,
    Enum
)
# local imports
from viktor.model.base import Base


class ResponseType(enum.Enum):
    COMPLIMENT = enum.auto()
    FACT = enum.auto()
    INSULT = enum.auto()
    GENERAL = enum.auto()
    PHRASE = enum.auto()
    QUOTE = enum.auto()


class ResponseCategory(enum.Enum):
    FOILHAT = enum.auto()
    JACKHANDEY = enum.auto()
    SARCASTIC = enum.auto()
    STAKEHOLDER = enum.auto()
    STANDARD = enum.auto()
    WORK = enum.auto()


class TableResponse(Base):
    """response table - stores various responses"""

    response_id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(Enum(ResponseType), default=ResponseType.GENERAL, nullable=False)
    category = Column(Enum(ResponseCategory), nullable=False)
    stage = Column(Integer, default=1, nullable=False)
    text = Column(TEXT, nullable=False)

    def __init__(self, response_type: ResponseType, category: ResponseCategory, text: str, stage: int = 1):
        self.type = response_type
        self.category = category
        self.stage = stage
        self.text = text

    def __repr__(self) -> str:
        return f'<TableResponse(type={self.type.name}, category={self.category.name}, stage={self.stage},' \
               f' text={self.text[:10]})>'
