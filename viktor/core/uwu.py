import random
import re
from typing import Tuple

from sqlalchemy.sql import func

from viktor.db_eng import ViktorPSQLClient
from viktor.model import TableUwu

TEXT_KEYS = ['text', 'fallback', 'pretext', 'title', 'footer']


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


class UWU:

    STUTTER = 0.05              # Chance of stutter per word
    OWO_REPEATER = 0.05         # Chance of owo repeating per word

    char_cluster_map = {
        r'th(?=\w+)': 'd',          # that -> dat, math !-> mad
        r'as$': 'az',               # has -> haz, asymmetrical !-> azymmetrical
        r'ck': 'k',                 # back -> bak,
        r'ove$': 'uv',              # love -> luv, over !-> uvr
        r'n(?=[aeiou]\w+)': 'ny'    # none -> nyone,
    }

    word_map = {
        'is': 'iz',
        # 'has': 'haz',
        'says': 'sez',
        'said': 'sed',
        'the': 'da',
    }

    repeater_map = {
        'uwu': ['nu', 'ou', 'du', 'un', 'bu'],
        'owo': ['ow', 'bo', 'do', 'on']
    }

    def __init__(self, eng: ViktorPSQLClient):
        self.eng = eng

    def get_prefix_and_suffix(self) -> Tuple[str, str]:
        with self.eng.session_mgr() as session:
            chars = [x.graphic for x in session.query(TableUwu.graphic).order_by(func.random()).limit(2).all()]
            prefix, suffix = [x.replace('`', ' ') for x in chars]
            return prefix, suffix

    @classmethod
    def match_word_and_preserve_case(cls, word: str) -> str:
        lower_word = word.lower()
        if lower_word in cls.word_map.keys():
            new_lower_word = cls.word_map[lower_word]

            # Determine case
            if word.islower():
                return new_lower_word
            elif word.istitle():
                return new_lower_word.title()
            elif word.isupper():
                return new_lower_word.upper()
            # Otherwise just return lowercased
            return new_lower_word
        return word

    def convert_to_uwu(self, message: str) -> str:
        # Remove command, if any
        converted = re.sub(r'^[Uu][Ww][Uu]', '', message).strip()

        # split message into words now
        conv_splits = converted.split(' ')
        words = []
        for word in conv_splits:
            if word.startswith('<') or word.startswith('&lt;') or word.endswith('>'):
                # Bypass link gen
                if '|' in word:
                    link_split = word.split('|')
                    link_name = link_split[1]
                    link_name = link_name.translate(str.maketrans('rRlL', 'wWwW'))
                    word = '|'.join([link_split[0], link_name])
                words.append(word)
                continue
            word = word.translate(str.maketrans('rRlL', 'wWwW'))

            # Convert known words
            word = self.match_word_and_preserve_case(word)

            # Convert character clusters
            for pattern, replacement in self.char_cluster_map.items():
                word = re.sub(pattern=pattern, repl=replacement, string=word)

            # Stutter
            if len(word) > 1 and re.match(r'\w', word[0]) and random.random() <= self.STUTTER:
                for i in range(random.randint(1, 4)):
                    word = f'{word[0]}-{word}'

            # OWO Repeater
            if len(word) > 4 and random.random() <= self.OWO_REPEATER:
                for uwu_type, repeat_list in self.repeater_map.items():
                    for frag in repeat_list:
                        if frag in word:
                            word = word.replace(uwu_type[0], uwu_type)

            words.append(word)
        converted = ' '.join(words)

        # Select extra feats (prefix/suffix/commentary)
        prefix, suffix = self.get_prefix_and_suffix()

        return f'{prefix} {converted} {suffix}'
