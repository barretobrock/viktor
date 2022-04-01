import enum
from sqlalchemy import (
    Column,
    Boolean,
    VARCHAR,
    Integer,
    Enum,
    ForeignKey
)
from sqlalchemy.orm import relationship
# local imports
from viktor.model.base import Base


class BotSettingType(enum.Enum):
    IS_ANNOUNCE_STARTUP = enum.auto()


class TableBotSetting(Base):
    """bot_settings table - for storing global bot settings

    Attributes:
    """

    setting_id = Column(Integer, primary_key=True, autoincrement=True)
    setting_name = Column(Enum(BotSettingType), nullable=False)
    setting_int = Column(Integer, nullable=False)

    def __init__(self, setting_name: BotSettingType, setting_int: int = 1):
        self.setting_name = setting_name
        self.setting_int = setting_int

    def __repr__(self) -> str:
        return f'<TableBotSetting(name={self.setting_name.name}, val={self.setting_int})>'


class ChannelSettingType(enum.Enum):
    IS_ALLOWED_REACTION = enum.auto()
    IS_ALLOWED_RESPONSE = enum.auto()


class TableChannelSetting(Base):
    """channel_settings table - for storing channel-specific settings

    Attributes:
        self.is_allowed_reaction: if True, allows automatic bot reactions
    """

    channel_setting_id = Column(Integer, primary_key=True, autoincrement=True)
    channel_key = Column(Integer, ForeignKey('viktor.slack_channel.channel_id'), nullable=False)
    channel = relationship('TableSlackChannel', back_populates='channel_settings', foreign_keys=[channel_key])
    setting_name = Column(Enum(ChannelSettingType), nullable=False)
    setting_int = Column(Integer, nullable=False)

    def __init__(self, setting_name: BotSettingType, setting_int: int = 1, **kwargs):
        self.setting_name = setting_name
        self.setting_int = setting_int
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __repr__(self) -> str:
        return f'<TableChannelSetting(name={self.setting_name.name}, val={self.setting_int})>'


