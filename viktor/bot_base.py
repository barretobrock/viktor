#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import re
import string
import sys
import requests
import tempfile
from pathlib import Path
from datetime import datetime
from types import SimpleNamespace
from typing import (
    Callable,
    List,
    Optional,
    Union,
    Dict
)
from urllib.parse import urlparse
import pandas as pd
import numpy as np
from slack.errors import SlackApiError
from random import (
    randint,
    choice
)
from sqlalchemy.sql import (
    and_,
    func
)
from slacktools import (
    SlackBotBase,
    BlockKitBuilder as BKitB
)
from slacktools.tools import build_commands
from loguru import logger
from viktor import ROOT_PATH
from viktor.core.linguistics import Linguistics
from viktor.core.phrases import (
    PhraseBuilders,
    recursive_uwu
)
from viktor.settings import auto_config
from viktor.model import (
    BotSettingType,
    ResponseType,
    ResponseCategory,
    TableEmoji,
    TablePerk,
    TableResponse,
    TableSlackUser
)
from viktor.db_eng import ViktorPSQLClient
from viktor.forms import Forms


class Viktor(Linguistics, PhraseBuilders, Forms):
    """Handles messaging to and from Slack API"""

    def __init__(self, eng: ViktorPSQLClient, bot_cred_entry: SimpleNamespace,  parent_log: logger):
        """
        Args:

        """
        self.bot_name = f'{auto_config.BOT_FIRST_NAME} {auto_config.BOT_LAST_NAME}'
        self.log = parent_log.bind(child_name=self.__class__.__name__)
        self.eng = eng
        self.bot_creds = bot_cred_entry
        self.triggers = auto_config.TRIGGERS
        self.main_channel = auto_config.TEST_CHANNEL
        self.emoji_channel = auto_config.EMOJI_CHANNEL
        self.general_channel = auto_config.GENERAL_CHANNEL
        self.approved_users = auto_config.ADMINS
        self.version = auto_config.VERSION
        self.update_date = auto_config.UPDATE_DATE

        super().__init__(eng=eng)

        # Begin loading and organizing commands after all methods are accounted for above
        self.commands = build_commands(self, cmd_yaml_path=ROOT_PATH.parent.joinpath('commands.yaml'),
                                       log=self.log)

        # Initate the bot, which comes with common tools for interacting with Slack's API
        self.log.debug('Spinning up SlackBotBase')
        self.st = SlackBotBase(bot_cred_entry=bot_cred_entry, triggers=self.triggers,
                               main_channel=self.main_channel, parent_log=self.log, use_session=True)
        # Pass in commands to SlackBotBase, where task delegation occurs
        self.log.debug('Patching in commands to SBB...')
        self.st.update_commands(commands=self.commands)
        self.bot_id = self.st.bot_id
        self.user_id = self.st.user_id
        self.bot = self.st.bot

        if self.eng.get_bot_setting(BotSettingType.IS_ANNOUNCE_STARTUP):
            self.log.debug('IS_ANNOUNCE_STARTUP was enabled, so sending message to main channel')
            self.st.message_main_channel(blocks=self.get_bootup_msg())

        # Place to temporarily store things. Typical structure is activity -> user -> data
        self.state_store = {
            'reacts': set(),
            'new-emoji': {},
            'new-ltit-req': {}
        }

        self.log.debug(f'{self.bot_name} booted up!')

    def get_bootup_msg(self) -> List[Dict]:
        return [BKitB.make_context_section([
            BKitB.markdown_section(f"*{self.bot_name}* *`{self.version}`* booted up at `{datetime.now():%F %T}`!"),
            BKitB.markdown_section(f"(updated {self.update_date})")
        ])]

    def search_help_block(self, message: str):
        """Takes in a message and filters command descriptions for output
        """
        self.log.debug(f'Got help search command: {message}')
        return self.st.search_help_block(message=message)

    def generate_intro(self) -> List[Dict]:
        """Generates the intro message and feeds it in to the 'help' command"""
        intro = f"Здравствуйте! I'm *{self.bot_name}* (:Q::regional_indicator_v::Q: for short).\n" \
                f"I can help do stuff for you, but you'll need to call my attention first with " \
                f"*`{'`* or *`'.join(self.triggers)}`*\n Example: *`v! hello`*\nHere's what I can do:"
        avi_url = "https://ca.slack-edge.com/TM1A69HCM-ULV018W73-1a94c7650d97-512"
        avi_alt = 'hewwo'
        # Build the help text based on the commands above and insert back into the commands dict
        return self.st.build_help_block(intro, avi_url, avi_alt)

    def refresh_xoxc(self, message: str, match_pattern: str):
        xoxc = re.sub(match_pattern, '', message).strip()
        self.st.refresh_xoxc_token(new_token=xoxc)
        return 'done.'

    def cleanup(self, *args):
        """Runs just before instance is destroyed"""
        _ = args
        notify_block = [
            BKitB.make_context_section([
                BKitB.markdown_section(f'{self.bot_name} died. :death-drops::party-dead::death-drops:')
            ])
        ]
        if self.eng.get_bot_setting(BotSettingType.IS_ANNOUNCE_SHUTDOWN):
            self.st.message_main_channel(blocks=notify_block)
        self.log.info('Bot shutting down...')
        sys.exit(0)

    def process_slash_command(self, event_dict: Dict):
        """Hands off the slash command processing while also refreshing the session"""
        self.st.parse_slash_command(event_dict)

    def process_event(self, event_dict: Dict):
        """Hands off the event data while also refreshing the session"""
        self.st.parse_event(event_data=event_dict)

    def process_incoming_action(self, user: str, channel: str, action_dict: Dict, event_dict: Dict,
                                ) -> Optional:
        """Handles an incoming action (e.g., when a button is clicked)"""
        action_id = action_dict.get('action_id')
        action_value = action_dict.get('value')
        msg = event_dict.get('message', {})
        thread_ts = msg.get('thread_ts')
        self.log.debug(f'Receiving action_id: {action_id} and value: {action_value} from user: {user} in '
                       f'channel: {channel}')

        if 'buttongame' in action_id:
            # Button game stuff
            game_value = action_value.split('|')[1]
            if game_value.isnumeric():
                game_value = int(game_value) - 5000
                resp = self.update_user_ltips(channel, self.approved_users[0], target_user=user, ltits=game_value)
                if resp is not None:
                    self.st.send_message(channel, resp, thread_ts=thread_ts)
        elif action_id == 'new-ifact':
            self.add_ifact(user=user, channel=channel, txt=action_value)
        elif action_id == 'new-role-p1':
            self.new_role_form_p2(user=user, channel=channel, new_title=action_value)
        elif action_id == 'new-role-p2':
            # Update the description part of the role. Title should already be updated in p1
            user_obj = self.eng.get_user_from_hash(user)
            if action_value != user_obj.role_desc:
                with self.eng.session_mgr() as session:
                    session.add(user_obj)
                    user_obj.role_desc = action_value
            self.build_role_txt(channel=channel, user=user)
        elif action_id == 'levelup-user':
            self.update_user_level(channel=channel, requesting_user=user,
                                   target_user=action_dict.get('selected_user'))
        elif action_id == 'ltits-user-p1':
            new_ltit_req: Dict
            new_ltit_req = {user: action_dict.get('selected_user')}
            if 'new-ltit-req' in self.state_store.keys():
                self.state_store['new-ltit-req'].update(new_ltit_req)
            else:
                self.state_store['new-ltit-req'] = new_ltit_req
            tgt_user_obj = self.eng.get_user_from_hash(action_dict.get('selected_user'))
            form_p2 = self.build_update_user_ltits_form_p2(tgt_user_obj.ltits)
            self.st.send_message(channel=channel, message='LTITs form p2', blocks=form_p2, thread_ts=thread_ts)
        elif action_id == 'ltits-user-p2':
            target_user = self.state_store['new-ltit-req'].get(user)
            # Convert the value into a number
            ltits = re.search(r'[-+]?\d+[,\d+.]*', action_value)
            if ltits is None:
                # No number provided.
                self.st.send_message(channel=channel,
                                     message=f'Can\'t find a number from this input: `{action_value}`',
                                     thread_ts=thread_ts)
                return None
            ltits = ltits.group()
            try:
                ltits = float(ltits)
            except ValueError:
                # Number was bad format
                self.st.send_message(channel=channel,
                                     message=f'Parsed number is bad format for float conversion: `{ltits}`',
                                     thread_ts=thread_ts)
                return None
            self.update_user_ltips(channel=channel, requesting_user=user, target_user=target_user, ltits=ltits)
        elif action_id == 'new-emoji-p1':
            # Store this user's first portion of the new emoji request
            new_emoji_req = {user: {'url': action_value}}
            self.state_store['new-emoji'].update(new_emoji_req)
            # Parse out the file name from the url
            emoji_name = os.path.splitext(os.path.split(urlparse(action_value).path)[1])[0]
            # Send the second portion
            self.add_emoji_form_p2(user=user, channel=channel, url=action_value, suggested_name=emoji_name)
        elif action_id == 'new-emoji-p2':
            # Compile all the details together and try to get the emoji uploaded
            url = self.state_store['new-emoji'].get(user).get('url')
            self.add_emoji(user, channel, url=url, new_name=action_value)
        elif action_dict.get('type') == 'message-shortcut':
            # Deal  with message shortcuts
            if action_id == 'uwu':
                # Uwu the message
                self.handle_menu_action_msg_transform_and_send(event_dict=event_dict, funktsioon=self.uwu)
            elif action_id == 'emojiword':
                # Emojiword the message
                self.handle_menu_action_msg_transform_and_send(event_dict=event_dict, funktsioon=self.word_emoji)
            elif action_id == 'mockthis':
                # Mock the message
                self.handle_menu_action_msg_transform_and_send(event_dict=event_dict, funktsioon=self.randcap)
        else:
            # TODO Otherwise treat the action as a phrase?
            pass

    def handle_menu_action_msg_transform_and_send(self, event_dict: Dict, funktsioon: Callable):
        """Stores the process to handle shortcuts through message menu to transform a message with a certain
        algorithm

        Args:
            event_dict: the event dict constructed from a detected slack event
            funktsioon: the function to call that handles the process of transforming the message.

        """
        # Extract event details
        msg = event_dict.get('message')  # type: Dict
        channel = event_dict.get('channel').get('id')
        thread_ts = msg.get('thread_ts')
        blocks = msg.get('blocks')
        msg_text = msg.get('text')

        replaced_blocks = []
        if blocks is not None:
            self.log.debug(f'{len(blocks)} blocks found. Processing action message as blocks.')
            for i, block in enumerate(blocks):
                replaced_blocks.append(recursive_uwu(i, block, replace_func=funktsioon))
            # Attempt to send the message to the channel
            try:
                self.st.send_message(channel=channel, message='A shortcut message', blocks=replaced_blocks,
                                     thread_ts=thread_ts)
            except SlackApiError:
                self.log.error(f'There was an error with attempting to send the message blocks. '
                               f'Likely due to them being malformed: \n{blocks}\n Sending just the text')
                self.st.send_message(channel=channel, message=funktsioon(msg_text), thread_ts=thread_ts)
        else:
            self.log.debug('Blocks weren\'t detected. Sending the plaintext message.')
            self.st.send_message(channel=channel, message=funktsioon(msg_text), thread_ts=thread_ts)

    def prebuild_main_menu(self, user_id: str, channel: str):
        """Encapsulates required objects for building and sending the main menu form"""
        self.build_main_menu(slack_api=self.st, user=user_id, channel=channel)

    # General support methods
    # ====================================================

    def show_gsheets_link(self) -> str:
        return f'https://docs.google.com/spreadsheets/d/{self.bot_creds.spreadsheet_key}/'

    def show_onboring_link(self) -> str:
        return f'https://docs.google.com/document/d/{self.bot_creds.onboarding_key}/edit?usp=sharing'

    def get_channel_stats(self, channel: str) -> str:
        """Collects posting stats for a given channel"""
        msgs = self.st.get_channel_history(channel, limit=1000)
        results = {}

        for msg in msgs:
            try:
                user = msg['user']
            except KeyError:
                user = msg['bot_id']
            txt_len = len(msg['text'])
            if user in results.keys():
                results[user]['msgs'].append(txt_len)
            else:
                # Apply new dict for new user
                results[user] = {'msgs': [txt_len]}

        # Process messages
        for k, v in results.items():
            results[k] = {
                'total_messages': len(v['msgs']),
                'avg_msg_len': sum(v['msgs']) / len(v['msgs'])
            }

        res_df = pd.DataFrame(results).transpose()

        res_df = res_df.reset_index()
        res_df = res_df.rename(columns={'index': 'user'})
        # Get list of users based on the ids we've got
        users = self.st.get_users_info(res_df['user'].tolist(), throw_exception=False)
        user_names = []
        for user in users:
            uid = user['id']
            try:
                name = user['profile']['display_name']
            except KeyError:
                name = user['real_name']

            if name == '':
                name = user['real_name']
            user_names.append({'id': uid, 'display_name': name})

        user_names_df = pd.DataFrame(user_names).drop_duplicates()
        res_df = res_df.merge(user_names_df, left_on='user', right_on='id', how='left')\
            .drop(['user', 'id'], axis=1).fillna('Unknown User')
        res_df = res_df[['display_name', 'total_messages', 'avg_msg_len']]
        res_df['total_messages'] = res_df['total_messages'].astype(int)
        res_df['avg_msg_len'] = res_df['avg_msg_len'].round(1)
        res_df = res_df.sort_values('total_messages', ascending=False)
        response = '*Stats for this channel:*\n Total messages examined: {}\n' \
                   '```{}```'.format(len(msgs), self.st.df_to_slack_table(res_df))
        return response

    def get_emojis_like(self, match_pattern: str, message: str, max_res: int = 500) -> str:
        """Gets emojis matching in the system that match a given regex pattern"""

        # Parse out the initial command via regex
        ptrn = re.sub(match_pattern, '', message).strip()

        if ptrn != '':
            # We've got a pattern to use
            pattern = re.compile(ptrn)
            emojis = self.st.get_emojis()
            matches = [k for k, v in emojis.items() if pattern.match(k)]
            len_match = len(matches)
            if len_match > 0:
                # Slack apparently handles message length limitations on its end, so
                #   let's just put all the emojis together into one string
                response = ''.join([':{}:'.format(x) for x in matches[:max_res]])
            else:
                response = 'No results for pattern `{}` :frowning:'.format(ptrn)

            if len_match >= max_res:
                # Append to the emoji_str that it was truncated
                trunc_resp = '`**Truncated Results ({}) -> ({})**`'.format(len_match, max_res)
                response = '{}\n{}'.format(trunc_resp, response)
        else:
            response = "I couldn't find a pattern from your message. Get your shit together <@{user}>"
        return response

    # Basic / Static standalone methods
    # ====================================================
    def sarcastic_response(self) -> str:
        """Sends back a sarcastic response when user is not allowed to use the action requested"""
        with self.eng.session_mgr() as session:
            resp = session.query(TableResponse.text).filter(and_(
                TableResponse.type == ResponseType.GENERAL,
                TableResponse.category == ResponseCategory.SARCASTIC
            )).order_by(func.random()).limit(1).one().text
            return resp

    @staticmethod
    def giggle() -> str:
        """Laughs, uncontrollably at times"""
        # Count the 'no's
        laugh_cycles = randint(1, 1000)
        response = f'ti{"hi" * laugh_cycles}!'
        return response

    @staticmethod
    def overly_polite(message: str) -> str:
        """Responds to 'no, thank you' with an extra 'no' """
        # Count the 'no's
        no_cnt = message.count('no')
        no_cnt += 1
        response = '{}, thank you!'.format(' '.join(['no'] * no_cnt)).capitalize()
        return response

    @staticmethod
    def shurg(message: str) -> str:
        """Shrugs at the front"""
        return f'¯\\_(ツ)_/¯ {message.replace("shurg", "").strip()}'

    @staticmethod
    def shrugg(message: str) -> str:
        """Shrugs at the back"""
        return f'{message.replace("shrug", "").strip()} ¯\\_(ツ)_/¯'

    @staticmethod
    def randcap(message: str, skip_first_word: bool = False) -> str:
        """Randomly capitalize string"""
        if skip_first_word:
            message = ' '.join(message.split()[1:])
        weights = (str.lower, str.upper)
        return ''.join(choice(weights)(c) for c in message) + ' :spongebob-mock:'

    @staticmethod
    def word_emoji(message: str, match_pattern: str = None) -> str:
        """Randomly capitalize string"""
        if match_pattern is not None:
            msg = re.sub(match_pattern, '', message).strip()
        else:
            msg = message
        # Build out character mapping
        char_dict = {c: f':alphabet-yellow-{c}:' for c in string.ascii_lowercase}
        char_dict.update({
            '!': ':alphabet-yellow-exclamation:',
            '?': ':alphabet-yellow-question:',
            '#': ':alphabet-yellow-hash:',
            '@': ':alphabet-yellow-at:',
            "'": ':air_quotes:',
            '"': ':air_quotes:',
            ' ': ':blank:',
            '1': ':one:',
            '2': ':two:',
            '3': ':three:',
            '4': ':four:',
            '5': ':five:',
            '6': ':six:',
            '7': ':seven:',
            '8': ':eight:',
            '9': ':nine:',
            '0': ':zero:',
        })
        return ''.join(char_dict[c.lower()] if c.lower() in char_dict.keys() else c for c in msg)

    @staticmethod
    def access_something() -> str:
        """Return random number of ah-ah-ah emojis (Jurassic Park movie reference)"""
        return ''.join([':ah-ah-ah:'] * randint(5, 50))

    @staticmethod
    def get_time() -> str:
        """Gets the server time"""
        return f'The server time is `{datetime.today():%F %T}`'

    @staticmethod
    def wfh_epoch() -> List[dict]:
        """Calculates WFH epoch time"""
        wfh_epoch = datetime(year=2020, month=3, day=3, hour=19, minute=15)
        now = datetime.now()
        diff = (now - wfh_epoch)
        wfh_secs = diff.total_seconds()
        day_s = (60 * 60 * 24)

        unit_dict = {
            # NORMAl
            'years': {
                'val': wfh_secs / day_s / 365,
                'type': 'normal'
            },
            'weeks': {
                'val': wfh_secs / (day_s * 7),
                'type': 'normal'
            },
            'days': {
                'val': wfh_secs / day_s,
                'type': 'normal'
            },

            # STRANGE
            'lustrum': {
                # 5 years
                'val': wfh_secs / day_s / 365 / 5,
                'type': 'strange'
            },
            'martian roundtrips': {
                # 9 months to get there, 3 months to wait for better alignment, 9 months to travel back
                'val': wfh_secs / day_s / 30 / 21,
                'type': 'strange'
            },
            'quarantines': {
                # 40 days
                'val': wfh_secs / day_s / 40,
                'type': 'strange'
            },
            'megaseconds': {
                # 1 million seconds
                'val': wfh_secs / 1000000,
                'type': 'strange'
            },
            'mileways': {
                # 20 mins; the period it took in Middle Ages to typically travel a mile
                'val': wfh_secs / (20 * 60),
                'type': 'strange'
            },
        }

        normal_section = []
        strange_section = []
        for k, v in unit_dict.items():
            val = v['val']
            dec = 1 if val > 30 else 2
            base_txt = f',.{dec}f'
            formatted = '`{{:<20}} {{:>15{}}}`'.format(base_txt).format(f'{k.title()}:', val)
            if v.get('type') == 'normal':
                normal_section.append(formatted)
            else:
                strange_section.append(formatted)

        return [
            BKitB.make_context_section([
                BKitB.markdown_section('WFH Epoch')
            ]),
            BKitB.make_block_section(
                f'Current WFH epoch time is *`{wfh_secs:.0f}`*.'
                f'\n ({diff})',
            ),
            BKitB.make_context_section('The time units you\'re used to\n' + '\n'.join(normal_section)),
            BKitB.make_context_section('Some time units that might be strange to you\n' +
                                       '\n'.join(strange_section)),
        ]

    # Misc. methods
    # ====================================================
    def inspirational(self, channel: str):
        """Sends a random inspirational message"""
        resp = requests.get('https://inspirobot.me/api?generate=true')
        if resp.status_code == 200:
            url = resp.text
            # Download img
            img = requests.get(url)
            if img.status_code == 200:
                with open('/tmp/inspirational.jpg', 'wb') as f:
                    f.write(img.content)
                self.st.upload_file(channel, '/tmp/inspirational.jpg', 'inspirational-shit.jpg')

    def button_game(self, message: str):
        """Renders 5 buttons that the user clicks - one button has a value that awards them points"""
        default_limit = 100
        limit = None
        msplit = message.split(' ')
        if len(msplit) > 1:
            # Try to get limit
            str_limit = re.search(r'[-+]?\d+[,\d+.]*', msplit[1])
            if str_limit is not None:
                limit = float(str_limit.group())
        if limit is None:
            limit = default_limit
        upper = int(abs(limit) if limit < 5000 else 5000)
        lower = int(upper * -1)
        btn_blocks = []
        # Determine where to hide the value
        n_buttons = randint(5, 12)
        items = list(range(1, n_buttons + 1))

        with self.eng.session_mgr() as session:
            emojis = [x.name for x in session.query(TableEmoji).order_by(func.random()).limit(n_buttons).all()]
        rand_val = randint(1, n_buttons)
        # Pick two places where negative values should go
        neg_items = list(np.random.choice([x for x in items if x != rand_val], int(n_buttons * .8), False))
        neg_values = []
        win = 0
        for i in items:
            if i == rand_val:
                val = np.random.choice(upper, 1)[0]
                win = val
            elif i in neg_items:
                val = np.random.choice(range(lower, 0), 1)[0]
                neg_values.append(val)
            else:
                val = 0
            btn_blocks.append(BKitB.make_action_button(f':{emojis[i - 1]}:', value=f'bg|{val + 5000}',
                                                       action_id=f'buttongame-{i}'))

        blocks = [
            BKitB.make_block_section(':spinny-rainbow-sheep:'
                                     ':alphabet-yellow-b::alphabet-yellow-u::alphabet-yellow-t:'
                                     ':alphabet-yellow-t::alphabet-yellow-o::alphabet-yellow-n:'
                                     ':blank::alphabet-yellow-g::alphabet-yellow-a::alphabet-yellow-m:'
                                     ':alphabet-yellow-e::alphabet-yellow-exclamation::spinny-rainbow-sheep:'),
            BKitB.make_context_section([
                BKitB.markdown_section('Try your luck and guess which button is hiding the LTITs!! '
                                       f'Only one value has `{win}` LTITs, {len(neg_values)} others have '
                                       f'{",".join([f"`{x}`" for x in neg_values])}. The rest are `0`.')
            ]),
            BKitB.make_action_button_group(btn_blocks)
        ]

        return blocks

    def quote_me(self, message: str, match_pattern: str) -> Optional[str]:
        """Converts message into letter emojis"""
        msg = re.sub(match_pattern, '', message).strip()
        return self.st.build_phrase(msg)

    def add_emoji_form_p1(self, user: str, channel: str, message: str):
        """Builds form to intake emoji and upload"""
        # If the message already contains a url, avoid sending the URL collection form and just process the
        #   info immediately as it would be for part 2
        url = None
        if 'https://' in message:
            url_rgx = re.search(r'https://\S+', message)
            if url_rgx is not None:
                url = url_rgx.group()
        if url is not None:
            # Store this user's first portion of the new emoji request
            new_emoji_req = {user: {'url': url}}
            self.state_store['new-emoji'].update(new_emoji_req)
            # Parse out the file name from the url
            emoji_name = os.path.splitext(os.path.split(urlparse(url).path)[1])[0]
            self.add_emoji_form_p2(user=user, channel=channel, url=url, suggested_name=emoji_name)
        else:
            form1 = self.build_new_emoji_form_p1()
            _ = self.st.private_channel_message(user_id=user, channel=channel, message='New emoji form, p1',
                                                blocks=form1)

    def add_emoji_form_p2(self, user: str, channel: str, url: str, suggested_name: str):
        """Part 2 of emoji intake"""
        # Check name against existing
        with self.eng.session_mgr() as session:
            exists: TableEmoji
            exists = session.query(TableEmoji).filter(TableEmoji.name == suggested_name).one_or_none()
            if exists is not None:
                # Name already exists. Modify it
                suggested_name += f'{exists.emoji_id}'

        form2 = self.build_new_emoji_form_p2(url, suggested_name=suggested_name)
        _ = self.st.private_channel_message(user_id=user, channel=channel, message='New emoji form, p2',
                                            blocks=form2)

    def add_emoji(self, user: str, channel: str, url: str, new_name: str):
        """Attempts to upload new emoji"""
        success = self.st.session.upload_emoji_from_url(url, new_name)
        if success:
            msg = f'Success! Here\'s how your emoji looks: :{new_name}:'
        else:
            msg = 'Something went wrong. Unable to upload the emoji at this time. ' \
                  'Make sure the emoji name you chose is not already in use. ' \
                  f'(Hint: if it is, there will be an emoji here: :{new_name}:'
        self.st.private_channel_message(user_id=user, channel=channel, message=msg)

    def add_ifact_form(self, user: str, channel: str):
        """Builds form to intake new fact"""
        _ = self.st.private_channel_message(user_id=user, channel=channel, message='New ifact form',
                                            blocks=self.build_ifact_input_form_p1())

    def add_ifact(self, user: str, channel: str, txt: str):
        _ = user
        fact = TableResponse(response_type=ResponseType.FACT, category=ResponseCategory.FOILHAT, text=txt)
        with self.eng.session_mgr() as session:
            session.add(fact)
        self.st.send_message(channel=channel, message=f'Fact added! id:`{fact.id}`\n{fact.text}')

    def get_fart(self, user: str, channel: str):
        fart_id = randint(1, 3000)
        resp = requests.get(f'https://boredhumans.b-cdn.net/farts/{fart_id}.mp3')
        fartpath = Path(tempfile.gettempdir()).joinpath('fart.mp3')
        if resp.status_code == 200:
            with fartpath.open(mode='wb') as f:
                f.write(resp.content)
            self.st.upload_file(channel=channel, filepath=fartpath.__str__(), filename='fart.mp3',
                                txt=f'Ok! Here\'s the recording I took of <@{user}> recently!')

    # OKR Methods
    # ------------------------------------------------
    def onboarding_docs(self) -> List[dict]:
        """Returns links to everything needed to bring a new OKR employee up to speed"""
        docs = [
            BKitB.make_block_section([
                "Welcome to OKR! We're glad to have you on board!\nCheck out these links below "
                "to get familiar with OKR and the industry we support!"
            ]),
            BKitB.make_block_section([
                f"\t<{self.show_onboring_link()}|Onboarding Doc>\n\t<{self.show_gsheets_link()}|Viktor's GSheet>\n"
            ]),
            BKitB.make_block_section([
                "For any questions, reach out to the CEO or our Head of Recruiting. "
                "Don't know who they are? Well, figure it out!"
            ])
        ]
        return docs

    def show_all_perks(self) -> List[Dict]:
        """Displays all the perks"""
        with self.eng.session_mgr() as session:
            perks = session.query(TablePerk).all()
            session.expunge_all()
        final_perks = self._build_perks_list(perks)
        return [
            BKitB.make_header('OKR Perks!'),
            BKitB.make_context_section([
                BKitB.markdown_section('you\'ll never see anything better, trust us!')
            ]),
            BKitB.make_block_section([p for p in final_perks])
        ]

    @staticmethod
    def _build_perks_list(perks: List[TablePerk]) -> List[str]:
        """Builds out a formatted list of perks based on a filtered query result from the table"""
        perk_dict = {}
        for perk in perks:
            # Organize perks by level
            level = perk.level
            if level in perk_dict.keys():
                perk_dict[level].append(perk.desc)
            else:
                perk_dict[level] = [perk.desc]
        # Sort by keys, just in case they're not in order
        perk_dict = dict(sorted(perk_dict.items()))
        final_perks = []
        for level, perk_list in perk_dict.items():
            formatted_perk_list = '\n\t\t - '.join(perk_list)
            final_perks.append(f'`lvl {level}`: \n\t\t - {formatted_perk_list}\n')
        return final_perks

    def show_my_perks(self, user: str) -> Union[List[Dict], str]:
        """Lists the perks granted at the user's current level"""
        # Get the user's level
        user_obj = self.eng.get_user_from_hash(user_hash=user)
        if user_obj is None:
            return 'User not found in OKR roles sheet :frowning:'

        level = user_obj.level
        ltits = user_obj.ltits

        # Get perks
        with self.eng.session_mgr() as session:
            perks = session.query(TablePerk).filter(TablePerk.level <= level).all()
            session.expunge_all()
        final_perks = self._build_perks_list(perks)
        return [
            BKitB.make_header(f'Perks for our very highly valued `{user_obj.name}`!'),
            BKitB.make_context_section([
                BKitB.markdown_section('you\'ll _really_ never see anything better, trust us!')
            ]),
            BKitB.make_block_section('Here are the _amazing_ perks you have unlocked!!'),
            BKitB.make_block_section([p for p in final_perks]),
            BKitB.make_block_section(f'...and don\'t forget you have *`{ltits}`* LTITs! That\'s something, too!')
        ]

    def new_role_form_p1(self, user: str, channel: str):
        """Builds form to intake emoji and upload"""
        # Load user
        user_obj = self.eng.get_user_from_hash(user)
        form1 = self.build_role_input_form_p1(existing_title=user_obj.role_title)
        _ = self.st.private_channel_message(user_id=user, channel=channel, message='New role form, p1',
                                            blocks=form1)

    def new_role_form_p2(self, user: str, channel: str, new_title: str):
        """Part 2 of new role intake"""
        # Load user
        user_obj = self.eng.get_user_from_hash(user)
        if new_title != user_obj.role_title:
            with self.eng.session_mgr() as session:
                session.add(user_obj)
                user_obj.role_title = new_title
        form2 = self.build_role_input_form_p2(title=new_title, existing_desc=user_obj.role_desc)
        _ = self.st.private_channel_message(user_id=user, channel=channel, message='New role form, p2',
                                            blocks=form2)

    def update_user_level(self, channel: str, requesting_user: str, target_user: str) -> Optional[str]:
        """Increment the user's level"""

        if requesting_user not in self.approved_users:
            return 'LOL sorry, levelups are SLT-approved only. If you\'re already SLT, it\'s the _other_ SLT tihi'

        if target_user == 'UPLAE3N67':
            # Some people should stay permanently at lvl 1
            return 'Hmm... that\'s weird. It says you can\'t be leveled up??'

        user_obj = self.eng.get_user_from_hash(target_user)
        if user_obj is None:
            return f'user <@{target_user}> not found in HR records... :nervous_peach:'
        with self.eng.session_mgr() as session:
            session.add(user_obj)
            user_obj.level += 1
        self.st.send_message(channel, f'Level for *`{user_obj.name}`* updated to *`{user_obj.level}`*.')

    def update_user_ltips(self, channel: str, requesting_user: str, target_user: str, ltits: float) -> \
            Optional[str]:
        """Increment the user's level"""

        if requesting_user not in self.approved_users:
            return 'LOL sorry, LTIT distributions are SLT-approved only'

        user_obj = self.eng.get_user_from_hash(target_user)
        if user_obj is None:
            return f'user <@{target_user}> not found in HR records... :nervous_peach:'
        with self.eng.session_mgr() as session:
            session.add(user_obj)
            user_obj.ltits += ltits
        self.st.send_message(
            channel, f'LTITs for  *`{user_obj.name}`* updated by *`{ltits}`* to *`{user_obj.ltits}`*.')

    def show_roles(self, user: str = None) -> Union[List[Dict], str]:
        """Prints users roles to channel"""
        def build_employee_info(emp: TableSlackUser) -> str:
            """Build out an individual line of an employee's info"""
            role = emp.role_title
            role_desc = emp.role_desc
            if role is None:
                role = 'You take the specifications from the customers, and you bring them ' \
                       'down to the software engineers'
            if role_desc is None:
                role_desc = 'What would you say... you do here?'

            return f'*`{emp.display_name}`*: Level *`{emp.level}`* (*`{emp.ltits}`* LTITs)\n' \
                   f'\t\t*{role}*\n\t\t\t{role_desc}'

        roles_output = []
        if user is None:
            # Printing roles for everyone
            roles_output += [
                BKitB.make_header('OKR Roles'),
                BKitB.make_context_section([
                    BKitB.markdown_section('_(as of last reorg)_')
                ])
            ]
            # Iterate through roles, print them out
            with self.eng.session_mgr() as session:
                users = session.query(TableSlackUser).all()
                session.expunge_all()
            roles_output += [BKitB.make_block_section([build_employee_info(emp=u)]) for u in users]
        else:
            # Printing role for an individual user
            user_obj = self.eng.get_user_from_hash(user_hash=user)
            if user_obj is None:
                return f'user <@{user}> not found in HR records... :nervous_peach:'
            roles_output.append(BKitB.make_block_section([build_employee_info(emp=user_obj)]))

        return roles_output

    def build_role_txt(self, channel: str, user: str = None):
        """Constructs a text blob consisting of roles without exceeding the character limits of Slack"""
        roles_output = self.show_roles(user)
        self.st.send_message(channel, message='Roles output', blocks=roles_output)
