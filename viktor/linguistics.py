#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
import requests
import json
import numpy as np
import urllib.parse as parse
from typing import Optional
from io import StringIO
from googletrans import Translator
from lxml import etree


class Linguistics:
    """Language methods"""

    iso_639_codes = dict([
        ('ab', 'Abkhaz'),
        ('aa', 'Afar'),
        ('af', 'Afrikaans'),
        ('ak', 'Akan'),
        ('sq', 'Albanian'),
        ('am', 'Amharic'),
        ('ar', 'Arabic'),
        ('an', 'Aragonese'),
        ('hy', 'Armenian'),
        ('as', 'Assamese'),
        ('av', 'Avaric'),
        ('ae', 'Avestan'),
        ('ay', 'Aymara'),
        ('az', 'Azerbaijani'),
        ('bm', 'Bambara'),
        ('ba', 'Bashkir'),
        ('eu', 'Basque'),
        ('be', 'Belarusian'),
        ('bn', 'Bengali'),
        ('bh', 'Bihari'),
        ('bi', 'Bislama'),
        ('bs', 'Bosnian'),
        ('br', 'Breton'),
        ('bg', 'Bulgarian'),
        ('my', 'Burmese'),
        ('ca', 'Catalan; Valencian'),
        ('ch', 'Chamorro'),
        ('ce', 'Chechen'),
        ('ny', 'Chichewa; Chewa; Nyanja'),
        ('zh', 'Chinese'),
        ('cv', 'Chuvash'),
        ('kw', 'Cornish'),
        ('co', 'Corsican'),
        ('cr', 'Cree'),
        ('hr', 'Croatian'),
        ('cs', 'Czech'),
        ('da', 'Danish'),
        ('dv', 'Divehi; Maldivian;'),
        ('nl', 'Dutch'),
        ('dz', 'Dzongkha'),
        ('en', 'English'),
        ('eo', 'Esperanto'),
        ('et', 'Estonian'),
        ('ee', 'Ewe'),
        ('fo', 'Faroese'),
        ('fj', 'Fijian'),
        ('fi', 'Finnish'),
        ('fr', 'French'),
        ('ff', 'Fula'),
        ('gl', 'Galician'),
        ('ka', 'Georgian'),
        ('de', 'German'),
        ('el', 'Greek, Modern'),
        ('gn', 'Guaraní'),
        ('gu', 'Gujarati'),
        ('ht', 'Haitian'),
        ('ha', 'Hausa'),
        ('he', 'Hebrew (modern)'),
        ('hz', 'Herero'),
        ('hi', 'Hindi'),
        ('ho', 'Hiri Motu'),
        ('hu', 'Hungarian'),
        ('ia', 'Interlingua'),
        ('id', 'Indonesian'),
        ('ie', 'Interlingue'),
        ('ga', 'Irish'),
        ('ig', 'Igbo'),
        ('ik', 'Inupiaq'),
        ('io', 'Ido'),
        ('is', 'Icelandic'),
        ('it', 'Italian'),
        ('iu', 'Inuktitut'),
        ('ja', 'Japanese'),
        ('jv', 'Javanese'),
        ('kl', 'Kalaallisut'),
        ('kn', 'Kannada'),
        ('kr', 'Kanuri'),
        ('ks', 'Kashmiri'),
        ('kk', 'Kazakh'),
        ('km', 'Khmer'),
        ('ki', 'Kikuyu, Gikuyu'),
        ('rw', 'Kinyarwanda'),
        ('ky', 'Kirghiz, Kyrgyz'),
        ('kv', 'Komi'),
        ('kg', 'Kongo'),
        ('ko', 'Korean'),
        ('ku', 'Kurdish'),
        ('kj', 'Kwanyama, Kuanyama'),
        ('la', 'Latin'),
        ('lb', 'Luxembourgish'),
        ('lg', 'Luganda'),
        ('li', 'Limburgish'),
        ('ln', 'Lingala'),
        ('lo', 'Lao'),
        ('lt', 'Lithuanian'),
        ('lu', 'Luba-Katanga'),
        ('lv', 'Latvian'),
        ('gv', 'Manx'),
        ('mk', 'Macedonian'),
        ('mg', 'Malagasy'),
        ('ms', 'Malay'),
        ('ml', 'Malayalam'),
        ('mt', 'Maltese'),
        ('mi', 'Māori'),
        ('mr', 'Marathi (Marāṭhī)'),
        ('mh', 'Marshallese'),
        ('mn', 'Mongolian'),
        ('na', 'Nauru'),
        ('nv', 'Navajo, Navaho'),
        ('nb', 'Norwegian Bokmål'),
        ('nd', 'North Ndebele'),
        ('ne', 'Nepali'),
        ('ng', 'Ndonga'),
        ('nn', 'Norwegian Nynorsk'),
        ('no', 'Norwegian'),
        ('ii', 'Nuosu'),
        ('nr', 'South Ndebele'),
        ('oc', 'Occitan'),
        ('oj', 'Ojibwe, Ojibwa'),
        ('cu', 'Old Church Slavonic'),
        ('om', 'Oromo'),
        ('or', 'Oriya'),
        ('os', 'Ossetian, Ossetic'),
        ('pa', 'Panjabi, Punjabi'),
        ('pi', 'Pāli'),
        ('fa', 'Persian'),
        ('pl', 'Polish'),
        ('ps', 'Pashto, Pushto'),
        ('pt', 'Portuguese'),
        ('qu', 'Quechua'),
        ('rm', 'Romansh'),
        ('rn', 'Kirundi'),
        ('ro', 'Romanian, Moldavan'),
        ('ru', 'Russian'),
        ('sa', 'Sanskrit (Saṁskṛta)'),
        ('sc', 'Sardinian'),
        ('sd', 'Sindhi'),
        ('se', 'Northern Sami'),
        ('sm', 'Samoan'),
        ('sg', 'Sango'),
        ('sr', 'Serbian'),
        ('gd', 'Scottish Gaelic'),
        ('sn', 'Shona'),
        ('si', 'Sinhala, Sinhalese'),
        ('sk', 'Slovak'),
        ('sl', 'Slovene'),
        ('so', 'Somali'),
        ('st', 'Southern Sotho'),
        ('es', 'Spanish; Castilian'),
        ('su', 'Sundanese'),
        ('sw', 'Swahili'),
        ('ss', 'Swati'),
        ('sv', 'Swedish'),
        ('ta', 'Tamil'),
        ('te', 'Telugu'),
        ('tg', 'Tajik'),
        ('th', 'Thai'),
        ('ti', 'Tigrinya'),
        ('bo', 'Tibetan'),
        ('tk', 'Turkmen'),
        ('tl', 'Tagalog'),
        ('tn', 'Tswana'),
        ('to', 'Tonga'),
        ('tr', 'Turkish'),
        ('ts', 'Tsonga'),
        ('tt', 'Tatar'),
        ('tw', 'Twi'),
        ('ty', 'Tahitian'),
        ('ug', 'Uighur, Uyghur'),
        ('uk', 'Ukrainian'),
        ('ur', 'Urdu'),
        ('uz', 'Uzbek'),
        ('ve', 'Venda'),
        ('vi', 'Vietnamese'),
        ('vo', 'Volapük'),
        ('wa', 'Walloon'),
        ('cy', 'Welsh'),
        ('wo', 'Wolof'),
        ('fy', 'Western Frisian'),
        ('xh', 'Xhosa'),
        ('yi', 'Yiddish'),
        ('yo', 'Yoruba'),
        ('za', 'Zhuang, Chuang'),
        ('zu', 'Zulu'),
    ])

    def __init__(self):
        self.trans = Translator()

    @staticmethod
    def _prep_for_xpath(url: str) -> etree.ElementBase:
        """Takes in a url and returns a tree that can be searched using xpath"""
        page = requests.get(url)
        html = page.content.decode('utf-8')
        parser = etree.HTMLParser()
        tree = etree.parse(StringIO(html), parser=parser)
        return tree

    def get_etymology(self, message: str, **kwargs):
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

        match_pattern = kwargs.pop('match_pattern', None)
        if match_pattern is not None:
            word = re.sub(match_pattern, '', message).strip()
        else:
            return None

        url = f'https://www.etymonline.com/search?q={parse.quote(word)}'
        content = self._prep_for_xpath(url)
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

    def prep_message_for_translation(self, message: str, **kwargs) -> Optional[str]:
        """Takes in the raw message and prepares it for lookup"""
        # Format should be like `et <word>` or `en <word>`
        match_pattern = kwargs.pop('match_pattern', None)
        if match_pattern is not None:
            word = re.sub(match_pattern, '', message).strip()
            target = message[:2]
        else:
            return None

        processed_word = self.get_root(word) if target == 'en' else word

        if processed_word is not None:
            return self._get_translation(processed_word, target)
        else:
            return f'Translation not found for `{word}`.'

    def _get_translation(self, word: str, target: str = 'en') -> str:
        """Returns the English translation of the Estonian word"""
        # Find the English translation of the word using EKI
        eki_url = f'http://www.eki.ee/dict/ies/index.cgi?Q={parse.quote(word)}&F=V&C06={target}'
        content = self._prep_for_xpath(eki_url)

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

    def prep_message_for_examples(self, message: str, **kwargs) -> Optional[str]:
        """Takes in the raw message and prepares it for lookup"""
        # Format should be like `et <word>` or `en <word>`
        match_pattern = kwargs.pop('match_pattern', None)
        if match_pattern is not None:
            word = re.sub(match_pattern, '', message).strip()
        else:
            return None
        processed_word = self.get_root(word)

        if processed_word is not None:
            return self._get_examples(processed_word, max_n=5)
        else:
            return f'No examples found for `{word}`.'

    def _get_examples(self, word: str, max_n: int = 5) -> str:
        """Returns some example sentences of the Estonian word"""
        # Find the English translation of the word using EKI
        ekss_url = f'http://www.eki.ee/dict/ekss/index.cgi?Q={parse.quote(word)}&F=M'
        content = self._prep_for_xpath(ekss_url)

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

    def prep_message_for_root(self, message: str, **kwargs) -> Optional[str]:
        """Takes in the raw message and prepares it for lookup"""
        # Format should be like `lemma <word>`
        match_pattern = kwargs.pop('match_pattern', None)
        if match_pattern is not None:
            word = re.sub(match_pattern, '', message).strip()
        else:
            return None

        # Make sure the word is a root if it's Estonian
        lemma = self.get_root(word)

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

    def translate_anything(self, text: str, target_lang: str) -> dict:
        """Uses Google Translate (heh) to try and translate any phrase"""
        # Pick up detection confidence
        try:
            src = self.trans.detect(text)
        except json.JSONDecodeError:
            text = re.sub(r'[^\w\s]+', '', text)
            src = self.trans.detect(text)
        src_lang = src.lang
        translation = self.trans.translate(text, dest=target_lang, src=src_lang)
        return {
            'src_code': src_lang,
            'src_name': self.iso_639_codes[src_lang],
            'conf': src.confidence,
            'tgt_code': translation.dest,
            'tgt_name': self.iso_639_codes[translation.dest],
            'translation': translation.text
        }
