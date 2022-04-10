from typing import (
    Dict,
    Optional,
    Union
)
from loguru import logger
from slacktools.db_engine import PSQLClient
from viktor.model import (
    BotSettingType,
    ErrorType,
    TableBotSetting,
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
            result = session.query(TableBotSetting).filter(TableBotSetting.setting_name == setting).one_or_none()
            if result is None:
                return result
            if setting.name.startswith('IS_'):
                # Boolean
                return result.setting_int == 1
            return result.setting_int

    def set_bot_setting(self, setting: BotSettingType, setting_val: Union[int, bool]):
        """Attempts to set a given setting"""
        with self.session_mgr() as session:
            session.query(TableBotSetting).filter(TableBotSetting.setting_name == setting).update(
                {TableBotSetting.setting_int: setting_val}
            )

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
