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
    is_private = Column(Boolean, nullable=False)
    channel_settings = relationship('TableChannelSetting', back_populates='channel')
    pins = relationship('TableQuote', back_populates='channel')

    def __init__(self, slack_channel_hash: str, channel_name: str, is_private: bool = False):
        self.slack_channel_hash = slack_channel_hash
        self.channel_name = channel_name
        self.is_private = is_private

    def __repr__(self) -> str:
        return f'<TableSlackChannel(hash={self.slack_channel_hash}, name={self.channel_name}, ' \
               f'is_private={self.is_private})>'
