import re
import requests
import string
from random import randint
from typing import (
    List,
    Optional,
    Dict,
    Union,
    Tuple
)
from sqlalchemy.sql import (
    func,
    and_
)
from slacktools import BlockKitBuilder as bkb
import viktor.app as vik_app
from viktor.model import (
    AcronymType,
    ResponseCategory,
    ResponseType,
    TableAcronym,
    TableResponse,
    TableUwu
)


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

        with vik_app.eng.session_mgr() as session:
            # Randomly select 2 graphics
            chars = [x.graphic for x in session.query(TableUwu.graphic).order_by(func.random()).limit(2).all()]
            prefix, suffix = chars

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
            text = f'{prefix} {text} {suffix}'

        return text.replace('`', ' ')

    @staticmethod
    def _word_result_organiser(word_results: List[TableResponse]) -> \
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

    @staticmethod
    def _get_random_response(resp_type: ResponseType, category: ResponseCategory) -> str:
        """Retrieves a random response from the provided type/category combo. If no combo exists,
            will instead return a string saying that the pairing was not found"""
        with vik_app.eng.session_mgr() as session:
            resp = session.query(TableResponse.text).filter(and_(
                TableResponse.type == resp_type,
                TableResponse.category == category
            )).order_by(func.random()).limit(1).one_or_none()
            if resp is None:
                return f'Cannot find combo in table: {resp_type.name} + {category.name}'
            return resp.text

    @classmethod
    def sh_response(cls) -> str:
        return cls._get_random_response(ResponseType.GENERAL, category=ResponseCategory.STAKEHOLDER)

    @classmethod
    def jackhandey(cls) -> str:
        return cls._get_random_response(ResponseType.GENERAL, category=ResponseCategory.JACKHANDEY)

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
        acronym_group_str = vik_app.Bot.st.get_flag_from_command(message, flags=['group', 'g'], default='standard')
        acronym_group = getattr(AcronymType, acronym_group_str.upper(), AcronymType.STANDARD)
        # Number of guesses to make
        n_times = vik_app.Bot.st.get_flag_from_command(message, flags=['n'], default='3')
        n_times = int(n_times) if n_times.isnumeric() else 3
        # Select the acronym list to use, verify that we have some words in that group
        with vik_app.eng.session_mgr() as session:
            words = [x.text for x in session.query(TableAcronym).filter(TableAcronym.type == acronym_group).all()]

        if len(words) == 0:
            return f'Unable to find an acronym group for {acronym_group_str}'

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
    def _process_cmd_and_generate_response(cls, cmd: str, message: str, user: str = None) -> str:
        """Handles processing the insult, compliement, phrase command and generating an appropriate response"""
        # Extract commands and other info from the message
        category_str, n_times, target = cls._message_extractor(message=message, cmd=cmd, default_group='standard')
        # Attempt to find the
        category = getattr(ResponseCategory, category_str.upper(), ResponseCategory.STANDARD)
        # Extract all related words from db
        with vik_app.eng.session_mgr() as session:
            words = session.query(TableResponse).filter(and_(
                TableResponse.type == ResponseType[cmd.upper()],
                TableResponse.category == category
            )).all()
            session.expunge_all()

        if len(words) == 0:
            return f'Unable to find a(n) {cmd} group for {category_str}'
        # Organize the words by stage
        # Build a dictionary of the query results, organized by stage
        word_dict = cls._word_result_organiser(word_results=words)
        # Use the word dict to randomly select words from each stage
        word_lists = []  # type: List[List[str]]
        for i in range(n_times):
            word_lists.append(cls._phrase_builder(word_dict=word_dict))
        # Build the phrases
        if cmd == 'insult':
            if target in sum(cls.pronoun_direction.values(), []):
                # Using pronouns. Try to be smart about this!
                target = next(iter([k for k, v in cls.pronoun_direction.items() if target in v]))
            txt = f"{target.title()} aint nothin but a {' and a '.join([' '.join(x) for x in word_lists])}."
        elif cmd == 'phrase':
            if category == ResponseCategory.STANDARD:
                processed = []
                for phrs in word_lists:
                    article = 'an' if phrs[-1] in 'aeiou' else 'a'
                    processed.append('Well {1} my {2} and {3} {0} {4}.'.format(article, *phrs))
            else:
                processed = [' '.join(x) for x in word_lists]
            txt = '. '.join([x.strip().capitalize() for x in f'{" ".join(processed)}'.split('.')])
        elif cmd == 'compliment':
            if target in sum(cls.pronoun_direction.values(), []):
                # Maybe we'll circle back here later and use a smarter way of dealing with pronouns
                txt = f"Dear Asshole, {' and '.join([' '.join(x) for x in word_lists])} Viktor."
            else:
                txt = f"Dear {target.title()},\n\t {' and '.join([' '.join(x) for x in word_lists])} <@{user}>"
        else:
            txt = 'boop......booop.........................boooooooooop    :party-dead:'
        return re.sub(r'(?<=[\w:.,!?()]) (?=[:.,!?()])', '', txt)

    @classmethod
    def insult(cls, message: str) -> str:
        """Insults the user at their request"""
        message_split = message.split()
        if len(message_split) <= 1:
            return "I can't work like this! I need something to insult!!:ragetype:"
        if all([x in message.lower() for x in ['me', 'hard']]):
            # Generate better insult
            return cls.get_evil_insult()

        return cls._process_cmd_and_generate_response(cmd='insult', message=message)

    @classmethod
    def phrase_generator(cls, message: str) -> str:
        """Generates a phrase based on a table of work fragments"""
        return cls._process_cmd_and_generate_response(cmd='phrase', message=message)

    @classmethod
    def compliment(cls, message: str, user: str) -> str:
        """Compliments the user at their request"""
        message_split = message.split()
        if len(message_split) <= 1:
            return "I can't work like this! I need a target to compliment!!:ragetype:"

        return cls._process_cmd_and_generate_response(cmd='compliment', message=message, user=user)

    @staticmethod
    def get_evil_insult() -> Optional[str]:
        resp = requests.get('https://evilinsult.com/generate_insult.php?lang=en&type=json')
        if resp.status_code == 200:
            return resp.json().get('insult')

    @classmethod
    def facts(cls, category: ResponseCategory = ResponseCategory.STANDARD) -> Union[str, List[Dict]]:
        """Gives the user a random fact at their request"""
        # Extract all related words from db
        with vik_app.eng.session_mgr() as session:
            randfact = session.query(TableResponse).filter(and_(
                TableResponse.type == ResponseType.FACT,
                TableResponse.category == category
            )).order_by(func.random()).limit(1).one_or_none()
            if randfact is None:
                return 'Couldn\'t find a fact for that category?'
            session.expunge(randfact)

        rf_id = randfact.response_id

        fact_header = f'{"Official" if category == ResponseCategory.STANDARD else "Conspiracy"} fact #{rf_id}'

        return [
            bkb.make_header(fact_header),
            bkb.make_block_section(randfact.text)
        ]

    @staticmethod
    def affirmation() -> str:
        resp = requests.get('https://www.affirmations.dev/')
        if resp.status_code == 200:
            # Get an uwu graphic
            with vik_app.eng.session_mgr() as session:
                header, footer = [x.graphic for x in session.query(TableUwu.graphic)
                                  .order_by(func.random()).limit(2).all()]
            aff_txt = resp.json().get('affirmation')
            return f'{header} {aff_txt} {footer}'

    @staticmethod
    def dadjoke():
        resp = requests.get('https://icanhazdadjoke.com/',  headers={'Accept': 'application/json'})
        if resp.status_code == 200:
            result = resp.json()
            return result.get("joke")
