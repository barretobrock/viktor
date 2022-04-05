from datetime import datetime
from sqlalchemy import (
    Column,
    VARCHAR,
    Integer,
    Boolean,
    TIMESTAMP
)
# local imports
from viktor.model.base import Base


class TableEmoji(Base):
    """emoji table - stores new emoji info"""

    emoji_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(VARCHAR(150), nullable=False)
    reaction_count = Column(Integer, default=0)
    is_react_denylisted = Column(Boolean, default=False, nullable=False)

    def __init__(self, name: str, is_react_denylisted: bool = False):
        self.name = name
        self.is_react_denylisted = is_react_denylisted

    def __repr__(self) -> str:
        return f'<TableEmoji(name={self.name}, is_react_denylisted={self.is_react_denylisted})>'


class TablePotentialEmoji(Base):
    """potential_emoji table - stores emojis found by scraping slackmojis"""

    pot_emoji_id = Column(Integer, primary_key=True, autoincrement=True)
    data_emoji_id = Column(Integer, nullable=False)
    name = Column(VARCHAR(150), nullable=False)
    upload_timestamp = Column(TIMESTAMP, nullable=False)
    link = Column(VARCHAR(200), nullable=False)

    def __init__(self, name: str, data_emoji_id: int, upload_timestamp: int, link: str):
        self.name = name
        self.data_emoji_id = data_emoji_id
        self.upload_timestamp = datetime.fromtimestamp(upload_timestamp)
        self.link = link

    def __repr__(self) -> str:
        return f'<TablePotentialEmoji(name={self.name}, uploaded={self.upload_timestamp})>'
