#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
import string
import requests
import pandas as pd
import numpy as np
from datetime import datetime as dt
from random import randint
from slacktools import SlackTools, GSheetReader
from ._version import get_versions

help_txt = """
I'm Viktor. Here's what I can do:
*Basic Commands:*
    - `(hello|hi|hey|qq|wyd|greetings)`
    - `speak`
    - `good bot`
    - `tihi`
    - `[no] (thanks|thank you|tanks)`
    - `time`
    - `access <literally-anything-else>`
    - `sauce` ?????
*Useful commands:*
    - `gsheets link`, `show link`: Shows link to Viktor's GSheet (acronyms, insults, etc..)
    - `refresh sheets`: Refreshes the GSheet that holds viktor's insults and acronyms
    - `emojis like <regex-pattern>`: get emojis matching the regex pattern
    - `channel stats`: get a leaderboard of the last 1000 messages posted in the channel
    - `show roles`, `show dooties`: Shows roles of all the workers of OKR
    - `update dooties [-u @user]`: Updates OKR roles of user (or other user). Useful during a reorg.
*Not-so-useful Commands:*
    - `(acro-guess|ag) <acronym> [-<group>]`: There are a lot of TLAs at work. This tries to guess what they are.
    - `insult <thing|person> [-<group>]`: generates an insult
    - `compliment <thing|person> [-<set>]`: generates something vaguely similar to a compliment
    - `quote me <thing-to-quote>`: turns your phrase into letter emojis
    - `uwu [-l <1 or 2>] <text_to_uwu>`: makes text pwetty (defaults to lvl 2)
    - `<any text with "inspir" in it>`: something profound to brighten your day
"""


class Viktor:
    """Handles messaging to and from Slack API"""

    def __init__(self, log_name, xoxb_token, xoxp_token):
        """
        :param log_name: str, name of the log to retrieve
        :param debug: bool,
        """
        self.bot_name = 'Viktor'
        self.triggers = ['viktor', 'v!']
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

        self.viktor_sheet = '1KYEbx2Y953u2fIXcntN_xKjBL_6DS02v7y7OcDjv4XU'
        self._read_in_sheets()
        self.roles = self.read_roles()

        version_dict = get_versions()
        self.version = version_dict['version']
        self.update_date = pd.to_datetime(version_dict['date']).strftime('%F %T')
        bootup_msg = f'Booted up at {pd.datetime.now():%F %T}! '   \
                     f'\n\t\tv{self.version} (updated {self.update_date})'
        self.st.send_message('test', bootup_msg)

        self.commands = {
            'good bot': 'thanks <@{user}>!',
            'gsheets link': self.show_gsheet_link(),
            'show link': self.show_gsheet_link(),
            'help': help_txt,
            'sauce': 'ay <@{user}> u got some jokes!',
            'speak': 'woof',
            'about': bootup_msg
        }

    def handle_command(self, event_dict):
        """Handles a bot command if it's known"""
        # Simple commands that we can map to a function
        response = None
        message = event_dict['message']
        raw_message = event_dict['raw_message']
        user = event_dict['user']
        channel = event_dict['channel']

        if message in self.commands.keys():
            cmd = self.commands[message]
            if callable(cmd):
                # Call the command
                response = cmd()
            else:
                # Response string
                response = cmd
        # elif message == 'garage':
        #     if user not in self.approved_users:
        #         response = self.sarcastic_response()
        #     else:
        #         self.take_garage_pic(channel)
        #         response = 'There ya go!'
        # elif message == 'outdoor':
        #     if user not in self.approved_users:
        #         response = self.sarcastic_response()
        #     else:
        #         self.take_outdoor_pic(channel)
        #         response = 'There ya go!'
        elif message == 'time':
            response = 'The time is {:%F %T}'.format(dt.today())
        elif message == 'uwu that':
            response = self.uwu(self.get_prev_msg_in_channel(event_dict))
        elif message in ['show roles', 'show dooties']:
            self.build_role_txt(channel)
        elif message == 'channel stats':
            # response = self.get_channel_stats(channel)
            response = 'This request is currently `borked`. I\'ll repair it later.'
        # elif message.startswith('make sentences') or message.startswith('ms '):
        #     response = self.generate_sentences(message)
        elif any([message.startswith(x) for x in ['acro-guess', 'ag']]):
            response = self.guess_acronym(message)
        elif message.startswith('insult'):
            response = self.insult(raw_message)
        elif message.startswith('compliment'):
            response = self.compliment(raw_message, user)
        elif message.startswith('emojis like'):
            response = self.get_emojis_like(message)
        elif message.startswith('uwu'):
            response = self.uwu(raw_message)
        elif any([x in message for x in ['thank you', 'thanks', 'tanks']]):
            response = self.overly_polite(message)
        elif message.startswith('access'):
            response = ''.join([':ah-ah-ah:'] * randint(5, 50))
        elif message.startswith('quote me'):
            msg = message[len('quote me'):].strip()
            response = self.st.build_phrase(msg)
        elif message.startswith('update dooties'):
            self.update_roles(user, channel, raw_message)
        elif message == 'refresh sheets':
            self._read_in_sheets()
            response = 'Sheets have been refreshed! `{}`'.format(','.join(self.gs_dict.keys()))
        elif any([message.startswith(x) for x in ['hey', 'hello', 'howdy', 'salu', 'hi', 'qq', 'wyd', 'greetings']]):
            response = self.sh_response()
        elif 'inspir' in message:
            # inspire me | give inspiration | inspirational pic
            self.inspirational(channel)
        elif 'tihi' in message:
            response = self.giggle()
        elif message != '':
            response = "I didn't understand this: `{}`\n " \
                       "Use `v!help` to get a list of my commands.".format(message)

        if response is not None:
            resp_dict = {
                'user': user
            }
            self.st.send_message(channel, response.format(**resp_dict))

    def sarcastic_response(self):
        """Sends back a sarcastic response when user is not allowed to use the action requested"""
        sarcastic_reponses = [
            ''.join([':ah-ah-ah:'] * randint(0, 50)),
            'Lol <@{user}>... here ya go bruv :pick:',
            'Nah boo, we good.',
            'Yeah, how about you go on ahead and, you know, do that yourself.'
            ':bye_felicia:'
        ]

        return sarcastic_reponses[randint(0, len(sarcastic_reponses) - 1)]

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
        user_names = pd.DataFrame(self.st.get_users_info(res_df['user'].tolist()))[['id', 'real_name']]
        res_df = res_df.merge(user_names, left_on='user', right_on='id', how='left').drop(['user', 'id'],
                                                                                          axis=1)
        res_df = res_df[['real_name', 'total_messages', 'avg_msg_len']]
        res_df['total_messages'] = res_df['total_messages'].astype(int)
        res_df['avg_msg_len'] = res_df['avg_msg_len'].round(1)
        res_df = res_df.sort_values('total_messages', ascending=False)
        response = '*Stats for this channel:*\n Total messages examined: {}\n' \
                   '```{}```'.format(len(msgs), self.st.df_to_slack_table(res_df))
        return response

    def get_prev_msg_in_channel(self, event_dict):
        """Gets the previous message from the channel"""
        resp = self.bot.conversations_history(
            channel=event_dict['channel'],
            latest=event_dict['ts'],
            limit=10)
        if not resp['ok']:
            return None
        if 'messages' in resp.data.keys():
            msgs = resp['messages']
            return msgs[0]['text']
        return None

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

    def message_grp(self, message):
        """Wrapper to send message to whole channel"""
        self.st.send_message(self.alerts_channel, message)

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
        self.roles = self.roles[['user', 'role']].merge(user_df, on='user', how='left')
        self.roles = self.roles[['user', 'name', 'role']]

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

    def show_roles(self):
        """Prints users roles to channel"""
        roles_output = ['**OKR Roles (as of last reorg)**:', '=' * 10]

        # Iterate through roles, print them out
        for i, row in self.roles.iterrows():
            roles_output.append(f'`{row["name"]}`: {row["role"]}')

        return roles_output

    def build_role_txt(self, channel):
        """Constructs a text blob consisting of roles without exceeding the character limits of Slack"""
        roles_output = self.show_roles()
        role_txt = ''
        for role_part in roles_output:
            # Instead of sending a message for every role, try to combine some rolls
            #   as long as they're below a certain text limit
            if len(role_txt) >= 2000:
                self.st.send_message(channel, role_txt)
                role_txt = role_part
            else:
                role_txt += f'\n\n{role_part}'
        self.st.send_message(channel, role_txt)

    def get_user_by_id(self, user_id, user_list):
        """Returns a dictionary of player info that has a matching 'id' value in a list of player dicts"""
        user_idx = self.get_user_index_by_id(user_id, user_list)
        return user_list[user_idx]

    @staticmethod
    def get_user_index_by_id(user_id, user_list):
        """Returns the index of a player in a list of players that has a matching 'id' value"""
        return user_list.index([x for x in user_list if x['id'] == user_id][0])

    def show_gsheet_link(self):
        """Prints a link to the gsheet in the channel"""
        return f'https://docs.google.com/spreadsheets/d/{self.viktor_sheet}/'

    def _get_emojis(self):
        """Collect emojis in workspace, remove those that are parts of a larger emoji"""
        emojis = list(self.st.get_emojis().keys())
        regex = re.compile('.*[0-9][-_][0-9].*')
        matches = list(filter(regex.match, emojis))
        return [x for x in emojis if x not in matches]

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
