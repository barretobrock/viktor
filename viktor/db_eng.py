import traceback
from typing import (
    Dict,
    Optional,
    Union
)
from contextlib import contextmanager
from sqlalchemy.engine import (
    create_engine,
    URL
)
from sqlalchemy.orm import sessionmaker
from easylogger import Log
from viktor.model import (
    BotSettingType,
    ErrorType,
    TableBotSetting,
    TableError,
    TableSlackChannel,
    TableSlackUser,
)


class ViktorPSQLClient:
    """Creates Postgres connection engine"""

    def __init__(self, props: Dict, parent_log: Log, **kwargs):
        self.log = Log(parent_log, child_name=self.__class__.__name__)
        self.engine = create_engine(URL.create(
            drivername='postgresql+psycopg2',
            username=props.get('usr'),
            password=props.get('pwd'),
            host=props.get('host'),
            port=props.get('port'),
            database=props.get('database')
        ))
        self._dbsession = sessionmaker(bind=self.engine)

    @contextmanager
    def session_mgr(self):
        """This sets up a transactional scope around a series of operations"""
        session = self._dbsession()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

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

    def log_error_to_db(self, e: Exception, error_type: ErrorType, user_key: int = None,
                        channel_key: int = None):
        """Logs error info to the service_error_log table"""
        err = TableError(
            error_type=error_type,
            error_class=e.__class__.__name__,
            error_text=str(e),
            error_traceback=''.join(traceback.format_tb(e.__traceback__)),
            user_key=user_key,
            channel_key=channel_key,
        )
        with self.session_mgr() as session:
            session.add(err)
