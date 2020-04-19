import re
import string
import pandas as pd
import numpy as np
from random import randint
from typing import List, Optional
from slacktools import SlackBotBase


class PhraseBuilders:
    def __init__(self, slacktool_obj: SlackBotBase):
        self.st = slacktool_obj

    @staticmethod
    def _check_group(group_name: str, group_dict: dict, sheet_name: str) -> Optional[str]:
        """Makes sure that the particular group desired exists"""
        if group_name not in group_dict.keys():
            return f'Cannot find set `{group_name}` in the `{sheet_name}` sheet. ' \
                   f'Available sets: `{"`, `".join(group_dict.keys())}`'
        return None

    @staticmethod
    def _build_group_dict(col_list: List[str]) -> dict:
        """Builds a dictionary of the columns grouped together by prefix in the column name"""
        # Parse the columns into flags and order
        group_dict = {}
        for col in col_list:
            if '_' in col:
                k, v = col.split('_')
                if k in group_dict.keys():
                    group_dict[k].append(col)
                else:
                    group_dict[k] = [col]
            else:
                group_dict[col] = [col]
        return group_dict

    @staticmethod
    def _phrase_builder(df: pd.DataFrame, phrase_cols: List[str]) -> List[str]:
        """Randomly assembles phrases together from a collection of columns in a dataframe"""
        phrase_list = []
        for phrase_part in sorted(phrase_cols):
            part = df[phrase_part].replace('', np.NaN).dropna().unique().tolist()
            if len(part) > 1:
                # Choose part from multiple parts
                txt = part[randint(0, len(part) - 1)]
            else:
                txt = part[0]
            phrase_list.append(txt.strip())
        return phrase_list

    def _get_target(self, message: str, cmd_base: str) -> str:
        """Parses out the target of the command

        Examples:
            >>> self._get_target("insult me -g standard", "insult")
            >>> "me"
            >>> self._get_target("compliment that person on the street -g standard", "compliment")
            >>> "that person on the street"
        """
        return self.st.parse_flags_from_command(message)['cmd'].replace(cmd_base, '').strip()

    def guess_acronym(self, acro_df: pd.DataFrame, message: str) -> str:
        """Tries to guess an acronym from a message"""
        message_split = message.split()
        if len(message_split) <= 1:
            return "I can't work like this! I need a real acronym!!:ragetype:"
        # We can work with this
        acronym = message_split[1]
        # clean of any punctuation (or non-letters)
        acronym = re.sub(r'\W', '', acronym)

        # Parse the group of acronyms the user wants to work with
        acronym_group = self.st.get_flag_from_command(message, flags=['group', 'g'], default='standard')
        # Number of guessed to make
        n_times = self.st.get_flag_from_command(message, flags=['n'], default='3')
        n_times = int(n_times) if n_times.isnumeric() else 3
        # Choose the acronym list to use
        cols = acro_df.columns.tolist()
        # Read in a dictionary of all the columns of that dataframe, organized by column prefix (phrase_group)
        phrase_group_dict = self._build_group_dict(cols)

        # Confirm that the user's desired group exists in the dict
        group_confirm = self._check_group(acronym_group, phrase_group_dict, 'acronyms')
        if group_confirm is not None:
            # Doesn't exist; notify user
            return group_confirm

        words = acro_df.loc[~acro_df[acronym_group].isnull(), acronym_group].unique().tolist()

        # Put the words into a dictionary, classified by first letter
        a2z = string.ascii_lowercase
        word_dict = {k: [] for k in a2z}
        for word in words:
            word = word.replace('\n', '')
            if len(word) > 1:
                word_dict[word[0].lower()].append(word.lower())

        # Build out the real acryonym meaning
        guesses = []
        for guess in range(n_times):
            meaning = []
            for letter in list(acronym):
                if letter.isalpha():
                    word_list = word_dict[letter]
                    meaning.append(word_list[randint(0, len(word_list) - 1)])
                else:
                    meaning.append(letter)
            guesses.append(' '.join(list(map(str.title, meaning))))

        guess_chunk = "\n_OR_\n".join(guesses)
        return f':robot-face: Here are my guesses for *`{acronym.upper()}`*!\n {guess_chunk}'

    def _phrase_action_handler(self, df: pd.DataFrame, cmd_base: str, message: str, sheet_name: str,
                               default_phrase_group: str, user: str = None) -> str:
        """Wrapper method for unifying the different types of phrase builders we have

        Args:
            cmd_base(str): The type of command we're working with (e.g., 'insult', 'compliment')
            message(str): The command in its entirety
            sheet_name(str): The name of the sheet in the spreadsheet we'll be examining
            default_phrase_group(str): The phrase group to default to.
            user(str): The user to tag (currently used in compliments only)
        """
        # Parse the group of phrases the user wants to work with
        phrase_group = self.st.get_flag_from_command(message, flags=['group', 'g'], default=default_phrase_group)
        # Number of times to cycle through phrase generation
        n_times = self.st.get_flag_from_command(message, flags=['n'], default='1')
        n_times = int(n_times) if n_times.isnumeric() else 1
        # Capture a possible target (not always used though)
        target = self._get_target(message, cmd_base)

        # Read in the dataframe we'll work with
        cols = df.columns.tolist()
        # Read in a dictionary of all the columns of that dataframe, organized by column prefix (phrase_group)
        phrase_group_dict = self._build_group_dict(cols)

        # Confirm that the user's desired group exists in the dict
        group_confirm = self._check_group(phrase_group, phrase_group_dict, sheet_name)
        if group_confirm is not None:
            # Doesn't exist; notify user
            return group_confirm

        phrase_cols = phrase_group_dict[phrase_group]
        phrases = []
        for i in range(n_times):
            if i == n_times - 1 and any(['joiner' in x for x in phrase_cols]):
                # Last iteration. Remove the joiner and add a period
                phrases += self._phrase_builder(df, phrase_cols)[:-1]
            else:
                phrases += self._phrase_builder(df, phrase_cols)

        # This will help if our target is a pronoun
        pronoun_direction = {
            'i': ['you', 'yourself', 'u', 'urself'],
            'you': ['me', 'myself'],
            'she': ['her', 'she'],
            'he': ['him', 'he'],
            'it': ['it'],
            'they': ['them', 'they']
        }

        if cmd_base == 'phrase':
            # Southern / C BS phrase gen
            phrase_txt = '. '.join([x.strip().capitalize() for x in f'{" ".join(phrases)}'.split('.')])
        elif cmd_base == 'insult':
            if target in sum(pronoun_direction.values(), []):
                # Using pronouns. Try to be smart about this!
                pronoun = next(iter([k for k, v in pronoun_direction.items() if target in v]))
                phrase_txt = f"{pronoun.title()} aint nothin but a {' '.join(phrases)}."
            else:
                phrase_txt = "{} aint nothin but a {}".format(target, ' '.join(phrases))
        elif cmd_base == 'compliment':
            if target in sum(pronoun_direction.values(), []):
                # Maybe we'll circle back here later and use a smarter way of dealing with pronouns
                phrase_txt = f"Dear Asshole, {' '.join(phrases)} Viktor."
            else:
                phrase_txt = f"Dear {target.title()}, {' '.join(phrases)} <@{user}>"
        else:
            phrase_txt = 'lol idk I couldn\'t make out your command :shrugman::shrugman2:'
        # Before returning, remove any spaces between words and punctutation (and between punctuation itself)
        return re.sub(r'(?<=[\w:.,!?()]) (?=[:.,!?()])', '', phrase_txt)

    def insult(self, df: pd.DataFrame, message: str) -> str:
        """Insults the user at their request"""
        message_split = message.split()
        if len(message_split) <= 1:
            return "I can't work like this! I need something to insult!!:ragetype:"

        resp = self._phrase_action_handler(df, message_split[0], message, 'insults', 'standard')
        return resp

    def phrase_generator(self, df: pd.DataFrame, message: str) -> str:
        """Generates a phrase based on a table of work fragments"""
        message_split = message.split()
        resp = self._phrase_action_handler(df, message_split[0], message, 'phrases', 'south')
        return f'{resp}'

    def compliment(self, df: pd.DataFrame, message: str, user: str) -> str:
        """Insults the user at their request"""
        message_split = message.split()
        if len(message_split) <= 1:
            return "I can't work like this! I need something to compliment!!:ragetype:"

        resp = self._phrase_action_handler(df, message_split[0], message, 'compliments', 'std', user)
        return resp
