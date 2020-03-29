#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
import sys
import string
import requests
import pandas as pd
import numpy as np
from typing import List, Optional, Tuple
from datetime import datetime as dt
from random import randint
from slacktools import SlackBotBase, GSheetReader, BlockKitBuilder
from .linguistics import Linguistics
from ._version import get_versions


class Viktor:
    """Handles messaging to and from Slack API"""

    def __init__(self, log_name: str, xoxb_token: str, xoxp_token: str, ss_key: str, onboarding_key: str,
                 debug: bool = False):
        """
        Args:
            log_name: str, name of the kavalkilu.Log object to retrieve
            xoxb_token: str, bot token to use
            xoxp_token: str, user token to use
            ss_key: str, spreadsheet containing various things Viktor reads in
            onboarding_key: str, link to onboarding documentation
            debug: bool, if True, will use a different set of triggers for testing purposes
        """
        self.bot_name = 'Viktor'
        self.triggers = ['viktor', 'v!'] if not debug else ['deviktor', 'dv!']
        self.main_channel = 'CM376Q90F'  # test
        self.alerts_channel = 'alerts'  # #alerts
        self.approved_users = ['UM35HE6R5', 'UM3E3G72S']
        self.bkb = BlockKitBuilder()
        self.ling = Linguistics()

        # Bot version stuff
        version_dict = get_versions()
        self.version = version_dict['version']
        self.update_date = pd.to_datetime(version_dict['date']).strftime('%F %T')
        self.bootup_msg = [self.bkb.make_context_section([
            f"*{self.bot_name}* *`{self.version}`* booted up at `{pd.datetime.now():%F %T}`!",
            f"(updated {self.update_date})"
        ])]

        # GSheets stuff
        self.gs_dict = {}
        self.viktor_sheet = ss_key
        self.onboarding_key = onboarding_key
        self.viktor_sheet_link = f'https://docs.google.com/spreadsheets/d/{self.viktor_sheet}/'
        self.onboarding_link = f'https://docs.google.com/document/d/{self.onboarding_key}/edit?usp=sharing'
        self._read_in_sheets()
        self.roles = self.read_roles()

        # Intro / help / command description area
        intro = "Здравствуйте! I'm *Viktor* (:regional_indicator_v: for short).\nI can help do stuff for you, " \
                "but you'll need to call my attention first with " \
                f"*`{'`* or *`'.join(self.triggers)}`*\n Example: *`v! hello`*\nHere's what I can do:"
        avi_url = "https://ca.slack-edge.com/TM1A69HCM-ULV018W73-1a94c7650d97-512"
        avi_alt = '<record scratch> You\'re probably wondering how I ended up in this situation'
        cat_basic = 'basic'
        cat_useful = 'useful'
        cat_notsouseful = 'not so useful'
        cat_org = 'org'
        cat_lang = 'language'
        cmd_categories = [cat_basic, cat_useful, cat_notsouseful, cat_lang, cat_org]
        commands = {
            r'^help': {
                'pattern': 'help',
                'cat': cat_basic,
                'desc': 'Description of all the commands I respond to!',
                'value': '',
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
                'cat': cat_org,
                'desc': 'Shows current roles of all the wonderful workers of OKR',
                'value': [self.build_role_txt, 'channel'],
            },
            r'^update doo[td]ies': {
                'pattern': 'update dooties [-u @user]',
                'cat': cat_org,
                'desc': 'Updates OKR roles of user (or other user). Useful during a quick reorg. '
                        '\n\t\t\t_NOTE: You only have to tag a user if it\'s not you._',
                'value': [self.update_roles, 'user', 'channel', 'raw_message'],
            },
            r'^show my (role|doo[td]ie)$': {
                'pattern': 'show my (role|doo[td]ie)',
                'cat': cat_org,
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
            r'^ins[ul]{2}t': {
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
            r'^emoji[s]? like': {
                'pattern': 'emoji[s] like <regex-pattern>',
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
                'cat': cat_org,
                'desc': 'Prints out all the material needed to get a new OKR employee up to speed!',
                'value': [self.onboarding_docs],
            },
            r'^(update\s?level|level\s?up)': {
                'pattern': '(update level|level up) -u <user>',
                'cat': cat_org,
                'desc': 'Accesses an employee\'s LevelUp registry and increments their level',
                'value': [self.update_user_level, 'channel', 'user', 'message']
            },
            r'^ltits': {
                'pattern': 'ltits -u <user> <number>',
                'cat': cat_org,
                'desc': 'Distribute or withdraw LTITs from an employee\'s account',
                'value': [self.update_user_ltips, 'channel', 'user', 'message']
            },
            r'^show (my )?perk[s]?': {
                'pattern': 'show [my] perk(s)',
                'cat': cat_org,
                'desc': 'Shows the perks an employee has access to at their current level',
                'value': [self.show_my_perks, 'user']
            },
            r'^show all perks': {
                'pattern': 'show all perks',
                'cat': cat_org,
                'desc': 'Shows all perks currently available at OKR',
                'value': [self.show_all_perks]
            },
            r'^e[nt]\s': {
                'pattern': '(et|en) <word-to-translate>',
                'cat': cat_lang,
                'desc': 'Offers a translation of an Estonian word into English or vice-versa',
                'value': [self.ling.prep_message_for_translation, 'message']
            },
            r'^ekss\s': {
                'pattern': 'ekss <word-to-lookup>',
                'cat': cat_lang,
                'desc': 'Offers example usage of the given Estonian word',
                'value': [self.ling.prep_message_for_examples, 'message']
            },
            r'^lemma\s': {
                'pattern': 'lemma <word-to-lookup>',
                'cat': cat_lang,
                'desc': 'Determines the lemma of the Estonian word',
                'value': [self.ling.prep_message_for_root, 'message']
            },
            r'^wfh\s?(time|epoch)': {
                'pattern': 'wfh (time|epoch)',
                'cat': cat_useful,
                'desc': 'Prints the current WFH epoch time',
                'value': [self.wfh_epoch]
            },
            r'^ety\s': {
                'pattern': 'ety <word>',
                'cat': cat_useful,
                'desc': 'Gets the etymology of a given word',
                'value': [self.ling.get_etymology, 'message']
            }
        }

        # Initate the bot, which comes with common tools for interacting with Slack's API
        self.st = SlackBotBase(log_name, triggers=self.triggers, team='orbitalkettlerelay',
                               main_channel=self.main_channel, xoxp_token=xoxp_token, xoxb_token=xoxb_token,
                               commands=commands, cmd_categories=cmd_categories)
        self.bot_id = self.st.bot_id
        self.bot = self.st.bot
        self.emoji_list = self._get_emojis()

        self.st.message_main_channel(blocks=self.bootup_msg)

        # Lastly, build the help text based on the commands above and insert back into the commands dict
        commands[r'^help']['value'] = self.st.build_help_block(intro, avi_url, avi_alt)
        # Update the command dict in SlackBotBase
        self.st.update_commands(commands)

    def cleanup(self, *args):
        """Runs just before instance is destroyed"""
        notify_block = [
            self.bkb.make_context_section(f'{self.bot_name} died. :death-drops::party-dead::death-drops:'),
            self.bkb.make_context_section(self.st.build_phrase('pour one out'))
        ]
        self.st.message_main_channel(blocks=notify_block)
        sys.exit(0)

    # General support methods
    # ====================================================
    def get_channel_stats(self, channel: str, **kwargs) -> str:
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

    def get_user_by_id(self, user_id: str, user_list: List[dict]) -> dict:
        """Returns a dictionary of player info that has a matching 'id' value in a list of player dicts"""
        user_idx = self.get_user_index_by_id(user_id, user_list)
        return user_list[user_idx]

    @staticmethod
    def get_user_index_by_id(user_id: str, user_list: List[dict]) -> int:
        """Returns the index of a player in a list of players that has a matching 'id' value"""
        return user_list.index([x for x in user_list if x['id'] == user_id][0])

    def _get_emojis(self, **kwargs) -> List[str]:
        """Collect emojis in workspace, remove those that are parts of a larger emoji"""
        emojis = list(self.st.get_emojis().keys())
        regex = re.compile('.*[0-9][-_][0-9].*')
        matches = list(filter(regex.match, emojis))
        return [x for x in emojis if x not in matches]

    def get_emojis_like(self, message: str, max_res: int = 500, **kwargs) -> str:
        """Gets emojis matching in the system that match a given regex pattern"""

        # Parse out the initial command
        match_pattern = kwargs.pop('match_pattern', None)
        if match_pattern is not None:
            ptrn = re.sub(match_pattern, '', message).strip()
        else:
            return 'Message didn\'t match expected syntax.'

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

    def _read_in_sheets(self):
        """Reads in GSheets for Viktor"""
        gs = GSheetReader(self.viktor_sheet)
        sheets = gs.sheets
        self.gs_dict = {}
        for sheet in sheets:
            self.gs_dict.update({
                sheet.title: gs.get_sheet(sheet.title)
            })

    def refresh_sheets(self, **kwargs) -> str:
        """Refreshes Viktor's Google Sheet"""
        self._read_in_sheets()
        return 'Sheets have been refreshed! `{}`'.format(','.join(self.gs_dict.keys()))

    @staticmethod
    def _grab_flag(msg_split: List[str], default_flag: str) -> Tuple[str, str]:
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
    def _build_flag_dict(col_list: List[str]) -> dict:
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
    def sarcastic_response() -> str:
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
    def giggle(**kwargs) -> str:
        """Laughs, uncontrollably at times"""
        # Count the 'no's
        laugh_cycles = randint(1, 500)
        response = f'ti{"hi" * laugh_cycles}!'
        return response

    @staticmethod
    def overly_polite(message: str, **kwargs) -> str:
        """Responds to 'no, thank you' with an extra 'no' """
        # Count the 'no's
        no_cnt = message.count('no')
        no_cnt += 1
        response = '{}, thank you!'.format(', '.join(['no'] * no_cnt)).capitalize()
        return response

    @staticmethod
    def access_something(**kwargs) -> str:
        """Return random number of ah-ah-ah emojis (Jurassic Park movie reference)"""
        return ''.join([':ah-ah-ah:'] * randint(5, 50))

    @staticmethod
    def get_time(**kwargs) -> str:
        """Gets the server time"""
        return f'The server time is `{dt.today():%F %T}`'

    @staticmethod
    def wfh_epoch(**kwargs) -> str:
        """Calculates WFH epoch time"""
        wfh_epoch = pd.datetime(year=2020, month=3, day=3, hour=19, minute=15)
        now = pd.datetime.now()
        diff = (now - wfh_epoch)

        return f'Current WFH epoch time is `{diff.total_seconds():.0f}`. \n ({diff}) '

    # Misc. methods
    # ====================================================
    def sh_response(self, **kwargs) -> str:
        """Responds to SHs"""
        resp_df = self.gs_dict['responses']
        responses = resp_df['responses_list'].unique().tolist()
        return responses[randint(0, len(responses) - 1)]

    def guess_acronym(self, message: str, **kwargs) -> str:
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

    def insult(self, message: str, **kwargs) -> str:
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

    def compliment(self, message: str, user: str, **kwargs) -> str:
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

    def inspirational(self, channel: str, **kwargs):
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

    def uwu_that(self, channel: str, ts: str, **kwargs) -> str:
        """Retrieves previous message and converts to UwU"""
        return self.uwu(self.st.get_prev_msg_in_channel(channel, ts))

    def uwu(self, msg: str, **kwargs) -> str:
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

    def quote_me(self, message: str, **kwargs) -> Optional[str]:
        """Converts message into letter emojis"""
        match_pattern = kwargs.pop('match_pattern', None)
        if match_pattern is not None:
            msg = re.sub(match_pattern, '', message).strip()
            return self.st.build_phrase(msg)
        return None

    # OKR Roles / Perks
    # ====================================================
    def onboarding_docs(self, **kwargs) -> List[dict]:
        """Returns links to everything needed to bring a new OKR employee up to speed"""
        docs = [
            self.bkb.make_block_section([
                "Welcome to OKR! We're glad to have you on board!\nCheck out these links below "
                "to get familiar with OKR and the industry we support!"
            ]),
            self.bkb.make_block_section([
                f"\t<Onboarding Doc|{self.onboarding_link}>\n\t<Viktor's GSheet|{self.viktor_sheet_link}>\n"
            ]),
            self.bkb.make_block_section([
                "For any questions, reach out to the CEO or our Head of Recruiting. "
                "Don't know who they are? Well, figure it out!"
            ])
        ]
        return docs

    def show_all_perks(self, **kwargs) -> str:
        """Displays all the perks"""
        perks_df = self.gs_dict['okr_perks']
        perks_df = perks_df.sort_values('level')
        perks = ''
        for level in perks_df['level'].unique().tolist():
            perk_list = '\n\t\t - '.join(perks_df.loc[perks_df['level'] == level, 'perk'].tolist())
            perks += f'`lvl {level}`: \n\t\t - {perk_list}\n'
        return f'*OKR perks*:\n{perks}'

    def show_my_perks(self, user: str, **kwargs) -> str:
        """Lists the perks granted at the user's current level"""
        # Get the user's level
        users_df = self.gs_dict['okr_roles'].copy()
        users_df = users_df[users_df['user'] == user]
        if not users_df.empty:
            level = users_df['level'].values[0]
            ltits = users_df['ltits'].values[0]
            perks_df = self.gs_dict['okr_perks'].copy()
            perks_df = perks_df[perks_df['level'] <= level]
            # Sort by perks level
            perks_df = perks_df.sort_values('level', ascending=True)
            perks = ''
            for i, row in perks_df.iterrows():
                perks += f'`lvl {row["level"]}`: {row["perk"]}\n'
            return f'WOW <@{user}>! You\'re at level `{level}`!!\n' \
                   f'You have access to the following _amazing_ perks:\n\n{perks}\n\n' \
                   f'...and don\'t forget you have `{ltits}` LTITs! That\'s something, too!'
        else:
            return 'User not found in OKR roles sheet :frowning:'

    def update_user_level(self, channel: str, user: str, message: str, **kwargs) -> Optional[str]:
        """Increment the user's level"""
        match_pattern = kwargs.pop('match_pattern', None)
        if match_pattern is not None:
            content = re.sub(match_pattern, '', message).strip()
        else:
            return None

        if user not in self.approved_users:
            return 'LOL sorry, levelups are CEO-approved only'

        if '-u' in content:
            # Updating role of other user
            # Extract user
            user = content.split()[1].replace('<@', '').replace('>', '').upper()
            if user == 'UPLAE3N67':
                # Some people should stay permanently at lvl 1
                return 'Hmm... that\'s weird. It says you can\'t be leveled up??'

            level_before = self.roles.loc[self.roles['user'] == user, 'level'].values[0]
            self.roles.loc[self.roles['user'] == user, 'level'] += 1

            self.st.send_message(channel, f'Level for <@{user}> updated to `{level_before + 1}`.')
            self.write_roles()
        else:
            return 'No user tagged for update.'

    def update_user_ltips(self, channel: str, user: str, message: str, **kwargs) -> Optional[str]:
        """Increment the user's level"""
        match_pattern = kwargs.pop('match_pattern', None)
        if match_pattern is not None:
            content = re.sub(match_pattern, '', message).strip()
        else:
            return None

        if user not in self.approved_users:
            return 'LOL sorry, LTIT distributions are CEO-approved only'

        if '-u' in content:
            # Updating role of other user
            # Extract user
            user = content.split()[1].replace('<@', '').replace('>', '').upper()
            points = content.split()[-1]
            if points.replace('-', '').replace('+', '').isnumeric():
                ltits = int(points.replace('-', '').replace('+', ''))
                ltits = ltits * -1 if '-' in points else ltits
                if not -1000 < ltits < 1000:
                    # Limit the number of ltits that can be distributed at any given time
                    ltits = 1000 if ltits > 1000 else -1000
                ltits_before = self.roles.loc[self.roles['user'] == user, 'ltits'].values[0]
                self.roles.loc[self.roles['user'] == user, 'ltits'] += ltits
                self.st.send_message(channel, f'LTITs for <@{user}> updated by `{ltits}` to `{ltits_before + ltits}`.')
                self.write_roles()
            else:
                return 'Please put points at the end. (+n, -n, n)'
        else:
            return 'No user tagged for update.'

    def collect_roleplayers(self) -> pd.DataFrame:
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

    def read_roles(self) -> pd.DataFrame:
        """Reads in JSON of roles"""
        return self.gs_dict['okr_roles']

    def write_roles(self, **kwargs):
        """Writes roles to GSheeets"""
        user_df = self.collect_roleplayers()
        self.roles = self.roles[['user', 'level', 'ltits', 'role']].merge(user_df, on='user', how='left')
        self.roles = self.roles[['user', 'name', 'level', 'ltits', 'role']]

        self.st.write_sheet(self.viktor_sheet, 'okr_roles', self.roles)

    def update_roles(self, user: str, channel: str, msg: str, **kwargs) -> Optional:
        """Updates a user with their role"""

        match_pattern = kwargs.pop('match_pattern', None)
        if match_pattern is not None:
            content = re.sub(match_pattern, '', msg).strip()
        else:
            return None

        if '-u' in content:
            # Updating role of other user
            # Extract user
            user = content.split()[1].replace('<@', '').replace('>', '').upper()
            content = ' '.join(content.split()[2:])
        self.roles.loc[self.roles['user'] == user, 'role'] = content
        self.st.send_message(channel, 'Role for <@{}> updated.'.format(user))

    def show_roles(self, user: str = None, **kwargs) -> List[str]:
        """Prints users roles to channel"""
        roles_output = []
        if user is None:
            # Printing roles for everyone
            roles_output += ['*OKR Roles (as of last reorg)*:', '=' * 10]
            # Iterate through roles, print them out
            for i, row in self.roles.iterrows():
                roles_output.append(f'`{row["name"]}`: Level `{row["level"]}` (`{row["ltits"]}` LTITs)\n'
                                    f'\t\t{row["role"]}')
        else:
            # Printing role for an individual user
            role_row = self.roles[self.roles['user'] == user]
            if not role_row.empty:
                for i, row in role_row.iterrows():
                    roles_output.append(f'`{row["name"]}`: Level `{row["level"]}` (`{row["ltits"]}` LTITs)\n'
                                        f'\t\t{row["role"]}')
            else:
                roles_output.append('No roles for you yet. Add them with the `update dooties` command.')

        return roles_output

    def build_role_txt(self, channel: str, user: str = None, **kwargs):
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
