#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
import os
from pathlib import Path
from random import (
    choice,
    randint,
)
import re
import string
import sys
import tempfile
from typing import (
    TYPE_CHECKING,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Union,
)
from urllib.parse import urlparse

from loguru import logger
import numpy as np
import pandas as pd
import requests
from slack_sdk.errors import SlackApiError
from slacktools import SlackBotBase
from slacktools.api.base import BaseApiObject
from slacktools.api.web.conversations import (
    Message,
    ThreadMessage,
)
from slacktools.block_kit.base import BlocksType
from slacktools.block_kit.blocks import (
    ActionsBlock,
    MarkdownContextBlock,
    MarkdownSectionBlock,
    PlainTextHeaderBlock,
    PlainTextSectionBlock,
)
from slacktools.block_kit.elements.formatters import (
    DateFormatter,
    DateFormatType,
    TextFormatter,
)
from slacktools.block_kit.elements.input import ButtonElement
from slacktools.command_processing import build_commands
from sqlalchemy.sql import (
    and_,
    func,
)

from viktor import ROOT_PATH
from viktor.core.linguistics import Linguistics
from viktor.core.phrases import PhraseBuilders
from viktor.core.uwu import (
    UWU,
    recursive_uwu,
)
from viktor.db_eng import ViktorPSQLClient
from viktor.forms import Forms
from viktor.model import (
    BotSettingType,
    ResponseCategory,
    ResponseType,
    TableEmoji,
    TablePerk,
    TableResponse,
    TableSlackUser,
)

if TYPE_CHECKING:
    from viktor.settings import (
        Development,
        Production,
    )


class Viktor(Linguistics, PhraseBuilders, Forms, UWU):
    """Handles messaging to and from Slack API"""

    def __init__(self, eng: ViktorPSQLClient, props: Dict, parent_log: logger,
                 config: Union['Development', 'Production']):
        """
        Args:

        """
        self.bot_name = f'{config.BOT_FIRST_NAME} {config.BOT_LAST_NAME}'
        self.log = parent_log.bind(child_name=self.__class__.__name__)
        self.eng = eng
        self.triggers = config.TRIGGERS
        self.main_channel = config.MAIN_CHANNEL
        self.emoji_channel = config.EMOJI_CHANNEL
        self.general_channel = config.GENERAL_CHANNEL
        self.admins = config.ADMINS
        self.version = config.VERSION
        self.update_date = config.UPDATE_DATE
        self.spreadsheet_key = props['spreadsheet-key']
        self.onboarding_key = props['onboarding-key']

        super().__init__(eng=eng)

        # Begin loading and organizing commands after all methods are accounted for above
        self.commands = build_commands(self, cmd_yaml_path=ROOT_PATH.parent.joinpath('commands.yaml'),
                                       log=self.log)

        # Initate the bot, which comes with common tools for interacting with Slack's API
        self.log.debug('Spinning up SlackBotBase')
        self.is_post_exceptions = self.eng.get_bot_setting(BotSettingType.IS_POST_ERR_TRACEBACK)
        self.st = SlackBotBase(props=props, triggers=self.triggers, main_channel=self.main_channel,
                               admins=self.admins, is_post_exceptions=self.is_post_exceptions, is_debug=config.DEBUG,
                               is_use_session=True, is_rand_response=True)
        # Pass in commands to SlackBotBase, where task delegation occurs
        self.log.debug('Patching in commands to SBB...')
        self.st.update_commands(commands=self.commands)
        self.bot_id = self.st.bot_id
        self.user_id = self.st.user_id
        self.bot = self.st.bot
        self.generate_intro()

        if self.eng.get_bot_setting(BotSettingType.IS_ANNOUNCE_STARTUP):
            self.log.debug('IS_ANNOUNCE_STARTUP was enabled, so sending message to main channel')
            self.st.message_main_channel(blocks=self.get_bootup_msg())

        # Place to temporarily store things. Typical structure is activity -> user -> data
        self.state_store = {
            'react-events': set(),                              # type: Set[str]  # Used to det. unique react events
            'reacts-store': self.eng.get_reaction_emojis(),     # type: List[str]   # List of reacts to randomly select
            'users': self.eng.get_all_users(),                  # type: Dict[str, TableSlackUser]
            'new-emoji': {},
            'new-ltit-req': {},
        }
        self.st.rand_response_methods = [
            self.convert_to_uwu,
            self.convert_to_uwu,
            self.convert_to_uwu,
            self.convert_to_uwu,
            self.word_emoji,
            self.randcap,
            self.randcap,
            self.randcap
        ]

        self.log.debug(f'{self.bot_name} booted up!')

    def get_bootup_msg(self) -> BlocksType:
        now = datetime.now()
        bootup_time_txt = f"{DateFormatType.date_short_pretty.value} at {DateFormatType.time_secs.value}"
        formatted_bootup_date = DateFormatter.localize_dates(now, bootup_time_txt)

        update_dtt = datetime.strptime(self.update_date, '%Y-%m-%d_%H:%M:%S')
        update_time_txt = f"{DateFormatType.date_short_pretty.value} at {DateFormatType.time_secs.value}"
        formatted_update_date = DateFormatter.localize_dates(update_dtt, update_time_txt)
        return [
            MarkdownContextBlock([
                f"*{self.bot_name}* *`{self.version}`* booted up {formatted_bootup_date}",
                f"(updated `{formatted_update_date}`)"
            ])
        ]

    def search_help_block(self, message: str):
        """Takes in a message and filters command descriptions for output
        """
        self.log.debug(f'Got help search command: {message}')
        return self.st.search_help_block(message=message)

    def generate_intro(self) -> List[Dict]:
        """Generates the intro message and feeds it in to the 'help' command"""
        intro = f"Oh hello there! I'm *{self.bot_name}* (:Q::regional_indicator_v::Q: for short).\n" \
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
            MarkdownContextBlock(f'{self.bot_name} died. Pour one out `010100100100100101010000`').asdict()
        ]
        if self.eng.get_bot_setting(BotSettingType.IS_ANNOUNCE_SHUTDOWN):
            self.st.message_main_channel(blocks=notify_block)
        self.log.info('Bot shutting down...')
        sys.exit(0)

    def toggle_user_bot_timeout(self, user: str) -> Optional[bool]:
        self.log.debug(f'Handling bot timeout toggle for user {user}')
        user_obj = self.eng.get_user_from_hash(user)
        if user_obj is None:
            return None
        with self.eng.session_mgr() as session:
            session.query(TableSlackUser).filter(TableSlackUser.slack_user_hash == user).update({
                TableSlackUser.is_in_bot_timeout: not user_obj.is_in_bot_timeout
            })

        user_obj = self.eng.get_user_from_hash(user)
        self.state_store['users'][user] = user_obj
        return user_obj.is_in_bot_timeout

    def process_slash_command(self, event_dict: Dict):
        """Hands off the slash command processing while also refreshing the session"""
        self.st.parse_slash_command(event_dict, users_dict=self.state_store['users'])

    def process_event(self, event_dict: Dict):
        """Hands off the event data while also refreshing the session"""
        self.st.parse_message_event(event_dict, users_dict=self.state_store['users'])

    def process_incoming_action(self, user: str, channel: str, action_dict: Dict, event_dict: Dict) -> Optional:
        """Handles an incoming action (e.g., when a button is clicked)"""
        action_id = action_dict.get('action_id')
        action_value = action_dict.get('value')
        msg = event_dict.get('message', {})
        thread_ts = msg.get('thread_ts')

        self.log.debug(f'Receiving action_id: {action_id} and value: {action_value} from user: {user} in '
                       f'channel: {channel}')

        if self.st.check_user_for_bot_timeout(users_dict=self.state_store['users'], uid=user):
            return None

        if 'buttongame' in action_id:
            # Button game stuff
            game_info = action_value.split('|')
            game_value = game_info[1]
            emoji = game_info[2]
            if game_value.isnumeric():
                game_value = int(game_value) - 5000
                resp = self.update_user_ltips(self.admins[0], target_user=user, ltits=game_value)
                blocks = [
                    MarkdownContextBlock('Button Game Results!'),
                    MarkdownSectionBlock(f'<@{user}>, You selected :{emoji}:, \nwhich carried a market value'
                                         f' of :sparkles: *`{game_value}`* :diddlecoin::sparkles:'),
                    MarkdownContextBlock(resp)
                ]
                self.st.send_message(channel, blocks=blocks, thread_ts=thread_ts)
            else:
                self.st.send_message(channel, self.convert_to_uwu('Oh no, something broke!'))
        elif action_id == 'help':
            self.st.send_message(channel=channel, blocks=self.generate_intro(), thread_ts=thread_ts)
        elif action_id.startswith('shelp'):
            msg = action_id.split('-', maxsplit=1)
            cmd = msg[0]
            blocks = self.search_help_block(f'{cmd[:-1]} -{cmd[-1:]} {msg[1]}')
            for grp in range(0, len(blocks), 50):
                self.st.send_message(channel=channel, blocks=blocks[grp: grp + 50], thread_ts=thread_ts)
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
        elif action_id == 'bot-timeout-user':
            # Check status of user beforehand
            selected_user_id = action_dict.get('selected_user')
            user_obj = self.state_store['users'].get(selected_user_id)
            if user_obj.is_admin:
                message = f'Blocked user {user_obj.display_name} from toggling is_in_bot_timeout - they\'re an admin.'
            else:
                new_state = self.toggle_user_bot_timeout(user=selected_user_id)
                message = f'{user_obj.display_name} is_in_bot_timeout toggled to `{new_state}`'
            self.st.private_channel_message(user_id=user, channel=channel, message=message)
        elif action_id == 'levelup-user':
            resp = self.update_user_level(requesting_user=user, target_user=action_dict.get('selected_user'))
            self.st.send_message(channel=channel, message=resp, thread_ts=thread_ts)
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
            resp = self.update_user_ltips(requesting_user=user, target_user=target_user, ltits=ltits)
            self.st.send_message(channel=channel, message=resp, thread_ts=thread_ts)
        elif action_id == 'new-many-emoji':
            self.add_emoji_p1(user=user, channel=channel, message='', is_many=True)
        elif action_id == 'new-emoji-p1':
            # Store this user's first portion of the new emoji request
            self.process_incoming_emoji_urls(user=user, channel=channel, raw_urls=action_value)
        elif action_id.startswith('new-emoji-p2-'):
            # Compile all the details together and try to get the emoji uploaded
            # Extract emoji_id
            emoji_id = int(action_id.split('-')[-1])
            emoji_dict = self.state_store['new-emoji'].get(user)[emoji_id]
            self.add_emoji(user, channel, url=emoji_dict['url'], new_name=action_value)
        elif action_dict.get('type') in ['message-shortcut', 'shortcut']:
            # Deal  with message shortcuts
            if action_id == 'uwu':
                # Uwu the message
                self.handle_menu_action_msg_transform_and_send(event_dict=event_dict, funktsioon=self.convert_to_uwu)
            elif action_id == 'emojiword':
                # Emojiword the message
                self.handle_menu_action_msg_transform_and_send(event_dict=event_dict, funktsioon=self.word_emoji)
            elif action_id == 'mockthis':
                # Mock the message
                self.handle_menu_action_msg_transform_and_send(event_dict=event_dict, funktsioon=self.randcap)
        else:
            # TODO Otherwise treat the action as a phrase?
            pass

    def uwu_that(self, channel: str, ts: str, thread_ts: str = None) -> Union[BlocksType, Dict, str]:
        if thread_ts is None:
            prev_msg: Message
            prev_msg = self.st.get_previous_msg_in_channel(channel=channel, timestamp=ts)
        else:
            prev_msg: ThreadMessage
            prev_msg, is_the_only_reply = self.st.get_previous_msg_in_thread(channel=channel, timestamp=ts,
                                                                             thread_ts=thread_ts)
            if is_the_only_reply:
                # Likely the uwu command was the first message in thread, so grab parent message
                prev_msg = self.st.get_previous_msg_in_channel(channel=channel, timestamp=thread_ts, inclusive=True)
        blocks = message = None
        try:
            blocks = prev_msg.blocks
        except AttributeError:
            message = prev_msg.text

        if blocks is None and message is None and 'attachments' in prev_msg.__dict__.keys():
            # Try to extract via attachments
            attachments = prev_msg.attachments
            replaced_atts = []
            for i, block in enumerate(attachments):
                if isinstance(block, BaseApiObject):
                    block = block.asdict()
                replaced_atts.append(recursive_uwu(i, block, replace_func=self.convert_to_uwu))
            att_dict = {'attachments': replaced_atts}
            for p in ['subtype', 'type', 'text']:
                if p in prev_msg.asdict().keys():
                    att_dict[p] = prev_msg.asdict()[p]
            return att_dict

        if blocks is not None:
            # Convert blocks to uwu
            replaced_blocks = []
            for i, block in enumerate(blocks):
                if isinstance(block, BaseApiObject):
                    block = block.asdict()
                replaced_blocks.append(recursive_uwu(i, block, replace_func=self.convert_to_uwu))
            return replaced_blocks
        elif message is not None:
            return self.convert_to_uwu(message)
        else:
            return self.convert_to_uwu('I really can\'t work with a message like that. How dare you. Bitch.')

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
        blocks = self.build_main_menu(user=user_id, channel=channel)

        self.st.private_channel_message(user_id=user_id, channel=channel,
                                        message='Welcome to the OKR Global Incorporated Ltd. Inc. main menu!',
                                        blocks=blocks)

    # General support methods
    # ====================================================

    def show_gsheets_link(self) -> str:
        return f'https://docs.google.com/spreadsheets/d/{self.spreadsheet_key}/'

    def show_onboring_link(self) -> str:
        return f'https://docs.google.com/document/d/{self.onboarding_key}/edit?usp=sharing'

    def get_channel_stats(self, channel: str) -> str:
        """Collects posting stats for a given channel"""
        chan_hist = self.st.get_channel_history(channel, limit=1000)
        results = {}

        for msg in chan_hist.messages:
            try:
                user = msg.user
            except AttributeError:
                user = msg.bot_id
            txt_len = len(msg.text)
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
            uid = user.id
            try:
                name = user.profile.display_name
            except KeyError:
                name = user.real_name

            if name == '':
                name = user.real_name
            user_names.append({'id': uid, 'display_name': name})

        user_names_df = pd.DataFrame(user_names).drop_duplicates()
        res_df = res_df.merge(user_names_df, left_on='user', right_on='id', how='left')\
            .drop(['user', 'id'], axis=1).fillna('Unknown User')
        res_df = res_df[['display_name', 'total_messages', 'avg_msg_len']]
        res_df['total_messages'] = res_df['total_messages'].astype(int)
        res_df['avg_msg_len'] = res_df['avg_msg_len'].round(1)
        res_df = res_df.sort_values('total_messages', ascending=False)
        response = '*Stats for this channel:*\n Total messages examined: {}\n' \
                   '```{}```'.format(len(chan_hist.messages), self.st.df_to_slack_table(res_df))
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
    def randcap(message: str) -> str:
        """Randomly capitalize string"""
        message = re.sub(r'^mock', '', message).strip()
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
        return ''.join(char_dict.get(c.lower(), '') for c in msg)

    @staticmethod
    def access_something() -> str:
        """Return random number of ah-ah-ah emojis (Jurassic Park movie reference)"""
        return ''.join([':ah-ah-ah:'] * randint(5, 50))

    @staticmethod
    def get_time() -> str:
        """Gets the server time"""
        return f'The server time is `{datetime.today():%F %T}`'

    @staticmethod
    def wfh_epoch() -> BlocksType:
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
            MarkdownContextBlock('WFH Epoch'),
            MarkdownContextBlock(f'Current WFH epoch time is *`{wfh_secs:.0f}`*.\n ({diff})'),
            MarkdownContextBlock('*The time units you\'re used to:*\n' + '\n'.join(normal_section)),
            MarkdownContextBlock('*Some time units that might be strange to you:*\n' + '\n'.join(strange_section))
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
            emoji = emojis[i - 1]
            btn_blocks.append(
                ButtonElement(f':{emoji}:', value=f'bg|{val + 5000}|{emoji}', action_id=f'buttongame-{i}')
            )

        blocks = [
            PlainTextSectionBlock(
                ':spinny-rainbow-sheep::alphabet-yellow-b::alphabet-yellow-u:'
                ':alphabet-yellow-t::alphabet-yellow-t::alphabet-yellow-o:'
                ':alphabet-yellow-n::blank::alphabet-yellow-g::alphabet-yellow-a:'
                ':alphabet-yellow-m::alphabet-yellow-e::alphabet-yellow-exclamation:'
                ':spinny-rainbow-sheep:'
            ),
            MarkdownContextBlock(
                'Try your luck and guess which button is hiding the LTITs!! '
                f'Only one value has `{win}` LTITs, {len(neg_values)} others have '
                f'{",".join([f"`{x}`" for x in neg_values])}. The rest are `0`.'
            ),
            ActionsBlock(btn_blocks)
        ]

        return blocks

    def quote_me(self, message: str, match_pattern: str) -> Optional[str]:
        """Converts message into letter emojis"""
        msg = re.sub(match_pattern, '', message).strip()
        return self.st.build_phrase(msg)

    def process_incoming_emoji_urls(self, user: str, channel: str, raw_urls: str):
        # Store this user's first portion of the new emoji request
        urls = re.split(r'[\r\n|]', raw_urls)
        self.log.debug(f'{len(urls)} urls processed for emoji extraction.')
        emoji_reqs = {}
        for url in urls:
            url = url.strip()
            emoji_reqs[id(url)] = {
                'url': url,
                'name': os.path.splitext(os.path.split(urlparse(url).path)[1])[0]
            }
        self.state_store['new-emoji'].update({user: emoji_reqs})
        self.log.debug(f'Stored urls in new-emoji state. Keys for user: '
                       f'{len(self.state_store["new-emoji"][user].keys())}')
        for emoji_id, emoji_dict in emoji_reqs.items():
            self.add_emoji_p2(user=user, channel=channel, url=emoji_dict['url'], suggested_name=emoji_dict['name'],
                              emoji_id=emoji_id)

    def add_emoji_p1(self, user: str, channel: str, message: str, is_many: bool = False):
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
            self.process_incoming_emoji_urls(user=user, channel=channel, raw_urls=url)
            # TODO: Back button, to go back and edit something
        else:
            form1 = self.build_new_emoji_form_p1(is_many=is_many)
            _ = self.st.private_channel_message(user_id=user, channel=channel, message='New emoji form, p1',
                                                blocks=form1)

    def add_emoji_p2(self, user: str, channel: str, url: str, suggested_name: str, emoji_id: int):
        """Part 2 of emoji intake"""
        # Check name against existing
        taken_name = None
        with self.eng.session_mgr() as session:
            exists: TableEmoji
            exists = session.query(TableEmoji).filter(TableEmoji.name == suggested_name).one_or_none()
            if exists is not None:
                # Name already exists. Modify it
                suggested_name += f'{exists.emoji_id}'
                taken_name = exists.name

        form2 = self.build_new_emoji_form_p2(url, suggested_name=suggested_name, emoji_id=emoji_id,
                                             taken_name=taken_name)
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
            msg = f'Fact added! id:`{fact.id}`\n{fact.text}'
        self.st.send_message(channel=channel, message=msg)

    def get_fart(self, user: str, channel: str):
        fart_id = randint(1, 3000)
        resp = requests.get(f'https://boredhumans.b-cdn.net/farts/{fart_id}.mp3')
        fartpath = Path(tempfile.gettempdir()).joinpath('fart.mp3')
        if resp.status_code == 200:
            with fartpath.open(mode='wb') as f:
                f.write(resp.content)
            self.st.upload_file(channel=channel, filepath=fartpath.__str__(), filename='fart.mp3',
                                txt='Ok! Here\'s the recording I took of you recently!')

    # OKR Methods
    # ------------------------------------------------
    def onboarding_docs(self) -> BlocksType:
        """Returns links to everything needed to bring a new OKR employee up to speed"""
        docs = [
            PlainTextSectionBlock(
                "Welcome to OKR: Guaranteed to have more morality than your current and former workplaces combined!"
                " We're glad to have you on board. You're family here, and like family, you're stuck with us. Forever."
                "Just think of the pizza parties!\n\n Anyway, check out these links below "
                "to get familiar with OKR family that you are now bloodbound to and the industry "
                "(who knows what that is!) we support!"
            ),
            MarkdownSectionBlock(f'\t{TextFormatter.build_link(self.show_onboring_link(), "Onboring Docs")}'),
            PlainTextSectionBlock(
                "For any questions, reach out to literally anyone here! The CEO or our Head of Recruiting might be "
                "a good start. Don't know who they are? Well, figure it out, fuck-face!"
            )
        ]
        return docs

    def show_all_perks(self) -> BlocksType:
        """Displays all the perks"""
        with self.eng.session_mgr() as session:
            perks = session.query(TablePerk).all()
            session.expunge_all()
        final_perks = self._build_perks_list(perks)
        return [
            PlainTextHeaderBlock('OKR Perks!'),
            MarkdownContextBlock(
                'you\'ll never see anything better, trust us!! '
                'we want you to want to work here but may or may not be actively trying to get more of you'
                ' to leave tihihihiiihihi! *boop* *snug*'
            ),
            MarkdownSectionBlock(final_perks)
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

    def show_my_perks(self, user: str) -> Union[BlocksType, str]:
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
            PlainTextHeaderBlock(f'Perks for our very highly valued `{user_obj.display_name}`!'),
            MarkdownContextBlock('you\'ll _really_ never see anything better, trust us!'),
            MarkdownContextBlock('Here are the _amazing_ perks you have unlocked!!'),
            MarkdownSectionBlock(final_perks),
            MarkdownSectionBlock(f'...and don\'t forget you have *`{ltits}`* LTITs! That\'s something, too!')
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
                existing_desc = user_obj.role_desc
        form2 = self.build_role_input_form_p2(title=new_title, existing_desc=existing_desc)
        _ = self.st.private_channel_message(user_id=user, channel=channel, message='New role form, p2',
                                            blocks=form2)

    def update_user_level(self, requesting_user: str, target_user: str) -> str:
        """Increment the user's level"""

        if requesting_user not in self.admins:
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
            msg = f'Level for *`{user_obj.display_name}`* updated to *`{user_obj.level}`*.'
        return msg

    def update_user_ltips(self, requesting_user: str, target_user: str, ltits: float) -> str:
        """Increment the user's level"""

        if requesting_user not in self.admins:
            return 'LOL sorry, LTIT distributions are SLT-approved only'

        user_obj = self.eng.get_user_from_hash(target_user)
        if user_obj is None:
            return f'user <@{target_user}> not found in HR records... :nervous_peach:'
        with self.eng.session_mgr() as session:
            session.add(user_obj)
            user_obj.ltits += ltits
            return f'LTITs for  *`{user_obj.display_name}`* updated by *`{ltits}`* to *`{user_obj.ltits}`*.'

    def show_roles(self, user: str = None) -> Union[BlocksType, str]:
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
                PlainTextHeaderBlock('OKR Roles'),
                MarkdownContextBlock('_(as of last reorg)_')
            ]
            # Iterate through roles, print them out
            with self.eng.session_mgr() as session:
                users = session.query(TableSlackUser).all()
                session.expunge_all()
                roles_output += [
                    MarkdownSectionBlock(build_employee_info(emp=u)) for u in users
                ]
        else:
            # Printing role for an individual user
            user_obj = self.eng.get_user_from_hash(user_hash=user)
            if user_obj is None:
                return f'user <@{user}> not found in HR records... :nervous_peach:'
            roles_output.append(
                MarkdownSectionBlock(build_employee_info(emp=user_obj))
            )

        return roles_output

    def build_role_txt(self, channel: str, user: str = None):
        """Constructs a text blob consisting of roles without exceeding the character limits of Slack"""
        roles_output = self.show_roles(user)
        self.st.send_message(channel, message='Roles output', blocks=roles_output)

    def good_bot(self, user: str) -> str:
        if user in self.admins:
            return 'thanks daddy' + '!' * randint(1, 10)
        return f'thanks, <@{user}>!'
