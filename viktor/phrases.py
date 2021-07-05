import re
import string
from random import randint
from typing import List, Optional, Dict, Union, Tuple
from sqlalchemy.orm import Session
from slacktools import SlackBotBase
from .model import TableAcronyms, TablePhrases, TableCompliments, TableInsults


class PhraseBuilders:
    pronoun_direction = {
        'i': ['you', 'yourself', 'u', 'urself'],
        'you': ['me', 'myself'],
        'she': ['her', 'she'],
        'he': ['him', 'he'],
        'it': ['it'],
        'they': ['them', 'they']
    }

    def __init__(self, slacktool_obj: SlackBotBase):
        self.st = slacktool_obj

    @staticmethod
    def _word_result_organiser(word_results: List[Union[TablePhrases, TableCompliments, TableInsults]]) -> \
            Dict[int, List[str]]:
        """Iterates over the list of word results and organizes the words by 'stage' column"""
        words_organised = {}
        for word in word_results:
            if word.stage in words_organised.keys():
                words_organised[word.stage].append(word.text)
            else:
                words_organised[word.stage] = [word.text]
        return words_organised

    @staticmethod
    def _phrase_builder(word_dict: Dict[int, List[str]]) -> List[str]:
        """Randomly assembles phrases together from a collection of columns in a dataframe"""
        phrase_list = []
        for k, v in word_dict.items():
            if len(v) > 1:
                txt = v[randint(0, len(v) - 1)]
            else:
                txt = v[0]
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

    def guess_acronym(self, message: str, session: Session) -> str:
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
        # Number of guesses to make
        n_times = self.st.get_flag_from_command(message, flags=['n'], default='3')
        n_times = int(n_times) if n_times.isnumeric() else 3
        # Select the acronym list to use, verify that we have some words in that group
        acronyms = session.query(TableAcronyms).filter(TableAcronyms.type == acronym_group).all()
        if len(acronyms) == 0:
            # No such type. Inform user about proper types
            available_sets = [
                x.type.name for x in session.query(TableAcronyms.type).group_by(TableAcronyms.type).all()]
            return f'Cannot find set `{acronym_group}` in the table. ' \
                   f'Available sets: `{"`, `".join(available_sets)}`'

        words = [x.text for x in acronyms]

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

    def _message_extractor(self, message, cmd: str, default_group: str) -> Tuple[str, int, Optional[str]]:
        """extracts valuable info from message"""
        # Parse the group of phrases the user wants to work with
        phrase_group = self.st.get_flag_from_command(message, flags=['group', 'g'], default=default_group)
        # Number of times to cycle through phrase generation
        n_times = self.st.get_flag_from_command(message, flags=['n'], default='1')
        n_times = int(n_times) if n_times.isnumeric() else 1
        # Capture a possible target (not always used though)
        target = self._get_target(message, cmd)
        return phrase_group, n_times, target

    def insult(self, message: str, session: Session) -> str:
        """Insults the user at their request"""
        message_split = message.split()
        if len(message_split) <= 1:
            return "I can't work like this! I need something to insult!!:ragetype:"
        # Extract commands and other info from the message
        grp, n_times, target = self._message_extractor(message=message, cmd='insult', default_group='standard')
        # Extract all related words from db
        words = session.query(TableInsults).filter(TableInsults.type == grp).all()
        if len(words) == 0:
            # No such type. Inform user about proper types
            available_sets = [
                x.type.name for x in session.query(TableInsults.type).group_by(TableInsults.type).all()]
            return f'Cannot find set `{grp}` in the table. ' \
                   f'Available sets: `{"`, `".join(available_sets)}`'
        # Organize the words by stage
        # Build a dictionary of the query results, organized by stage
        word_dict = self._word_result_organiser(word_results=words)
        # Use the word dict to randomly select words from each stage
        word_lists = []  # type: List[List[str]]
        for i in range(n_times):
            word_lists.append(self._phrase_builder(word_dict=word_dict))
        # Build the phrases
        if target in sum(self.pronoun_direction.values(), []):
            # Using pronouns. Try to be smart about this!
            pronoun = next(iter([k for k, v in self.pronoun_direction.items() if target in v]))
            p_txt = f"{pronoun.title()} aint nothin but a {' and a '.join([' '.join(x) for x in word_lists])}."
        else:
            p_txt = f"{target.title()} aint nothin but a {' and a '.join([' '.join(x) for x in word_lists])}."
        return re.sub(r'(?<=[\w:.,!?()]) (?=[:.,!?()])', '', p_txt)

    def phrase_generator(self, message: str, session: Session) -> str:
        """Generates a phrase based on a table of work fragments"""
        # Extract commands and other info from the message
        grp, n_times, target = self._message_extractor(message=message, cmd='phrase', default_group='standard')
        # Extract all related words from db
        words = session.query(TablePhrases).filter(TablePhrases.type == grp).all()
        if len(words) == 0:
            # No such type. Inform user about proper types
            available_sets = [
                x.type.name for x in session.query(TablePhrases.type).group_by(TablePhrases.type).all()]
            return f'Cannot find set `{grp}` in the table. ' \
                   f'Available sets: `{"`, `".join(available_sets)}`'
        # Organize the words by stage
        # Build a dictionary of the query results, organized by stage
        word_dict = self._word_result_organiser(word_results=words)
        # Use the word dict to randomly select words from each stage
        word_lists = []     # type: List[List[str]]
        for i in range(n_times):
            word_lists.append(self._phrase_builder(word_dict=word_dict))
        # Build the phrases
        if grp == 'standard':
            processed = []
            for phrs in word_lists:
                article = 'an' if phrs[-1] in 'aeiou' else 'a'
                processed.append('Well {1} my {2} and {3} {0} {4}.'.format(article, *phrs))
        else:
            processed = [' '.join(x) for x in word_lists]
        phrase_txt = '. '.join([x.strip().capitalize() for x in f'{" ".join(processed)}'.split('.')])
        return re.sub(r'(?<=[\w:.,!?()]) (?=[:.,!?()])', '', phrase_txt)

    def compliment(self, message: str, user: str, session: Session) -> str:
        """Insults the user at their request"""
        message_split = message.split()
        if len(message_split) <= 1:
            return "I can't work like this! I need something to compliment!!:ragetype:"

        # Extract commands and other info from the message
        grp, n_times, target = self._message_extractor(message=message, cmd='compliment', default_group='standard')
        # Extract all related words from db
        words = session.query(TableCompliments).filter(TableCompliments.type == grp).all()
        if len(words) == 0:
            # No such type. Inform user about proper types
            available_sets = [
                x.type.name for x in session.query(TableCompliments.type).group_by(TableCompliments.type).all()]
            return f'Cannot find set `{grp}` in the table. ' \
                   f'Available sets: `{"`, `".join(available_sets)}`'
        # Organize the words by stage
        # Build a dictionary of the query results, organized by stage
        word_dict = self._word_result_organiser(word_results=words)
        # Use the word dict to randomly select words from each stage
        word_lists = []  # type: List[List[str]]
        for i in range(n_times):
            word_lists.append(self._phrase_builder(word_dict=word_dict))
        # Build the phrases
        if target in sum(self.pronoun_direction.values(), []):
            # Maybe we'll circle back here later and use a smarter way of dealing with pronouns
            phrase_txt = f"Dear Asshole, {' and '.join([' '.join(x) for x in word_lists])} Viktor."
        else:
            phrase_txt = f"Dear {target.title()}, {' and '.join([' '.join(x) for x in word_lists])} <@{user}>"
        return re.sub(r'(?<=[\w:.,!?()]) (?=[:.,!?()])', '', phrase_txt)
