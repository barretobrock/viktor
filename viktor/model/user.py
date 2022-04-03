from sqlalchemy import (
    Boolean,
    Column,
    VARCHAR,
    Integer,
    Float,
    ForeignKey,
    TEXT
)
from sqlalchemy.orm import relationship
# local imports
from viktor.model.base import Base


class TableSlackUser(Base):
    """slack_user table"""

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    slack_user_hash = Column(VARCHAR(50), nullable=False, unique=True)
    slack_bot_hash = Column(VARCHAR(50), nullable=True)
    real_name = Column(VARCHAR(120), nullable=False)
    display_name = Column(VARCHAR(120), nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    status_emoji = Column(VARCHAR(150))
    status_title = Column(VARCHAR(255))
    role_title = Column(TEXT)
    role_desc = Column(TEXT)
    level = Column(Float(32), default=0, nullable=False)
    ltits = Column(Float(5), default=0, nullable=False)
    avatar_link = Column(VARCHAR(255))
    change_logs = relationship('TableSlackUserChangeLog', back_populates='user')

    def __init__(self, slack_user_hash: str, real_name: str, display_name: str, is_admin: bool = False,
                 role_title: str = None, role_desc: str = None, level: float = 0., ltits: float = 0.,
                 avatar_link: str = None, status_emoji: str = None, status_title: str = None,
                 slack_bot_hash: str = None, **kwargs):
        self.slack_user_hash = slack_user_hash
        self.slack_bot_hash = slack_bot_hash
        self.real_name = real_name
        self.display_name = display_name
        self.is_admin = is_admin
        self.role_title = role_title
        self.role_desc = role_desc
        self.level = level
        self.ltits = ltits
        self.avatar_link = avatar_link
        self.status_emoji = status_emoji
        self.status_title = status_title

        for k, v in kwargs.items():
            setattr(self, k, v)

    def __repr__(self) -> str:
        return f'<TableSlackUser(name={self.real_name}, display_name={self.display_name}, level={self.level}, ' \
               f'ltits={self.ltits})>'


class TableSlackUserChangeLog(Base):
    """slack_user_change_log - to store when a user's info changes"""

    user_change_id = Column(Integer, primary_key=True, autoincrement=True)
    user_key = Column(Integer, ForeignKey('viktor.slack_user.user_id'), nullable=False)
    user = relationship('TableSlackUser', back_populates='change_logs', foreign_keys=[user_key])
    real_name = Column(VARCHAR(120))
    display_name = Column(VARCHAR(120))
    status_emoji = Column(VARCHAR(150))
    status_title = Column(VARCHAR(255))
    role_title = Column(TEXT)
    role_desc = Column(TEXT)
    avatar_link = Column(VARCHAR(255))

    def __init__(self, real_name: str = None, display_name: str = None, status_title: str = None,
                 status_emoji: str = None, role_title: str = None,
                 role_desc: str = None, avatar_link: str = None, **kwargs):
        self.real_name = real_name
        self.display_name = display_name
        self.status_emoji = status_emoji
        self.status_title = status_title
        self.role_title = role_title
        self.role_desc = role_desc
        self.avatar_link = avatar_link

        for k, v in kwargs.items():
            setattr(self, k, v)

    def __repr__(self) -> str:
        return f'<TableSlackUserChangeLog(name={self.real_name}, display_name={self.display_name}, ' \
               f'status={self.status_title[:20]})>'
