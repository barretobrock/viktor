from unittest import (
    TestCase,
    main,
)
from unittest.mock import MagicMock

from tests.common import (
    get_test_logger,
    make_patcher,
)
from viktor.db_eng import ViktorPSQLClient
from viktor.model import BotSettingType


class TestPSQLClient(TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.log = get_test_logger()

    def setUp(self) -> None:
        self.mock_psql_engine = make_patcher(self, 'viktor.db_eng.PSQLClient.__init__')
        self.sessionmaker = make_patcher(self, 'viktor.db_eng.PSQLClient')
        props = {
            'usr': 'someone',
            'pwd': 'password',
            'host': 'hostyhost',
            'database': 'dateybase',
            'port': 5432,
        }
        self.eng = ViktorPSQLClient(props=props, parent_log=self.log)
        self.eng._dbsession = MagicMock(name='session')

    def test_get_setting(self):
        self.eng._dbsession().query().filter().one_or_none.return_value = None
        resp = self.eng.get_bot_setting(BotSettingType.IS_ALLOW_GLOBAL_REACTION)

        self.eng._dbsession().query.assert_called()
        self.eng._dbsession().commit.assert_called()
        self.eng._dbsession().close.assert_called()
        self.assertIsNone(resp)


if __name__ == '__main__':
    main()
