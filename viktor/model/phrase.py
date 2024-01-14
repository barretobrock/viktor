import enum

from sqlalchemy import (
    TEXT,
    Column,
    Enum,
    Integer,
)

# local imports
from viktor.model.base import Base


class PhraseCategory(enum.Enum):
    FOILHAT = enum.auto()
    JACKHANDEY = enum.auto()
    SARCASTIC = enum.auto()
    STAKEHOLDER = enum.auto()


class TablePhrase(Base):
    """word table - stores various words to be combined ad-lib style"""

    phrase_id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(Enum(PhraseCategory), nullable=False)
    text = Column(TEXT, nullable=False)

    def __init__(self, category: PhraseCategory, text: str):
        self.category = category
        self.text = text

    def __repr__(self) -> str:
        return f'<TablePhrase(category={self.category.name}, text={self.text[:10]})>'
