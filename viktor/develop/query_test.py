from easylogger import Log
from slacktools import (
    SecretStore,
    SlackTools
)
from viktor.model import (
    AcronymType,
    Base,
    BotSettingType,
    ResponseCategory,
    ResponseType,
    TableAcronym,
    TableBotSetting,
    TableEmoji,
    TablePerk,
    TableQuote,
    TableResponse,
    TableSlackChannel,
    TableSlackUser,
    TableSlackUserChangeLog,
    TableUwu
)
from viktor.db_eng import ViktorPSQLClient
from viktor.settings import auto_config


class Qtest:
    """For holding all the various ETL processes, delimited by table name or function of data stored"""

    def __init__(self, env: str = 'dev'):
        self.log = Log('vik-etl', log_level_str='DEBUG', log_to_file=True)
        self.log.debug('Optaining credential file...')
        credstore = SecretStore('secretprops-bobdev.kdbx')

        self.log.debug('Opening up the database...')
        db_props = credstore.get_entry(f'davaidb-{env}').custom_properties
        self.psql_client = ViktorPSQLClient(props=db_props, parent_log=self.log)
        self.st = SlackTools(credstore, auto_config.BOT_NICKNAME, self.log)


if __name__ == '__main__':
    from sqlalchemy.sql import (
        func,
        and_
    )
    from viktor.model import (
        TableSlackUser,
        TablePerk
    )

    qtest = Qtest(env='dev')

    with qtest.psql_client.session_mgr() as session:
        pass
