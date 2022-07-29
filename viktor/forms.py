from typing import (
    Dict,
    List,
)

from slacktools import BlockKitBuilder as BKitB
from slacktools import SlackTools


class Forms:
    """Stores various Block Kit forms"""

    @classmethod
    def build_main_menu(cls, slack_api: SlackTools, user: str, channel: str):
        """Generates and sends a main menu"""
        button_list = [
            BKitB.make_action_button('Phrase', value='phrase', action_id='phrase'),
            BKitB.make_action_button('Insult', value='insult', action_id='insult'),
            BKitB.make_action_button('OKR Roles', value='roles', action_id='roles'),
            BKitB.make_action_button('OKR Perks!', value='perks', action_id='perks')
        ]
        blocks = [
            BKitB.make_header('Velkom zu Wiktor Main Menu'),
            BKitB.make_action_button_group(button_list)
        ]
        slack_api.private_channel_message(user_id=user, channel=channel,
                                          message='Welcome to the OKR Global Incorporated main menu!',
                                          blocks=blocks)

    @staticmethod
    def build_new_emoji_form_p1() -> List[Dict]:
        """Intakes a link to the new emoji"""

        return [BKitB.make_plaintext_input(label='Insert emoji URL here uwu', action_id='new-emoji-p1')]

    @staticmethod
    def build_new_emoji_form_p2(url: str, suggested_name: str) -> List[Dict]:
        """Builds the second part to the new game form with Block Kit"""
        return [
            BKitB.make_image_section_with_text('Here\'s how your emoji will look...', image_url=url,
                                               alt_text='emoji'),
            BKitB.make_plaintext_input(label='Type the name of the emoji without ":"',
                                       initial_value=suggested_name, action_id='new-emoji-p2'),
            BKitB.make_action_button_group([
                BKitB.make_action_button('Cancel!!!', value='cancel', action_id='new-emoji-cancel',
                                         danger_style=True)
            ])
        ]

    @staticmethod
    def build_ifact_input_form_p1() -> List[Dict]:
        """Intakes a link to the new emoji"""

        return [BKitB.make_plaintext_input(label='Add fact here!', action_id='new-ifact')]

    @staticmethod
    def build_update_user_level_form():
        return [
            BKitB.make_header('Levelup form!'),
            BKitB.make_context_section([BKitB.markdown_section('_(yes, it really is this easy to levelup!)_')]),
            BKitB.make_user_select('Select user to levelup', action_id='levelup-user')
        ]

    @staticmethod
    def build_update_user_ltits_form_p1():
        return [
            BKitB.make_header('LTITs distribution form, part 1!'),
            BKitB.make_context_section([BKitB.markdown_section('_(yes, it really is this easy to get LTITs!)_')]),
            BKitB.make_user_select('Select user to give LTITs to', action_id='ltits-user-p1')
        ]

    @staticmethod
    def build_update_user_ltits_form_p2(current_ltits: float):
        return [
            BKitB.make_header('LTITs distribution form, part 2!'),
            BKitB.make_context_section([BKitB.markdown_section('_(yes, it really is this easy to get LTITs!)_')]),
            BKitB.make_block_section(f'User\'s current LTITs: *`{current_ltits}`*'),
            BKitB.make_plaintext_input('Select LTIT amount', action_id='ltits-user-p2', initial_value=str(10))
        ]

    @staticmethod
    def build_role_input_form_p1(existing_title: str) -> List[Dict]:
        """Intakes a link to the new emoji"""

        return [
            BKitB.make_header('Form 420-W: Self-professed ReOrg Pending Approval from Viktor, Part 1'),
            BKitB.make_plaintext_input(label='What\'s your desired new title here at OKR?',
                                       action_id='new-role-p1', initial_value=existing_title, multiline=True),
            BKitB.make_action_button_group([
                BKitB.make_action_button('Cancel!!!', value='cancel', action_id='new-emoji-cancel',
                                         danger_style=True)
            ])
        ]

    @staticmethod
    def build_role_input_form_p2(title: str, existing_desc: str) -> List[Dict]:
        """Intakes a link to the new emoji"""

        return [
            BKitB.make_header('Form 420-W: Self-professed ReOrg Pending Approval from Viktor, Part 2'),
            BKitB.make_block_section(':uwupolice:*Your new title*:'),
            BKitB.make_block_section(title),
            BKitB.make_plaintext_input(label='Now, Describe your new title - like, what would you say... '
                                             'you _really_ do here??',
                                       action_id='new-role-p2', initial_value=existing_desc, multiline=True),
            BKitB.make_action_button_group([
                BKitB.make_action_button('Cancel!!!', value='cancel', action_id='new-emoji-cancel',
                                         danger_style=True)
            ])
        ]
