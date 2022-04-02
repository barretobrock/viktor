import enum
from sqlalchemy import (
    Column,
    Enum,
    ForeignKey,
    VARCHAR,
    Integer,
    TEXT
)
# local imports
from viktor.model.base import Base


class ErrorType(enum.Enum):
    INPUT_ERROR = enum.auto()


class TableError(Base):
    """error table"""

    error_id = Column(Integer, primary_key=True, autoincrement=True)
    error_type = Column(Enum(ErrorType), nullable=False)
    error_class = Column(VARCHAR(150), nullable=False)
    error_text = Column(VARCHAR(255), nullable=False)
    error_traceback = Column(TEXT)

    user_key = Column(ForeignKey('viktor.slack_user.user_id'))
    channel_key = Column(ForeignKey('viktor.slack_channel.channel_id'))

    def __init__(self, error_type: ErrorType, error_class: str, error_text: str, error_traceback: str = None,
                 user_key: int = None, channel_key: int = None):
        self.error_type = error_type
        self.error_class = error_class
        self.error_text = error_text
        self.error_traceback = error_traceback
        self.user_key = user_key
        self.channel_key = channel_key

    def __repr__(self) -> str:
        return f'<TableError(type={self.error_type.name} class={self.error_class}, text={self.error_text[:20]})>'
