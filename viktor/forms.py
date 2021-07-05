from random import choice
from typing import List, Dict
from sqlalchemy.orm import Session
from slacktools import BlockKitBuilder as bkb, SlackTools


class Forms:
    """Stores various Block Kit forms"""

    @classmethod
    def build_main_menu(cls, slack_api: SlackTools, user: str, channel: str):
        """Generates and sends a main menu"""
        links = [
            'https://picard.ytmnd.com/',
            'https://darthno.ytmnd.com/',
            'https://christmaschebacca.ytmnd.com/',
            'https://leekspin.ytmnd.com/'
        ]
        button_list = [
            bkb.make_action_button('Phrase', value='phrase', action_id='phrase', url=choice(links)),
            bkb.make_action_button('Insult', value='insult', action_id='insult', url=choice(links)),
            bkb.make_action_button('OKR Roles', value='roles', action_id='roles', url=choice(links)),
            bkb.make_action_button('OKR Perks!', value='perks', action_id='perks', url=choice(links))
        ]
        blocks = [
            bkb.make_header('Velkom zu Wiktor Main Menu'),
            bkb.make_action_button_group(button_list)
        ]
        slack_api.private_channel_message(user_id=user, channel=channel,
                                          message='Welcome to the OKR Global Incorporated main menu!',
                                          blocks=blocks)

    @staticmethod
    def build_new_emoji_form_p1() -> List[Dict]:
        """Intakes a link to the new emoji"""

        return [bkb.make_plaintext_input(label='Insert emoji URL here uwu', action_id='new-emoji-p1')]

    @staticmethod
    def build_new_emoji_form_p2(url: str) -> List[Dict]:
        """Builds the second part to the new game form with Block Kit"""
        return [
            bkb.make_image_section_with_text('Here\'s how your emoji will look...', image_url=url,
                                             alt_text='emoji'),
            bkb.make_plaintext_input(label='Type the name of the emoji without ":"', action_id='new-emoji-p2'),
            bkb.make_action_button_group([
                bkb.make_action_button('Cancel!!!', value='cancel', action_id='new-emoji-cancel',
                                       danger_style=True)
            ])
        ]
