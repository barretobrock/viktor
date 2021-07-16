#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
import requests
import numpy as np
import urllib.parse as parse
from typing import Optional
from io import StringIO
from lxml import etree


class Linguistics:
    """Language methods"""

    # URLs
    ETY_SEARCH = 'https://www.etymonline.com/search'
    EKI_BASE = 'https://www.eki.ee/dict'
    EKI_IES = f'{EKI_BASE}/ies/index.cgi'
    EKI_EKSS = f'{EKI_BASE}/ekss/index.cgi'
    FIL_BASE = 'https://www.filosoft.ee'

    @staticmethod
    def _prep_for_xpath(url: str) -> etree.ElementBase:
        """Takes in a url and returns a tree that can be searched using xpath"""
        page = requests.get(url)
        html = page.content.decode('utf-8')
        parser = etree.HTMLParser()
        tree = etree.parse(StringIO(html), parser=parser)
        return tree

    @classmethod
    def get_etymology(cls, message: str, pattern: str):
        """Grabs the etymology of a word from Etymonline"""

        def get_definition_name(res: etree.ElementBase) -> str:
            item_str = ''
            for elem in res.xpath('object/a'):
                for x in elem.iter():
                    for item in [x.text, x.tail]:
                        if item is not None:
                            if item.strip() != '':
                                item_str += f' {item}'
            return item_str.strip()

        word = re.sub(pattern, '', message).strip()

        url = f'{cls.ETY_SEARCH}?q={parse.quote(word)}'
        content = cls._prep_for_xpath(url)
        results = content.xpath('//div[contains(@class, "word--C9UPa")]')
        output = ':word:\n'
        if len(results) > 0:
            for result in results:
                name = get_definition_name(result)
                if word in name:
                    desc = ' '.join([x for elem in result.xpath('object/section') for x in elem.itertext()])
                    desc = ' '.join([f'_{x}_' for x in desc.split('\n') if x.strip() != ''])
                    output += f'*`{name}`*:\n{desc}\n'

        if output != '':
            return output
        else:
            return f'No etymological data found for `{word}`.'

    @classmethod
    def prep_message_for_translation(cls, message: str, match_pattern: str) -> Optional[str]:
        """Takes in the raw message and prepares it for lookup"""
        # Format should be like `et <word>` or `en <word>`
        word = re.sub(match_pattern, '', message).strip()
        target = message[:2]

        processed_word = cls.get_root(word) if target == 'en' else word

        if processed_word is not None:
            return cls._get_translation(processed_word, target)
        else:
            return f'Translation not found for `{word}`.'

    @classmethod
    def _get_translation(cls, word: str, target: str = 'en') -> str:
        """Returns the English translation of the Estonian word"""
        # Find the English translation of the word using EKI
        eki_url = f'{cls.EKI_IES}?Q={parse.quote(word)}&F=V&C06={target}'
        content = cls._prep_for_xpath(eki_url)

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

    @classmethod
    def prep_message_for_examples(cls, message: str, match_pattern: str) -> Optional[str]:
        """Takes in the raw message and prepares it for lookup"""
        # Format should be like `et <word>` or `en <word>`
        word = re.sub(match_pattern, '', message).strip()
        processed_word = cls.get_root(word)

        if processed_word is not None:
            return cls._get_examples(processed_word, max_n=5)
        else:
            return f'No examples found for `{word}`.'

    @classmethod
    def _get_examples(cls, word: str, max_n: int = 5) -> str:
        """Returns some example sentences of the Estonian word"""
        # Find the English translation of the word using EKI
        ekss_url = f'{cls.EKI_EKSS}?Q={parse.quote(word)}&F=M'
        content = cls._prep_for_xpath(ekss_url)

        results = content.xpath('//div[@class="tervikart"]')
        exp_list = []
        for i in range(0, len(results)):
            result = content.xpath(f'(//div[@class="tervikart"])[{i + 1}]/*/span[@class="m leitud_id"]')
            examples = content.xpath(f'(//div[@class="tervikart"])[{i + 1}]/*/span[@class="n"]')
            # Process text in elements
            result = [''.join(x.itertext()) for x in result]
            examples = [''.join(x.itertext()) for x in examples]
            if word in result:
                re.split(r'[?.!]', ''.join(examples))
                exp_list += re.split(r'[?.!]', ''.join(examples))
                # Strip of leading / tailing whitespace
                exp_list = [x.strip() for x in exp_list if x.strip() != '']
                if len(exp_list) > max_n:
                    exp_list = [exp_list[x] for x in np.random.choice(len(exp_list), max_n, False).tolist()]
                examples = '\n'.join([f'`{x}`' for x in exp_list])
                return f'Examples for `{word}`:\n{examples}'

        return f'No example sentences found for `{word}`'

    @classmethod
    def prep_message_for_root(cls, message: str, match_pattern: str) -> Optional[str]:
        """Takes in the raw message and prepares it for lookup"""
        # Format should be like `lemma <word>`
        word = re.sub(match_pattern, '', message).strip()

        # Make sure the word is a root if it's Estonian
        lemma = cls.get_root(word)

        if lemma is not None:
            return f'Lemma for `{word}`: `{lemma}`'
        else:
            return f'Lemmatization not found for `{word}`.'

    @staticmethod
    def get_root(word: str) -> Optional[str]:
        """Retrieves the root word (nom. sing.) from Lemmatiseerija"""
        # First, look up the word's root with the lemmatiseerija
        lemma_url = f'https://www.filosoft.ee/lemma_et/lemma.cgi?word={parse.quote(word)}'
        content = requests.get(lemma_url).content
        content = str(content, 'utf-8')
        # Use regex to find the word/s
        lemma_regex = re.compile(r'<strong>.*na\slemma[d]?\son:</strong><br>(\w+)<br>')
        match = lemma_regex.search(content)
        word = None
        if match is not None:
            word = match.group(1)
        return word
