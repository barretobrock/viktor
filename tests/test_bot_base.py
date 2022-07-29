from unittest import (
    TestCase,
    main,
)
from unittest.mock import MagicMock

from tests.common import (
    get_test_logger,
    make_patcher,
    random_string,
)
from viktor.bot_base import Viktor


class TestViktor(TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.log = get_test_logger()

    def setUp(self) -> None:
        self.mock_eng = MagicMock(name='PSQLClient')
        self.mock_creds = MagicMock(name='bot_cre_entry')
        self.mock_slack_base = make_patcher(self, 'viktor.bot_base.SlackBotBase')
        self.command_builder_control(is_on=self._testMethodName == 'test_init')
        self.viktor = Viktor(eng=self.mock_eng, bot_cred_entry=self.mock_creds, parent_log=self.log)

    def command_builder_control(self, is_on: bool = False):
        """This can get fairly verbose, so we'll turn this off for most test cases"""
        if not is_on:
            # Turn off command loading for most setup processes
            self.mock_build_commands = make_patcher(self, 'viktor.bot_base.build_commands')
        else:
            self.mock_build_commands = None

    def test_init(self):
        # Assert greater than 10 commands
        self.assertGreater(len(self.viktor.commands), 10)
        self.mock_eng.get_bot_setting.assert_called()
        self.mock_slack_base.assert_called()

    def test_process_incoming_action(self):
        self.viktor.update_user_ltips = MagicMock(name='update_user_ltips')
        user = random_string(12)
        channel = random_string(10)
        action_scenarios = {
            'buttongame': {
                'resp': {
                    'action_id': 'buttongame',
                    'value': 'something|3',
                },
                'check_call': {
                    'call': self.viktor.update_user_ltips,
                    'args': [channel, self.viktor.approved_users[0]],
                    'kwargs': dict(target_user=user, ltits=3 - 5000)
                }
            },
        }

        for scen, scen_dict in action_scenarios.items():
            self.log.debug(f'Working on scenario {scen}')
            _ = self.viktor.process_incoming_action(user=user, channel=channel, action_dict=scen_dict['resp'],
                                                    event_dict={})
            if 'check_call' in scen_dict.keys():
                check_dict = scen_dict['check_call']
                check_dict['call'].assert_called_with(*check_dict['args'], **check_dict['kwargs'])
            elif 'check_calls' in scen_dict.keys():
                check_dict: dict
                for check_dict in scen_dict['check_calls']:
                    if check_dict.get('args') is None or len(check_dict.get('args')) == 0:
                        check_dict['call'].assert_called()
                    else:
                        check_dict['call'].assert_called_with(*check_dict['args'])


if __name__ == '__main__':
    main()
