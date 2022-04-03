from sqlalchemy import (
    Column,
    Boolean,
    VARCHAR,
    Integer
)
from sqlalchemy.orm import relationship
# local imports
from viktor.model.base import Base


class TableSlackChannel(Base):
    """slack_channel table"""

    channel_id = Column(Integer, primary_key=True, autoincrement=True)
    slack_channel_hash = Column(VARCHAR(150), nullable=False, unique=True)
    channel_name = Column(VARCHAR(150), nullable=False)
    is_allow_bot_react = Column(Boolean, default=True, nullable=False)
    is_allow_bot_response = Column(Boolean, default=True, nullable=False)
    is_private = Column(Boolean, default=False, nullable=False)
    is_archived = Column(Boolean, default=False, nullable=False)
    pins = relationship('TableQuote', back_populates='channel')

    def __init__(self, slack_channel_hash: str, channel_name: str, is_allow_bot_react: bool = True,
                 is_allow_bot_response: bool = True, is_private: bool = False, is_archived: bool = False):
        self.slack_channel_hash = slack_channel_hash
        self.channel_name = channel_name
        self.is_allow_bot_react = is_allow_bot_react
        self.is_allow_bot_response = is_allow_bot_response
        self.is_private = is_private
        self.is_archived = is_archived

    def __repr__(self) -> str:
        return f'<TableSlackChannel(hash={self.slack_channel_hash}, name={self.channel_name}, ' \
               f'is_private={self.is_private})>'
