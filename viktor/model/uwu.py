from sqlalchemy import (
    Column,
    TEXT,
    Integer
)
# local imports
from viktor.model.base import Base


class TableUwu(Base):
    """uwu table - stores uwu graphics for /uwu command"""

    uwu_id = Column(Integer, primary_key=True, autoincrement=True)
    graphic = Column(TEXT, nullable=False)

    def __init__(self, graphic_txt: str):
        self.graphic = graphic_txt

    def __repr__(self) -> str:
        return f'<TableUwu(text_len={len(self.graphic)}>'
