import re
import requests
import string
from random import randint, choice
from typing import List, Optional, Dict, Union, Tuple, Type
import numpy as np
from slacktools import BlockKitBuilder as bkb
import viktor.app as vik_app
from .model import TableAcronyms, TablePhrases, TableCompliments, TableInsults, TableFacts, TableUwu, \
    TableResponses


TEXT_KEYS = ['text']


def recursive_uwu(key, val, replace_func):
    """Iterates through a nested dict, replaces text areas with uwu"""
    if isinstance(val, dict):
        items = val.items()
    elif isinstance(val, (list, tuple)):
        items = enumerate(val)
    else:
        if isinstance(key, str) and key in TEXT_KEYS:
            return replace_func(val)
        return val

    for k, v in items:
        val[k] = recursive_uwu(k, v, replace_func)
    return val


class PhraseBuilders:
    pronoun_direction = {
        'i': ['you', 'yourself', 'u', 'urself'],
        'you': ['me', 'myself'],
        'she': ['her', 'she'],
        'he': ['him', 'he'],
        'it': ['it'],
        'they': ['them', 'they']
    }

    @staticmethod
    def uwu(msg: str) -> str:
        """uwu-fy a message"""
        default_lvl = 2

        if '-l' in msg.split():
            level = msg.split()[msg.split().index('-l') + 1]
            level = int(level) if level.isnumeric() else default_lvl
            text = ' '.join(msg.split()[msg.split().index('-l') + 2:])
        else:
            level = default_lvl
            text = msg.replace('uwu', '').strip()

        chars = [x for x in vik_app.db.session.query(TableUwu.graphic).all()]

        if level >= 1:
            # Level 1: Letter replacement
            text = text.translate(str.maketrans('rRlL', 'wWwW'))

        if level >= 2:
            # Level 2: Placement of 'uwu' when certain patterns occur
            pattern_allowlist = {
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
                roll = randint(1, 10)
                if roll < 3 and len(word) > 0:
                    word = f'{word[0]}-{word}'
                for pattern, pattern_dict in pattern_allowlist.items():
                    if word.startswith(pattern_dict['start']):
                        word = word.replace(pattern_dict['start'], pattern)
                    else:
                        for fragment in pattern_dict['anywhere']:
                            if fragment in word:
                                word = word.replace(pattern_dict['start'], pattern)
                phrase.append(word)
            text = ' '.join(phrase)

            # Last step, insert random characters
            prefix_emoji = chars[np.random.choice(len(chars), 1)[0]].graphic
            suffix_emoji = chars[np.random.choice(len(chars), 1)[0]].graphic
            text = f'{prefix_emoji} {text} {suffix_emoji}'

        return text.replace('`', ' ')

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

    @classmethod
    def _get_target(cls, message: str, cmd_base: str) -> str:
        """Parses out the target of the command

        Examples:
            >>> cls._get_target("insult me -g standard", "insult")
            >>> "me"
            >>> cls._get_target("compliment that person on the street -g standard", "compliment")
            >>> "that person on the street"
        """
        return vik_app.Bot.st.parse_flags_from_command(message)['cmd'].replace(cmd_base, '').strip()

    @staticmethod
    def _get_set(tbl: Type[Union[TablePhrases, TableCompliments, TableInsults]], grp: str) -> \
            Union[str, List[Union[TablePhrases, TableCompliments, TableInsults]]]:
        """Retrieve the set from the given table. If not found, return a list of available sets"""
        words = vik_app.db.session.query(tbl).filter(tbl.type == grp).all()
        if len(words) == 0:
            all_groups = vik_app.db.session.query(tbl).group_by(tbl.type).all()
            available_sets = [x.type.name for x in all_groups]
            return f'Cannot find set `{grp}` in the table. Available sets: `{"`, `".join(available_sets)}`'
        return words

    @classmethod
    def _message_extractor(cls, message, cmd: str, default_group: str) -> Tuple[str, int, Optional[str]]:
        """extracts valuable info from message"""
        # Parse the group of phrases the user wants to work with
        phrase_group = vik_app.Bot.st.get_flag_from_command(message, flags=['group', 'g'], default=default_group)
        # Number of times to cycle through phrase generation
        n_times = vik_app.Bot.st.get_flag_from_command(message, flags=['n'], default='1')
        n_times = int(n_times) if n_times.isnumeric() else 1
        # Capture a possible target (not always used though)
        target = cls._get_target(message, cmd)
        return phrase_group, n_times, target

    @classmethod
    def sh_response(cls) -> str:
        responses = cls._get_set(TableResponses, grp='stakeholder')
        return choice(responses).text

    @classmethod
    def jackhandey(cls) -> str:
        responses = cls._get_set(TableResponses, grp='jackhandey')
        return choice(responses).text

    @classmethod
    def guess_acronym(cls, message: str) -> str:
        """Tries to guess an acronym from a message"""
        message_split = message.split()
        if len(message_split) <= 1:
            return "I can't work like this! I need a real acronym!!:ragetype:"
        # We can work with this
        acronym = message_split[1]
        # clean of any punctuation (or non-letters)
        acronym = re.sub(r'\W', '', acronym)

        # Parse the group of acronyms the user wants to work with
        acronym_group = vik_app.Bot.st.get_flag_from_command(message, flags=['group', 'g'], default='standard')
        # Number of guesses to make
        n_times = vik_app.Bot.st.get_flag_from_command(message, flags=['n'], default='3')
        n_times = int(n_times) if n_times.isnumeric() else 3
        # Select the acronym list to use, verify that we have some words in that group
        acronyms = cls._get_set(TableAcronyms, acronym_group)
        if isinstance(acronyms, str):
            # Unable to find group
            return acronyms

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

    @classmethod
    def insult(cls, message: str) -> str:
        """Insults the user at their request"""
        message_split = message.split()
        if len(message_split) <= 1:
            return "I can't work like this! I need something to insult!!:ragetype:"
        if all([x in message.lower() for x in ['me', 'hard']]):
            # Generate better insult
            return cls.get_evil_insult()
        # Extract commands and other info from the message
        grp, n_times, target = cls._message_extractor(message=message, cmd='insult', default_group='standard')
        # Extract all related words from db
        words = cls._get_set(TableInsults, grp)
        if isinstance(words, str):
            # Unable to find group
            return words
        # Organize the words by stage
        # Build a dictionary of the query results, organized by stage
        word_dict = cls._word_result_organiser(word_results=words)
        # Use the word dict to randomly select words from each stage
        word_lists = []  # type: List[List[str]]
        for i in range(n_times):
            word_lists.append(cls._phrase_builder(word_dict=word_dict))
        # Build the phrases
        if target in sum(cls.pronoun_direction.values(), []):
            # Using pronouns. Try to be smart about this!
            pronoun = next(iter([k for k, v in cls.pronoun_direction.items() if target in v]))
            p_txt = f"{pronoun.title()} aint nothin but a {' and a '.join([' '.join(x) for x in word_lists])}."
        else:
            p_txt = f"{target.title()} aint nothin but a {' and a '.join([' '.join(x) for x in word_lists])}."
        return re.sub(r'(?<=[\w:.,!?()]) (?=[:.,!?()])', '', p_txt)

    @classmethod
    def phrase_generator(cls, message: str) -> str:
        """Generates a phrase based on a table of work fragments"""
        # Extract commands and other info from the message
        grp, n_times, target = cls._message_extractor(message=message, cmd='phrase', default_group='standard')
        # Extract all related words from db
        words = cls._get_set(TablePhrases, grp)
        if isinstance(words, str):
            # Unable to find group
            return words
        # Organize the words by stage
        # Build a dictionary of the query results, organized by stage
        word_dict = cls._word_result_organiser(word_results=words)
        # Use the word dict to randomly select words from each stage
        word_lists = []     # type: List[List[str]]
        for i in range(n_times):
            word_lists.append(cls._phrase_builder(word_dict=word_dict))
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

    @classmethod
    def compliment(cls, message: str, user: str) -> str:
        """Compliments the user at their request"""
        message_split = message.split()
        if len(message_split) <= 1:
            return "I can't work like this! I need something to compliment!!:ragetype:"

        # Extract commands and other info from the message
        grp, n_times, target = cls._message_extractor(message=message, cmd='compliment', default_group='standard')
        # Extract all related words from db
        words = cls._get_set(TableCompliments, grp)
        if isinstance(words, str):
            # Unable to find group
            return words
        # Organize the words by stage
        # Build a dictionary of the query results, organized by stage
        word_dict = cls._word_result_organiser(word_results=words)
        # Use the word dict to randomly select words from each stage
        word_lists = []  # type: List[List[str]]
        for i in range(n_times):
            word_lists.append(cls._phrase_builder(word_dict=word_dict))
        # Build the phrases
        if target in sum(cls.pronoun_direction.values(), []):
            # Maybe we'll circle back here later and use a smarter way of dealing with pronouns
            phrase_txt = f"Dear Asshole, {' and '.join([' '.join(x) for x in word_lists])} Viktor."
        else:
            phrase_txt = f"Dear {target.title()}, {' and '.join([' '.join(x) for x in word_lists])} <@{user}>"
        return re.sub(r'(?<=[\w:.,!?()]) (?=[:.,!?()])', '', phrase_txt)

    @staticmethod
    def get_evil_insult() -> Optional[str]:
        resp = requests.get('https://evilinsult.com/generate_insult.php?lang=en&type=json')
        if resp.status_code == 200:
            return resp.json().get('insult')

    @classmethod
    def facts(cls, grp: str = 'standard') -> Union[str, List[Dict]]:
        """Gives the user a random fact at their request"""
        # Extract all related words from db
        facts = cls._get_set(TableFacts, grp)
        if isinstance(facts, str):
            # Unable to find group
            return facts
        # Select random fact
        randfact = choice(facts)
        rf_id = facts.index(randfact) + 1

        fact_header = f'{"Official" if grp == "standard" else "Conspiracy"} fact #{rf_id}'

        return [
            bkb.make_header(fact_header),
            bkb.make_block_section(randfact.text)
        ]

    @staticmethod
    def affirmation() -> str:
        resp = requests.get('https://www.affirmations.dev/')
        if resp.status_code == 200:
            # Get an uwu graphic
            uwu_list = [x for x in vik_app.db.session.query(TableUwu.graphic).all()]
            header = choice(uwu_list)
            footer = choice(uwu_list)
            aff_txt = resp.json().get('affirmation')
            return f'{header} {aff_txt} {footer}'

    @staticmethod
    def dadjoke():
        resp = requests.get('https://icanhazdadjoke.com/',  headers={'Accept': 'application/json'})
        if resp.status_code == 200:
            result = resp.json()
            jid = result.get("id")
            url = f'https://icanhazdadjoke.com/j/{jid}'
            return [
                bkb.make_context_section([bkb.markdown_section(f'Dadjoke `{jid}`')]),
                bkb.make_block_section(f'{result.get("joke")}')
            ]
