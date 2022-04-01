from sqlalchemy import (
    Column,
    VARCHAR,
    Integer,
    Boolean
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
