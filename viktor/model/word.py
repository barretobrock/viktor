import enum

from sqlalchemy import (
    TEXT,
    Column,
    Enum,
    Integer,
)

# local imports
from viktor.model.base import Base


class WordType(enum.Enum):
    NOUN = enum.auto()
    VERB = enum.auto()
    ADVERB = enum.auto()
    ADJECTIVE = enum.auto()


class WordCategory(enum.Enum):
    SVPITCH = enum.auto()


class TableWord(Base):
    """word table - stores various words to be combined ad-lib style"""

    word_id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(Enum(WordType), default=WordType.NOUN, nullable=False)
    category = Column(Enum(WordCategory), nullable=False)
    stage = Column(Integer, default=1, nullable=False)
    text = Column(TEXT, nullable=False)

    def __init__(self, word_type: WordType, category: WordCategory, text: str, stage: int = 1):
        self.type = word_type
        self.category = category
        self.stage = stage
        self.text = text

    def __repr__(self) -> str:
        return f'<TableWord(type={self.type.name}, category={self.category.name}, stage={self.stage},' \
               f' text={self.text[:10]})>'
