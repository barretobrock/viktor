import traceback
from typing import Dict
from contextlib import contextmanager
from sqlalchemy.engine import create_engine, URL
from sqlalchemy.orm import sessionmaker
from easylogger import Log


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

    # def get_service_setting(self, setting: SettingType) -> Union[int, bool]:
    #     """Extracts all service settings"""
    #     with self.session_mgr() as session:
    #         result = session.\
    #             query(TableServiceSetting).\
    #             filter(TableServiceSetting.setting_name == setting).\
    #             one_or_none()
    #         if setting.name.startswith('IS_'):
    #             return result.setting_int == 1
    #         else:
    #             return result.setting_int

    # def get_setting_non_ipdo_channel_messaging(self) -> bool:
    #     """Pulls in the global IML service setting to determine if any external IPDO messages should be sent"""
    #     return self.get_service_setting(setting=SettingType.IS_NOTIFY_NON_IPDO_CHANNELS)
    #
    # def get_setting_data_check_optimization(self) -> bool:
    #     """Pulls in the global IML service setting to determine if any external IPDO messages should be sent"""
    #     return self.get_service_setting(setting=SettingType.IS_OPTIMIZE_DATA_CHECKS)

    # def log_error_to_db(self, e: Exception, error_type: ErrorType, data_check_key: int = None,
    #                     data_source_key: int = None, subscription_key: int = None):
    #     """Logs error info to the service_error_log table"""
    #     err = TableServiceError(
    #         error_type=error_type,
    #         error_class=e.__class__.__name__,
    #         error_text=str(e),
    #         error_traceback=''.join(traceback.format_tb(e.__traceback__)),
    #         data_check_key=data_check_key,
    #         data_source_key=data_source_key,
    #         subscription_key=subscription_key
    #     )
    #     with self.session_mgr() as session:
    #         session.add(err)
