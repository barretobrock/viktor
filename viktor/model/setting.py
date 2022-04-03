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
    IS_ANNOUNCE_SHUTDOWN = enum.auto()
    IS_ALLOW_GLOBAL_REACTION = enum.auto()
    IS_POST_ERR_TRACEBACK = enum.auto()


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
