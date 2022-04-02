from datetime import datetime
from sqlalchemy import (
    Column,
    Boolean,
    VARCHAR,
    Integer,
    ForeignKey,
    TEXT,
    TIMESTAMP
)
from sqlalchemy.orm import relationship
# local imports
from viktor.model.base import Base


class TablePerk(Base):
    """perk table"""

    perk_id = Column(Integer, primary_key=True, autoincrement=True)
    level = Column(Integer, nullable=False)
    desc = Column(TEXT)

    def __init__(self, level: int, desc: str):
        self.level = level
        self.desc = desc

    def __repr__(self) -> str:
        return f'<TablePerk(level={self.level}, desc={self.desc[:20]})>'


class TableQuote(Base):
    """quote table

    Args:
        self.is_quotable: if True, can be used to grab a random quote from a user
    """

    quote_id = Column(Integer, primary_key=True, autoincrement=True)
    author_user_key = Column(Integer, ForeignKey('viktor.slack_user.user_id'), nullable=False)
    author = relationship('TableSlackUser', backref='quotes', foreign_keys=[author_user_key])
    channel_key = Column(Integer, ForeignKey('viktor.slack_channel.channel_id'), nullable=False)
    channel = relationship('TableSlackChannel', back_populates='pins', foreign_keys=[channel_key])
    pinner_user_key = Column(Integer, ForeignKey('viktor.slack_user.user_id'), nullable=False)
    pinner = relationship('TableSlackUser', backref='pins', foreign_keys=[pinner_user_key])
    is_quotable = Column(Boolean, default=False, nullable=False)
    text = Column(TEXT, nullable=False)
    link = Column(VARCHAR(255))
    message_timestamp = Column(TIMESTAMP, nullable=False)
    pin_timestamp = Column(TIMESTAMP, nullable=False)

    def __init__(self, text: str, message_timestamp: datetime, pin_timestamp: datetime, is_quotable: bool = False,
                 link: str = None, **kwargs):
        self.text = text
        self.message_timestamp = message_timestamp
        self.pin_timestamp = pin_timestamp
        self.is_quotable = is_quotable
        self.link = link
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __repr__(self) -> str:
        return f'<TableQuote(is_quotable={self.is_quotable}, text={self.text[:10]}, ' \
               f'message_ts={self.message_timestamp}, pin_ts={self.pin_timestamp})>'
