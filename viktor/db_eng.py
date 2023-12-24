from typing import (
    Dict,
    List,
    Optional,
    Union,
)

from loguru import logger
from slacktools.db_engine import PSQLClient
from sqlalchemy.sql import (
    and_,
    not_,
)

from viktor.model import (
    BotSettingType,
    ErrorType,
    TableBotSetting,
    TableEmoji,
    TableError,
    TableSlackChannel,
    TableSlackUser,
)


class ViktorPSQLClient(PSQLClient):
    """Creates Postgres connection engine"""

    def __init__(self, props: Dict, parent_log: logger, **kwargs):
        _ = kwargs
        super().__init__(props=props, parent_log=parent_log)

    def get_bot_setting(self, setting: BotSettingType) -> Optional[Union[int, bool]]:
        """Attempts to return a given bot setting"""
        with self.session_mgr() as session:
            result = session.query(TableBotSetting).filter(TableBotSetting.setting_type == setting).one_or_none()
            if result is None:
                return result
            if setting.name.startswith('IS_'):
                # Boolean
                return result.setting_int == 1
            return result.setting_int

    def set_bot_setting(self, setting: BotSettingType, setting_val: Union[int, bool]):
        """Attempts to set a given setting"""
        with self.session_mgr() as session:
            session.query(TableBotSetting).filter(TableBotSetting.setting_type == setting).update(
                {TableBotSetting.setting_int: setting_val}
            )

    def get_reaction_emojis(self) -> List[str]:
        with self.session_mgr() as session:
            emoji_objs = session.query(TableEmoji).filter(and_(
                not_(TableEmoji.is_react_denylisted),
                not_(TableEmoji.is_deleted)
            )).all()
            return [x.name for x in emoji_objs]

    def get_all_users(self) -> Dict[str, TableSlackUser]:
        with self.session_mgr() as session:
            users = session.query(TableSlackUser).all()
            if len(users) > 0:
                expunged_users = {}
                user: TableSlackUser
                for user in users:
                    session.expunge(user)
                    expunged_users[user.slack_user_hash] = user
                return expunged_users

    def set_user_as_admin(self, uid: str):
        with self.session_mgr() as session:
            session.query(TableSlackUser).filter(TableSlackUser.slack_user_hash == uid).update({
                TableSlackUser.is_admin: True
            })

    def get_user_from_hash(self, user_hash: str) -> Optional[TableSlackUser]:
        """Takes in a slack user hash, outputs the expunged object, if any"""
        with self.session_mgr() as session:
            user = session.query(TableSlackUser).filter(TableSlackUser.slack_user_hash == user_hash).one_or_none()
            if user is not None:
                session.expunge(user)
        return user

    def get_channel_from_hash(self, channel_hash: str) -> Optional[TableSlackChannel]:
        """Takes in a slack user hash, outputs the expunged object, if any"""
        with self.session_mgr() as session:
            channel = session.query(TableSlackChannel).\
                filter(TableSlackChannel.slack_channel_hash == channel_hash).one_or_none()
            if channel is not None:
                session.expunge(channel)
        return channel

    def log_viktor_error_to_db(self, e: Exception, error_type: ErrorType, user_key: int = None,
                               channel_key: int = None):
        """Logs error info to the service_error_log table"""
        self.log_error_to_db(e=e, err_tbl=TableError, error_type=error_type, user_key=user_key,
                             channel_key=channel_key)
