#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
import string
import requests
import pandas as pd
import numpy as np
from datetime import datetime as dt
from random import randint
from io import StringIO
import urllib.parse as parse
from lxml import etree
from slacktools import SlackTools, GSheetReader
from ._version import get_versions


class Viktor:
    """Handles messaging to and from Slack API"""

    def __init__(self, log_name, xoxb_token, xoxp_token, ss_key, onboarding_key, debug=False):
        """
        :param log_name: str, name of the log to retrieve
        :param debug: bool,
        """
        self.bot_name = 'Viktor'
        self.triggers = ['viktor', 'v!'] if not debug else ['deviktor', 'dv!']
        self.alerts_channel = 'alerts'  # #alerts
        # Read in common tools for interacting with Slack's API
        self.st = SlackTools(log_name, triggers=self.triggers, team='orbitalkettlerelay',
                             xoxp_token=xoxp_token, xoxb_token=xoxb_token)
        # Two types of API interaction: bot-level, user-level
        self.bot = self.st.bot
        self.user = self.st.user
        self.bot_id = self.bot.auth_test()['user_id']

        self.approved_users = ['UM35HE6R5', 'UM3E3G72S']
        self.emoji_list = self._get_emojis()
        self.gs_dict = {}

        self.viktor_sheet = ss_key
        self.onboarding_key = onboarding_key
        self.viktor_sheet_link = f'https://docs.google.com/spreadsheets/d/{self.viktor_sheet}/'
        self.onboarding_link = f'https://docs.google.com/document/d/{self.onboarding_key}/edit?usp=sharing'
        self._read_in_sheets()
        self.roles = self.read_roles()

        version_dict = get_versions()
        self.version = version_dict['version']
        self.update_date = pd.to_datetime(version_dict['date']).strftime('%F %T')
        self.bootup_msg = f'```Booted up at {pd.datetime.now():%F %T}! '\
                          f'\n\t{self.version} (updated {self.update_date})```'
        self.st.send_message('test', self.bootup_msg)

        # This will be built later
        self.help_txt = ''

        cat_basic = 'basic'
        cat_useful = 'useful'
        cat_notsouseful = 'not so useful'

        self.cmd_dict = {
            r'^help': {
                'pattern': 'help',
                'cat': cat_basic,
                'desc': 'Description of all the commands I respond to!',
                'value': self.help_txt,
            },
            r'^about$': {
                'pattern': 'about',
                'cat': cat_useful,
                'desc': 'Bootup time of Viktor\'s current instance, his version and last update date',
                'value': self.bootup_msg,
            },
            r'good bo[tiy]': {
                'pattern': 'good bo[tiy]',
                'cat': cat_basic,
                'desc': 'Did I do something right for once?',
                'value': 'thanks <@{user}>!',
            },
            r'^(gsheet[s]?|show) link$': {
                'pattern': '(gsheets|show) link',
                'cat': cat_useful,
                'desc': 'Shows link to Viktor\'s GSheet (acronyms, insults, etc..)',
                'value': self.viktor_sheet_link,
            },
            r'^time$': {
                'pattern': 'time',
                'cat': cat_basic,
                'desc': 'Display current server time',
                'value': [self.get_time],
            },
            r'^sauce$': {
                'pattern': 'sauce',
                'cat': cat_basic,
                'desc': 'Handle some ridicule...',
                'value': 'ay <@{user}> u got some jokes!',
            },
            r'^speak$': {
                'pattern': 'speak',
                'cat': cat_basic,
                'desc': '_Really_ basic response here.',
                'value': 'woof',
            },
            r'^uwu that$': {
                'pattern': 'uwu that',
                'cat': cat_notsouseful,
                'desc': 'Uwu the text immediately above this command.',
                'value': [self.uwu_that, 'channel', 'ts'],
            },
            r'^show (roles|doo[td]ies)$': {
                'pattern': 'show (roles|doo[td]ies)',
                'cat': cat_useful,
                'desc': 'Shows current roles of all the wonderful workers of OKR',
                'value': [self.build_role_txt, 'channel'],
            },
            r'^update doo[td]ies': {
                'pattern': 'update dooties [-u @user]',
                'cat': cat_useful,
                'desc': 'Updates OKR roles of user (or other user). Useful during a quick reorg. '
                        '\n\t\t\t_NOTE: You only have to tag a user if it\'s not you._',
                'value': [self.update_roles, 'user', 'channel', 'raw_message'],
            },
            r'^show my (role|doo[td]ie)$': {
                'pattern': 'show my (role|doo[td]ie)',
                'cat': cat_useful,
                'desc': 'Shows your current role as of the last reorg.',
                'value': [self.build_role_txt, 'channel', 'user'],
            },
            r'^channel stats$': {
                'pattern': 'channel stats',
                'cat': cat_useful,
                'desc': 'Get a leaderboard of the last 1000 messages posted in the channel',
                'value': [self.get_channel_stats, 'channel'],
            },
            r'^(ag|acro[-]?guess)': {
                'pattern': '(acro-guess|ag) <acronym> [-<group>]',
                'cat': cat_notsouseful,
                'desc': 'There are RBNs of TLAs at OKR. This tries RRRRH to guess WTF they mean IRL. '
                        '\n\t\t\tThe optional group name corresponds to the column name '
                        'of the acronyms in Viktor\'s spreadsheet',
                'value': [self.guess_acronym, 'message'],
            },
            r'^insult': {
                'pattern': 'insult <thing|person> [-<group>]',
                'cat': cat_notsouseful,
                'desc': 'Generates an insult. The optional group name corresponds to the column name '
                        'of the insults in Viktor\'s spreadsheet',
                'value': [self.insult, 'message'],
            },
            r'^compliment': {
                'pattern': 'compliment <thing|person> [-<group>]',
                'cat': cat_notsouseful,
                'desc': 'Generates a :q:compliment:q:. The optional group name corresponds to the column name '
                        'of the compliments in Viktor\'s spreadsheet',
                'value': [self.compliment, 'raw_message', 'user'],
            },
            r'^emojis like': {
                'pattern': 'emojis like <regex-pattern>',
                'cat': cat_useful,
                'desc': 'Get emojis matching the regex pattern',
                'value': [self.get_emojis_like, 'message'],
            },
            r'^refresh emojis$': {
                'pattern': 'refresh emojis',
                'cat': cat_useful,
                'desc': 'Makes Viktor aware of emojis that have been uploaded since his last reboot.',
                'value': [self._get_emojis],
            },
            r'^uwu': {
                'pattern': 'uwu [-l <1 or 2>] <text_to_uwu>',
                'cat': cat_notsouseful,
                'desc': 'Makes text pwettiew and easiew to uwundewstand (defaults to highest uwu level)',
                'value': [self.uwu, 'raw_message'],
            },
            r'(thanks|(no\s?)*\s(t[h]?ank\s?(you|u)))': {
                'cat': cat_basic,
                'desc': 'Thank Viktor for something',
                'value': [self.overly_polite, 'message'],
            },
            r'^access': {
                'pattern': 'access <literally-anything-else>',
                'cat': cat_notsouseful,
                'desc': 'Try to gain access to something - whether that be the power grid to your failing '
                        'theme park on an island off the coast of Costa Rica or something less pressing.',
                'value': [self.access_something],
            },
            r'^quote me': {
                'pattern': 'quote me <thing-to-quote>',
                'cat': cat_notsouseful,
                'desc': 'Turns your quote into letter emojis',
                'value': [self.quote_me, 'message'],
            },
            r'^refresh sheets$': {
                'pattern': 'refresh sheets',
                'cat': cat_useful,
                'desc': 'Pulls in new data from Viktor\'s GSheet.',
                'value': [self.refresh_sheets],
            },
            r'^(he(y|llo)|howdy|salu|hi|qq|wyd|greet|servus|ter|bonj)': {
                'cat': cat_notsouseful,
                'desc': 'Responds appropriately to a simple greeting',
                'value': [self.sh_response],
            },
            r'.*inspir.*': {
                'pattern': '<any text with "inspir" in it>',
                'cat': cat_notsouseful,
                'desc': 'Uploads an inspirational picture',
                'value': [self.inspirational, 'channel'],
            },
            r'.*tihi.*': {
                'pattern': '<any text with "tihi" in it>',
                'cat': cat_notsouseful,
                'desc': 'Giggles',
                'value': [self.giggle],
            },
            r'^onbo[a]?r[d]?ing$': {
                'pattern': '(onboarding|onboring)',
                'cat': cat_useful,
                'desc': 'Prints out all the material needed to get a new OKR employee up to speed!',
                'value': [self.onboarding_docs],
            },
            r'^update level': {
                'pattern': 'update level -u <user>',
                'cat': cat_useful,
                'desc': 'Accesses an employee\'s LevelUp registry and increments their level',
                'value': [self.update_user_level, 'channel', 'user', 'message']
            },
            r'^show (my )?perk[s]?': {
                'pattern': 'show [my] perk(s)',
                'cat': cat_useful,
                'desc': 'Shows the perks an employee has access to at their current level',
                'value': [self.show_my_perks, 'user']
            },
            r'^show all perks': {
                'pattern': 'show all perks',
                'cat': cat_useful,
                'desc': 'Shows all perks currently available at OKR',
                'value': [self.show_all_perks]
            },
            r'^e[nt]\s': {
                'pattern': 'et <word-to-translate>',
                'cat': cat_useful,
                'desc': 'Offers a translation of an Estonian word',
                'value': [self.prep_message_for_translation, 'message']
            },
            r'^ekss\s': {
                'pattern': 'ekss <word-to-lookup>',
                'cat': cat_useful,
                'desc': 'Offers example usage of the given Estonian word',
                'value': [self.prep_message_for_examples, 'message']
            }
        }

        # Lastly, build the help text based on the commands above and insert back into the commands dict
        self.build_help_txt()
        self.cmd_dict[r'^help']['value'] = self.help_txt

    def build_help_txt(self):
        """Builds Viktor's description of functions into a giant wall of text"""
        intro_txt = "Здравствуйте! I'm Viktor (V for short). Here's what I can do:"
        help_dict = {
            'basic': [],
            'useful': [],
            'not so useful': [],
        }
        for k, v in self.cmd_dict.items():
            if 'pattern' not in v.keys():
                v['pattern'] = k
            help_dict[v['cat']].append(f' - `{v["pattern"]}`: {v["desc"]}')

        command_frags = []
        for k, v in help_dict.items():
            list_of_cmds = "\n\t".join(v)
            command_frags.append(f'*{k.title()} Commands*:\n\t{list_of_cmds}')

        self.help_txt = "{}\n{}".format(intro_txt, '\n'.join(command_frags))

    # Packet handling
    # ====================================================
    @staticmethod
    def call_command(cmd, *args, **kwargs):
        """
        Calls the command referenced while passing in arguments
        :return: None or string
        """
        return cmd(*args, **kwargs)

    def handle_command(self, event_dict):
        """Handles a bot command if it's known"""
        # Simple commands that we can map to a function
        response = None
        message = event_dict['message']
        channel = event_dict['channel']

        is_matched = False
        for regex, resp_dict in self.cmd_dict.items():
            match = re.match(regex, message)
            if match is not None:
                # We've matched on a command
                resp = resp_dict['value']
                if isinstance(resp, list):
                    # Copy the list to ensure changes aren't propagated to the command list
                    resp_list = resp.copy()
                    # Examine list, replace any known strings ('message', 'channel', etc.)
                    #   with event context variables
                    for k, v in event_dict.items():
                        if k in resp_list:
                            resp_list[resp_list.index(k)] = v
                    # Function with args; sometimes response can be None
                    response = self.call_command(*resp_list)
                else:
                    # String response
                    response = resp
                is_matched = True
                break
        if message != '' and not is_matched:
            response = f"I didn\'t understand this: `{message}`\n " \
                       f"Use {' or '.join([f'`{x} help`' for x in self.triggers])} to get a list of my commands."

        if response is not None:
            try:
                response = response.format(**event_dict)
            except KeyError:
                # Response likely has some curly braces in it that disrupt str.format().
                # Pass string without formatting
                pass
            self.st.send_message(channel, response)

    # General support methods
    # ====================================================
    def get_prev_msg_in_channel(self, channel, timestamp):
        """Gets the previous message from the channel"""
        resp = self.bot.conversations_history(
            channel=channel,
            latest=timestamp,
            limit=10)
        if not resp['ok']:
            return None
        if 'messages' in resp.data.keys():
            msgs = resp['messages']
            return msgs[0]['text']
        return None

    def get_channel_stats(self, channel):
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

    def message_grp(self, message):
        """Wrapper to send message to whole channel"""
        self.st.send_message(self.alerts_channel, message)

    def get_user_by_id(self, user_id, user_list):
        """Returns a dictionary of player info that has a matching 'id' value in a list of player dicts"""
        user_idx = self.get_user_index_by_id(user_id, user_list)
        return user_list[user_idx]

    @staticmethod
    def get_user_index_by_id(user_id, user_list):
        """Returns the index of a player in a list of players that has a matching 'id' value"""
        return user_list.index([x for x in user_list if x['id'] == user_id][0])

    def _get_emojis(self):
        """Collect emojis in workspace, remove those that are parts of a larger emoji"""
        emojis = list(self.st.get_emojis().keys())
        regex = re.compile('.*[0-9][-_][0-9].*')
        matches = list(filter(regex.match, emojis))
        return [x for x in emojis if x not in matches]

    def get_emojis_like(self, message, max_res=500):
        """Gets emojis matching in the system that match a given regex pattern"""

        # Parse the regex from the message
        ptrn = re.search(r'(?<=emojis like ).*', message)
        if ptrn.group(0) != '':
            # We've got a pattern to use
            pattern = re.compile(ptrn.group(0))
            emojis = self.st.get_emojis()
            matches = [k for k, v in emojis.items() if pattern.match(k)]
            len_match = len(matches)
            if len_match > 0:
                # Slack apparently handles message length limitations on its end, so
                #   let's just put all the emojis together into one string
                response = ''.join([':{}:'.format(x) for x in matches[:max_res]])
            else:
                response = 'No results for pattern `{}`'.format(ptrn.group(0))

            if len_match >= max_res:
                # Append to the emoji_str that it was truncated
                trunc_resp = '`**Truncated Results ({}) -> ({})**`'.format(len_match, max_res)
                response = '{}\n{}'.format(trunc_resp, response)
        else:
            response = "I couldn't find a pattern from your message. Get your shit together <@{user}>"
        return response

    def _read_in_sheets(self):
        """Reads in GSheets for Viktor"""
        gs = GSheetReader(self.viktor_sheet)
        sheets = gs.sheets
        self.gs_dict = {}
        for sheet in sheets:
            self.gs_dict.update({
                sheet.title: gs.get_sheet(sheet.title)
            })

    def refresh_sheets(self):
        """Refreshes Viktor's Google Sheet"""
        self._read_in_sheets()
        return 'Sheets have been refreshed! `{}`'.format(','.join(self.gs_dict.keys()))

    @staticmethod
    def _grab_flag(msg_split, default_flag):
        """Collects flag from message. If no flag, uses a default"""
        # Check if flag is at the end of the msg
        flag = msg_split[-1]
        if '-' in flag:
            flag = flag.replace('-', '')
            # Skip the last part of the message, as that's the flag
            target = ' '.join(msg_split[1:-1])
        else:
            flag = default_flag
            # Get the rest of the message
            target = ' '.join(msg_split[1:])
        return flag, target

    @staticmethod
    def _build_flag_dict(col_list):
        """Builds a dictionary of the columns for a particular sheet that
            contains several ordered columns grouped under a central theme"""
        # Parse the columns into flags and order
        flag_dict = {}
        for col in col_list:
            if '_' in col:
                k, v = col.split('_')
                if k in flag_dict.keys():
                    flag_dict[k].append(col)
                else:
                    flag_dict[k] = [col]
        return flag_dict

    # Basic / Static standalone methods
    # ====================================================
    @staticmethod
    def sarcastic_response():
        """Sends back a sarcastic response when user is not allowed to use the action requested"""
        sarcastic_reponses = [
            ''.join([':ah-ah-ah:'] * randint(0, 50)),
            'Lol <@{user}>... here ya go bruv :pick:',
            'Nah boo, we good.',
            'Yeah, how about you go on ahead and, you know, do that yourself.'
            ':bye_felicia:'
        ]

        return sarcastic_reponses[randint(0, len(sarcastic_reponses) - 1)]

    @staticmethod
    def giggle():
        """Laughs, uncontrollably at times"""
        # Count the 'no's
        laugh_cycles = randint(1, 500)
        response = f'ti{"hi" * laugh_cycles}!'
        return response

    @staticmethod
    def overly_polite(message):
        """Responds to 'no, thank you' with an extra 'no' """
        # Count the 'no's
        no_cnt = message.count('no')
        no_cnt += 1
        response = '{}, thank you!'.format(', '.join(['no'] * no_cnt)).capitalize()
        return response

    @staticmethod
    def access_something():
        """Return random number of ah-ah-ah emojis (Jurassic Park movie reference)"""
        return ''.join([':ah-ah-ah:'] * randint(5, 50))

    @staticmethod
    def get_time():
        """Gets the server time"""
        return f'The server time is `{dt.today():%F %T}`'

    # Misc. methods
    # ====================================================
    def sh_response(self):
        """Responds to SHs"""
        resp_df = self.gs_dict['responses']
        responses = resp_df['responses_list'].unique().tolist()
        return responses[randint(0, len(responses) - 1)]

    def guess_acronym(self, message):
        """Tries to guess an acronym from a message"""
        message_split = message.split()
        if len(message_split) <= 1:
            return "I can't work like this! I need a real acronym!!:ragetype:"
        # We can work with this
        acronym = message_split[1]
        if len(message_split) >= 3:
            flag = message_split[2].replace('-', '')
        else:
            flag = 'standard'
        # clean of any punctuation (or non-letters)
        acronym = re.sub(r'\W', '', acronym)

        # Choose the acronym list to use
        acro_df = self.gs_dict['acronyms']
        cols = acro_df.columns.tolist()
        if flag not in cols:
            return 'Cannot find set `{}` in the `acronyms` sheet. ' \
                   'Available sets: `{}`'.format(flag, ','.join(cols))
        words = acro_df.loc[~acro_df[flag].isnull(), flag].unique().tolist()

        # Put the words into a dictionary, classified by first letter
        a2z = string.ascii_lowercase
        word_dict = {k: [] for k in a2z}
        for word in words:
            word = word.replace('\n', '')
            if len(word) > 1:
                word_dict[word[0].lower()].append(word.lower())

        # Build out the real acryonym meaning
        guesses = []
        for guess in range(3):
            meaning = []
            for letter in list(acronym):
                if letter.isalpha():
                    word_list = word_dict[letter]
                    meaning.append(word_list[randint(0, len(word_list) - 1)])
                else:
                    meaning.append(letter)
            guesses.append(' '.join(list(map(str.title, meaning))))

        return ':robot-face: Here are my guesses for *{}*!\n {}'.format(acronym.upper(),
                                                                        '\n_OR_\n'.join(guesses))

    def insult(self, message):
        """Insults the user at their request"""
        message_split = message.split()
        if len(message_split) <= 1:
            return "I can't work like this! I need something to insult!!:ragetype:"

        # We can work with this
        flag, target = self._grab_flag(message_split, 'standard')

        # Choose the acronym list to use
        insult_df = self.gs_dict['insults']
        cols = insult_df.columns.tolist()
        flag_dict = self._build_flag_dict(cols)

        if flag not in flag_dict.keys():
            return 'Cannot find set `{}` in the `insults` sheet. ' \
                   'Available sets: `{}`'.format(flag, ','.join(flag_dict.keys()))
        insults = []
        for insult_part in sorted(flag_dict[flag]):
            part_series = insult_df[insult_part].replace('', np.NaN).dropna().unique()
            part = part_series.tolist()
            insults.append(part[randint(0, len(part) - 1)])

        if target.lower() == 'me':
            return "You aint nothin but a {}".format(' '.join(insults))
        else:
            return "{} aint nothin but a {}".format(target, ' '.join(insults))

    def compliment(self, message, user):
        """Insults the user at their request"""
        message_split = message.split()
        if len(message_split) <= 1:
            return "I can't work like this! I need something to compliment!!:ragetype:"

        # We can work with this
        flag, target = self._grab_flag(message_split, 'std')

        # Choose the acronym list to use
        compliment_df = self.gs_dict['compliments']
        cols = compliment_df.columns.tolist()
        flag_dict = self._build_flag_dict(cols)

        if flag not in flag_dict.keys():
            return 'Cannot find set `{}` in the `compliments` sheet. ' \
                   'Available sets: `{}`'.format(flag, ','.join(flag_dict.keys()))
        compliments = []
        for compliment_part in sorted(flag_dict[flag]):
            part_series = compliment_df[compliment_part].replace('', np.NaN).dropna().unique()
            part = part_series.tolist()
            txt = part[randint(0, len(part) - 1)]
            if any([x.isalnum() for x in list(txt)]):
                # If there are any alphanumerics in the string, append (space will be added)
                compliments.append(txt)
            else:
                # txt is likely just a bunch of punctuation. Try to combine with the previous item in the list
                if len(compliments) > 0:
                    compliments[-1] += txt
                else:
                    # Just append it. We tried.
                    compliments.append(txt)

        if target == 'me':
            return "{} Viktor.".format(' '.join(compliments))
        else:
            return "Dear {}, {} <@{}>".format(target, ' '.join(compliments), user)

    def inspirational(self, channel):
        """Sends a random inspirational message"""
        resp = requests.get('http://inspirobot.me/api?generate=true')
        if resp.status_code == 200:
            url = resp.text
            # Download img
            img = requests.get(url)
            if img.status_code == 200:
                with open('/tmp/inspirational.jpg', 'wb') as f:
                    f.write(img.content)
                self.st.upload_file(channel, '/tmp/inspirational.jpg', 'inspirational-shit.jpg')

    def uwu_that(self, channel, ts):
        """Retrieves previous message and converts to UwU"""
        return self.uwu(self.get_prev_msg_in_channel(channel, ts))

    def uwu(self, msg):
        """uwu-fy a message"""
        default_lvl = 2

        if '-l' in msg.split():
            level = msg.split()[msg.split().index('-l') + 1]
            level = int(level) if level.isnumeric() else default_lvl
            text = ' '.join(msg.split()[msg.split().index('-l') + 2:])
        else:
            level = default_lvl
            text = msg.replace('uwu', '').strip()

        uwu_df = self.gs_dict['uwu_graphics']
        chars = uwu_df['uwu'].tolist()

        if level >= 1:
            # Level 1: Letter replacement
            text = text.translate(str.maketrans('rRlL', 'wWwW'))

        if level >= 2:
            # Level 2: Placement of 'uwu' when certain patterns occur
            pattern_whitelist = {
                'uwu': {
                    'start': 'u',
                    'anywhere': ['nu', 'ou', 'du', 'un', 'bu'],
                },
                'owo': {
                    'start': 'o',
                    'anywhere': ['ow', 'bo', 'do', 'on'],
                }
            }
            # Rebuild the phrase letter by letter
            phrase = []
            for word in text.split(' '):
                for pattern, pattern_dict in pattern_whitelist.items():
                    if word.startswith(pattern_dict['start']):
                        word = word.replace(pattern_dict['start'], pattern)
                    else:
                        for fragment in pattern_dict['anywhere']:
                            if fragment in word:
                                word = word.replace(pattern_dict['start'], pattern)
                phrase.append(word)
            text = ' '.join(phrase)

            # Last step, insert random characters
            prefix_emoji = chars[np.random.choice(len(chars), 1)[0]]
            suffix_emoji = chars[np.random.choice(len(chars), 1)[0]]
            text = f'{prefix_emoji} {text} {suffix_emoji}'

        return text.replace('`', ' ')

    def quote_me(self, message):
        """Converts message into letter emojis"""
        msg = message[len('quote me'):].strip()
        return self.st.build_phrase(msg)

    # Language methods
    # ====================================================
    @staticmethod
    def prep_for_xpath(url):
        """Takes in a url and returns a tree that can be searched using xpath"""
        page = requests.get(url)
        html = page.content.decode('utf-8')
        parser = etree.HTMLParser()
        tree = etree.parse(StringIO(html), parser=parser)
        return tree

    def prep_message_for_translation(self, message):
        """Takes in the raw message and prepares it for lookup"""
        # Format should be like `et <word>` or `en <word>`
        word = re.sub(r'^e[nt]\s', '', message)
        target = message[:2]

        # Make sure the word is a root if it's Estonian
        if target == 'en':
            word = self.get_root(word)

        if word is not None:
            return self._get_translation(word, target)
        else:
            return 'Translation not found.'

    def _get_translation(self, word, target='en'):
        """Returns the English translation of the Estonian word"""
        # Find the English translation of the word using EKI
        eki_url = f'http://www.eki.ee/dict/ies/index.cgi?Q={parse.quote(word)}&F=V&C06={target}'
        content = self.prep_for_xpath(eki_url)

        results = content.xpath('//div[@class="tervikart"]')
        result = []
        for i in range(0, len(results)):
            et_result = content.xpath(f'(//div[@class="tervikart"])[{i + 1}]/*/span[@lang="et"]')
            en_result = content.xpath(f'(//div[@class="tervikart"])[{i + 1}]/*/span[@lang="en"]')
            # Process text in elements
            et_result = [''.join(x.itertext()) for x in et_result]
            en_result = [''.join(x.itertext()) for x in en_result]
            if target == 'en':
                if word in et_result:
                    result += en_result
            else:
                if word in en_result:
                    result += et_result

        if len(result) > 0:
            # Make all entries lowercase and remove dupes
            result = list(set(map(str.lower, result)))
            return f"`{word}`: {', '.join(result)}"
        else:
            return f'No results found for `{word}` :frowning:'

    def prep_message_for_examples(self, message):
        """Takes in the raw message and prepares it for lookup"""
        # Format should be like `et <word>` or `en <word>`
        word = re.sub(r'^ekss\s', '', message)
        word = self.get_root(word)

        if word is not None:
            return self._get_examples(word, max_n=5)
        else:
            return 'No examples found.'

    def _get_examples(self, word, max_n=5):
        """Returns some example sentences of the Estonian word"""
        # Find the English translation of the word using EKI
        ekss_url = f'http://www.eki.ee/dict/ekss/index.cgi?Q={parse.quote(word)}&F=M'
        content = self.prep_for_xpath(ekss_url)

        results = content.xpath('//div[@class="tervikart"]')
        exp_list = []
        for i in range(0, len(results)):
            result = content.xpath(f'(//div[@class="tervikart"])[{i + 1}]/*/span[@class="m leitud_id"]')
            examples = content.xpath(f'(//div[@class="tervikart"])[{i + 1}]/*/span[@class="n"]')
            # Process text in elements
            result = [''.join(x.itertext()) for x in result]
            examples = [''.join(x.itertext()) for x in examples]
            if word in result:
                re.split(r'[?\.!]', ''.join(examples))
                exp_list += re.split(r'[?\.!]', ''.join(examples))
                # Strip of leading / tailing whitespace
                exp_list = [x.strip() for x in exp_list if x.strip() != '']
                if len(exp_list) > max_n:
                    exp_list = [exp_list[x] for x in np.random.choice(len(exp_list), max_n, False).tolist()]
                examples = '\n'.join([f'`{x}`' for x in exp_list])
                return f'Examples for `{word}`:\n{examples}'

        return f'No example sentences found for `{word}`'

    @staticmethod
    def get_root(word):
        """Retrieves the root word (nom. sing.) from Lemmatiseerija"""
        # First, look up the word's root with the lemmatiseerija
        lemma_url = f'https://www.filosoft.ee/lemma_et/lemma.cgi?word={parse.quote(word)}'
        content = requests.get(lemma_url).content
        content = str(content, 'utf-8')
        # Use regex to find the word/s
        lemma_regex = re.compile(r'<strong>.*na\slemma[d]?\son:<\/strong><br>(\w+)<br>')
        match = lemma_regex.search(content)
        word = None
        if match is not None:
            word = match.group(1)
        return word

    # OKR Roles / Perks
    # ====================================================
    def onboarding_docs(self):
        """Returns links to everything needed to bring a new OKR employee up to speed"""
        docs = f"""
        Welcome to OKR! We're glad to have you on board! 
        Check out these links below to get familiar with OKR and the industry we support!

        Onboarding Doc: {self.onboarding_link}
        Viktor's GSheet: {self.viktor_sheet_link}

        For any questions, reach out to the CEO or our Head of Recruiting. 
            Don't know who they are? Well, figure it out!
        """
        return docs

    def show_all_perks(self):
        """Displays all the perks"""
        perks_df = self.gs_dict['okr_perks']
        perks_df = perks_df.sort_values('level')
        perks = ''
        for level in perks_df['level'].unique().tolist():
            perk_list = '\n\t\t - '.join(perks_df.loc[perks_df['level'] == level, 'perk'].tolist())
            perks += f'`lvl {level}`: \n\t\t - {perk_list}\n'
        return f'*OKR perks*:\n{perks}'

    def show_my_perks(self, user):
        """Lists the perks granted at the user's current level"""
        # Get the user's level
        users_df = self.gs_dict['okr_roles'].copy()
        users_df = users_df[users_df['user'] == user]
        if not users_df.empty:
            level = users_df['level'].values[0]
            perks_df = self.gs_dict['okr_perks'].copy()
            perks_df = perks_df[perks_df['level'] <= level]
            # Sort by perks level
            perks_df = perks_df.sort_values('level', ascending=True)
            perks = ''
            for i, row in perks_df.iterrows():
                perks += f'`lvl {row["level"]}`: {row["perk"]}\n'
            return f'WOW <@{user}>! You\'re at level `{level}`!!\n' \
                   f'You have access to the following _amazing_ perks:\n\n{perks}'
        else:
            return 'User not found in OKR roles sheet :frowning:'

    def update_user_level(self, channel, user, message):
        """Increment the user's level"""
        if user not in self.approved_users:
            return 'LOL sorry, levelups are CEO-approved only'

        content = message[len('update level'):].strip()
        if '-u' in content:
            # Updating role of other user
            # Extract user
            user = content.split()[1].replace('<@', '').replace('>', '').upper()
            if user == 'UPLAE3N67':
                # Some people should stay permanently at lvl 1
                return 'Hmm... that\'s weird. It says you can\'t be leveled up??'

            level_before = self.roles.loc[self.roles['user'] == user, 'level'].values[0]
            self.roles.loc[self.roles['user'] == user, 'level'] += 1
            # Save roles to Gsheet
            self.write_roles()
            self.st.send_message(channel, f'Level for <@{user}> updated to `{level_before + 1}`.')
        else:
            return 'No user tagged for update.'

    def read_roles(self):
        """Reads in JSON of roles"""
        return self.gs_dict['okr_roles']

    def collect_roleplayers(self):
        """Collects user id and name for people having OKR roles"""
        users = self.st.get_channel_members('CM3E3E82J')  # general

        user_df = pd.DataFrame(users)
        user_df['display_name'] = np.where(user_df['display_name'] == '',
                                           user_df['real_name'], user_df['display_name'])
        user_df = user_df.rename(columns={
            'id': 'user',
            'name': 'old_name',
            'display_name': 'name'
        })

        return user_df[['user', 'name']]

    def write_roles(self):
        """Writes roles to GSheeets"""
        user_df = self.collect_roleplayers()
        self.roles = self.roles[['user', 'level', 'role']].merge(user_df, on='user', how='left')
        self.roles = self.roles[['user', 'name', 'level', 'role']]

        self.st.write_sheet(self.viktor_sheet, 'okr_roles', self.roles)

    def update_roles(self, user, channel, msg):
        """Updates a user with their role"""
        content = msg[len('update dooties'):].strip()
        if '-u' in content:
            # Updating role of other user
            # Extract user
            user = content.split()[1].replace('<@', '').replace('>', '').upper()
            content = ' '.join(content.split()[2:])
        self.roles.loc[self.roles['user'] == user, 'role'] = content
        self.st.send_message(channel, 'Role for <@{}> updated.'.format(user))
        # Save roles to Gsheet
        self.write_roles()

    def show_roles(self, user=None):
        """Prints users roles to channel"""

        if user is None:
            # Printing roles for everyone
            roles_output = ['*OKR Roles (as of last reorg)*:', '=' * 10]
            # Iterate through roles, print them out
            for i, row in self.roles.iterrows():
                roles_output.append(f'`{row["name"]}`: Level `{row["level"]}`\n\t\t{row["role"]}')
        else:
            # Printing role for an individual user
            role_row = self.roles[self.roles['user'] == user]
            if not role_row.empty:
                for i, row in role_row.iterrows():
                    roles_output = [f'`{row["name"]}`: Level `{row["level"]}` \n\t\t{row["role"]}']
            else:
                roles_output = ['No roles for you yet. Add them with the `update dooties` command.']

        return roles_output

    def build_role_txt(self, channel, user=None):
        """Constructs a text blob consisting of roles without exceeding the character limits of Slack"""
        roles_output = self.show_roles(user)
        role_txt = ''
        if user is None:
            for role_part in roles_output:
                # Instead of sending a message for every role, try to combine some rolls
                #   as long as they're below a certain text limit
                if len(role_txt) >= 2000:
                    self.st.send_message(channel, role_txt)
                    role_txt = role_part
                else:
                    role_txt += f'\n\n{role_part}'
        else:
            role_txt = '\n'.join(roles_output)
        self.st.send_message(channel, role_txt)
