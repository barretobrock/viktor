from unittest import TestCase, main
from unittest.mock import (
    patch,
    MagicMock
)
from viktor.bot_base import Viktor
from tests.common import (
    get_test_logger,
    make_patcher,
    random_string
)


class TestCAHBot(TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.log = get_test_logger()

    def setUp(self) -> None:
        self.mock_eng = MagicMock(name='PSQLClient')
        self.mock_creds = make_patcher(self, 'cah.bot_base.SecretStore')
        self.mock_slack_base = make_patcher(self, 'cah.bot_base.SlackBotBase')
        self.mock_forms = make_patcher(self, 'cah.bot_base.Forms')

        self.viktor = Viktor(eng=self.mock_eng, creds=self.mock_creds, parent_log=self.log)

    def test_init(self):
        # Assert greater than 10 entries
        self.assertGreater(len(self.viktor.commands.keys()), 10)
        self.mock_eng.get_setting.assert_called()
        self.mock_slack_base.assert_called()
        self.mock_forms.assert_called()

    def test_process_incoming_action(self):
        self.viktor.process_picks = MagicMock(name='process_picks')
        self.viktor.choose_card = MagicMock(name='choose_card')
        self.viktor.new_game = MagicMock(name='new_game')
        self.viktor.display_status = MagicMock(name='status')
        self.viktor.current_game = MagicMock(name='current_game')
        user = random_string(12)
        channel = random_string(10)
        action_scenarios = {
            'gameplay randchoose all': {
                'resp': {
                    'action_id': 'game-choose-1',
                    'type': 'multi_static_select',
                    'selected_options': [
                        {
                            'value': 'randchoose-all'
                        },
                    ]
                },
                'check_call': {
                    'call': self.cahbot.choose_card,
                    'args': [user, 'randchoose']
                }
            },
            'gameplay choose 1': {
                'resp': {
                    'action_id': 'game-choose-1',
                    'type': 'multi_static_select',
                    'selected_options': [
                        {
                            'value': 'choose-1'
                        },
                    ]
                },
                'check_call': {
                    'call': self.cahbot.choose_card,
                    'args': [user, 'choose 1']
                }
            },
            'gameplay choose 214': {
                'resp': {
                    'action_id': 'game-choose-1',
                    'type': 'multi_static_select',
                    'selected_options': [{'value': f'choose-{i}'} for i in [2, 1, 4]],
                },
                'check_call': {
                    'call': self.cahbot.choose_card,
                    'args': [user, 'choose 214']
                }
            },
            'gameplay choose button': {
                'resp': {
                    'action_id': 'game-choose-1',
                    'type': 'button',
                    'value': 'choose-1'
                },
                'check_call': {
                    'call': self.cahbot.choose_card,
                    'args': [user, 'choose 1']
                }
            },
            'gameplay pick button': {
                'resp': {
                    'action_id': 'game-pick-5',
                    'type': 'button',
                    'value': 'pick-5'
                },
                'check_call': {
                    'call': self.cahbot.process_picks,
                    'args': [user, 'pick 5']
                }
            },
            'gameplay new game p1': {
                'resp': {
                    'action_id': 'new-game-start',
                },
                'check_calls': [
                    {
                        'call': self.cahbot.st.send_message,
                        'args': []
                    },
                    {
                        'call': self.mock_eng.session_mgr,
                        'args': []
                    },
                    {
                        'call': self.cahbot.forms.build_new_game_form_p1,
                        'args': []
                    }
                ]
            },
            'gameplay new game p2': {
                'resp': {
                    'action_id': 'new-game-deck',
                    'selected_option': {
                        'value': 'deck_testypoo'
                    },
                },
                'check_calls': [
                    {
                        'call': self.cahbot.st.private_channel_message,
                        'args': []
                    },
                    {
                        'call': self.cahbot.forms.build_new_game_form_p2,
                        'args': []
                    }
                ]
            },
            'gameplay new game p3': {
                'resp': {
                    'action_id': 'new-game-users',
                    'selected_users': ['someone', 'someone-else'],
                },
                'check_calls': [
                    {
                        'call': self.cahbot.new_game,
                        'args': []
                    }
                ]
            },
            'status': {
                'resp': {
                    'action_id': 'status',
                },
                'check_calls': [
                    {
                        'call': self.cahbot.display_status,
                        'args': []
                    }
                ]
            },
            'modify-question-form': {
                'resp': {
                    'action_id': 'modify-question-form',
                },
                'check_calls': [
                    {
                        'call': self.cahbot.forms.modify_question_form,
                        'args': []
                    },
                    {
                        'call': self.cahbot.st.private_channel_message,
                        'args': []
                    }
                ]
            },
            'modify-question': {
                'resp': {
                    'action_id': 'modify-question',
                },
                'check_calls': [
                    {
                        'call': self.cahbot.current_game.current_question_card.modify_text,
                        'args': []
                    },
                    {
                        'call': self.cahbot.st.message_test_channel,
                        'args': []
                    }
                ]
            }
        }

        for scen, scen_dict in action_scenarios.items():
            self.log.debug(f'Working on scenario {scen}')
            resp = self.cahbot.process_incoming_action(user=user, channel=channel, action_dict=scen_dict['resp'],
                                                       event_dict={})
            if 'check_call' in scen_dict.keys():
                check_dict = scen_dict['check_call']
                check_dict['call'].assert_called_with(*check_dict['args'])
            elif 'check_calls' in scen_dict.keys():
                check_dict: dict
                for check_dict in scen_dict['check_calls']:
                    if check_dict.get('args') is None or len(check_dict.get('args')) == 0:
                        check_dict['call'].assert_called()
                    else:
                        check_dict['call'].assert_called_with(*check_dict['args'])


if __name__ == '__main__':
    main()