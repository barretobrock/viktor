import re
import time
from datetime import datetime
from typing import List, Dict
import pytz
from slack.errors import SlackApiError
from easylogger import Log
from slacktools import SecretStore, GSheetReader, SlackTools
from viktor.model import Base, TableEmojis, AcronymTypes, TableAcronyms, TableUsers, TablePerks, \
    ResponseTypes, TableResponses, TableFacts, TableUwu, TableInsults, InsultTypes, TablePhrases, PhraseTypes, \
    TableCompliments, ComplimentTypes, TableQuotes
from viktor.etl import acronym_tables, emoji_tables, okr_tables, response_tables, user_tables, quotes_tables
from viktor.settings import auto_config
from viktor.utils import collect_pins


class ETL:
    """For holding all the various ETL processes, delimited by table name or function of data stored"""

    def __init__(self, tables: List[str]):
        self.log = Log('vik-etl', log_level_str='DEBUG', log_to_file=True)
        self.log.debug('Opening up the database...')
        self.session, self.eng = auto_config.SESSION(), auto_config.engine

        # Determine tables to drop
        self.log.debug(f'Dropping tables: {tables} from db...')
        tbl_objs = []
        for table in tables:
            tbl_objs.append(Base.metadata.tables.get(table))
        Base.metadata.drop_all(self.eng, tables=tbl_objs)
        self.log.debug('Establishing database...')
        Base.metadata.create_all(self.eng)

        self.log.debug('Authenticating credentials for services...')
        credstore = SecretStore('secretprops-bobdev.kdbx')
        cah_creds = credstore.get_key_and_make_ns(auto_config.BOT_NICKNAME)
        self.gsr = GSheetReader(sec_store=credstore, sheet_key=cah_creds.spreadsheet_key)
        self.st = SlackTools(credstore, auto_config.BOT_NICKNAME, self.log)
        self.log.debug('Completed loading services')

    def etl_acronyms(self):
        self.log.debug('Working on acronyms...')
        df = self.gsr.get_sheet('acronyms')
        col_mapping = {
            'standard': AcronymTypes.standard,
            'f': AcronymTypes.fun,
            'i': AcronymTypes.work,
            'urban': AcronymTypes.urban
        }
        for col in df.columns.tolist():
            self.log.debug(f'Building list for {col}...')
            word_list = df.loc[df[col].notnull(), col].unique().tolist()
            self.session.add_all([TableAcronyms(type=col_mapping[col], text=x) for x in word_list])
        self.session.commit()

    def etl_emojis(self):
        """ETL for emojis"""
        self.log.debug('Working on emojis...')
        emojis = list(self.st.get_emojis().keys())
        regex = re.compile('.*[0-9][-_][0-9].*')
        matches = list(filter(regex.match, emojis))
        items = []
        for emoji in emojis:
            items.append(TableEmojis(name=emoji, is_denylisted=emoji in matches))
        self.log.debug(f'Adding {len(items)} to table..')
        self.session.add_all(items)
        self.session.commit()

    def etl_okr_users(self):
        # Users
        self.log.debug('Working on OKR users...')
        users = self.st.get_channel_members(channel=auto_config.GENERAL_CHANNEL, humans_only=False)
        roles = self.gsr.get_sheet('okr_roles')
        usr_tbls = []
        for user in users:
            display_name = user['display_name']
            name = display_name if display_name != '' else user['real_name']
            uid = user['id']
            role_row = roles.loc[roles['user'] == uid, :]
            if role_row.empty:
                usr_tbls.append(
                    TableUsers(slack_id=uid, name=name)
                )
            else:
                usr_tbls.append(
                    TableUsers(slack_id=uid, name=name, role=role_row['role'].values[0],
                               role_desc=role_row['desc'].values[0], level=role_row['level'].values[0],
                               ltits=role_row['ltits'].values[0])
                )
        self.log.debug(f'Adding {len(usr_tbls)} user details to table...')
        self.session.add_all(usr_tbls)
        self.session.commit()

    def etl_okr_perks(self):
        # Perks
        self.log.debug('Working on OKR perks...')
        perks = self.gsr.get_sheet('okr_perks')
        perk_rows = []
        for i, row in perks.iterrows():
            perk_rows.append(TablePerks(level=row['level'], desc=row['perk']))
        self.log.debug(f'Adding {len(perk_rows)} rows to table...')
        self.session.add_all(perk_rows)
        self.session.commit()

    def _parse_df(self, sheet_name: str, tbl_name: str, col_mapping: Dict = None):
        """Parses a dataframe into a series of unique word lists"""
        df = self.gsr.get_sheet(sheet_name=sheet_name)
        finished_rows = []
        for col in df.columns.tolist():
            self.log.debug(f'Reading in {col} word list...')
            word_list = df.loc[(~df[col].isnull()) & (df[col] != ''), col].tolist()
            # Add to table
            if tbl_name == 'responses':
                finished_rows += [TableResponses(type=col_mapping[col], text=x) for x in word_list]
            elif tbl_name == 'insults':
                insult, stage = col.split('_')
                finished_rows += [TableInsults(type=col_mapping[insult], stage=stage, text=x) for x in word_list]
            elif tbl_name == 'compliments':
                cmp, stage = col.split('_')
                finished_rows += [TableCompliments(type=col_mapping[cmp], stage=stage, text=x) for x in word_list]
            elif tbl_name == 'phrases':
                phrs, stage = col.split('_')
                finished_rows += [TablePhrases(type=col_mapping[phrs], stage=stage, text=x) for x in word_list]
            elif tbl_name == 'facts':
                finished_rows += [TableFacts(text=x) for x in word_list]
            elif tbl_name == 'uwu_graphics':
                finished_rows += [TableUwu(graphic=x) for x in word_list]
        self.log.debug(f'Adding {len(finished_rows)} items to session...')
        self.session.add_all(finished_rows)

    def etl_responses(self):
        # Responses
        self.log.debug('Working on responses...')
        col_mapping = {
            'stakeholder': ResponseTypes.stakeholder,
            'general': ResponseTypes.general,
            'sarcastic': ResponseTypes.sarcastic
        }
        self._parse_df('responses', tbl_name='responses', col_mapping=col_mapping)

        # Insults
        self.log.debug('Working on insults...')
        col_mapping = {
            'standard': InsultTypes.standard,
            'i': InsultTypes.work
        }
        self._parse_df('insults', tbl_name='insults', col_mapping=col_mapping)

        # Compliments
        self.log.debug('Working on compliments...')
        col_mapping = {
            'std': ComplimentTypes.standard,
            'indeed': ComplimentTypes.work
        }
        self._parse_df('compliments', tbl_name='compliments', col_mapping=col_mapping)

        # Phrases
        self.log.debug('Working on phrases...')
        col_mapping = {
            'south': PhraseTypes.standard,
            'bs': PhraseTypes.work
        }
        self._parse_df('phrases', tbl_name='phrases', col_mapping=col_mapping)

        # Facts
        self.log.debug('Working on facts...')
        self._parse_df('facts', tbl_name='facts')

        # UWU
        self.log.debug('Working on uwu_graphics...')
        self._parse_df('uwu_graphics', tbl_name='uwu_graphics')
        self.session.commit()
        self.log.debug('Completed response ETL')

    def etl_quotes(self):
        # Users
        self.log.debug('Working on quotes...')
        # First we get all the channels
        channels = []
        prev_len = 0
        channels_resp = self.st.bot.conversations_list(limit=1000)
        for ch in channels_resp.get('channels'):
            self.log.debug(f'Adding {ch["name"]}')
            channels.append({'id': ch['id'], 'name': ch['name']})
        # Then we iterate through the channels and collect the pins
        tbl_objs = []
        for i, chan in enumerate(channels):
            self.log.debug(f'Working on item {i}')
            c_name = chan['name']
            if c_name.startswith('shitpost'):
                continue
            c_id = chan['id']
            self.log.debug(f'Getting pins for channel: {c_name} ({c_id})')
            try:
                pins_resp = self.st.bot.pins_list(channel=c_id)
            except SlackApiError as err:
                # Check if the error is associated with not being in the channel
                resp = err.response.get('error')
                self.log.error(f'Received error response: {resp}')
                pins_resp = {'items': []}
            pins = pins_resp.get('items')
            for pin in pins:
                tbl_objs.append(collect_pins(pin, session=self.session, log=self.log))
            # Wait so we don't exceed call limits
            if prev_len < len(tbl_objs):
                self.log.debug('Cooling off')
                time.sleep(3)
            prev_len = len(tbl_objs)
        self.session.add_all(tbl_objs)
        self.log.debug(f'Added {len(tbl_objs)} pins')
        self.session.commit()


if __name__ == '__main__':
    all_tables = acronym_tables + emoji_tables + response_tables + okr_tables + user_tables + quotes_tables
    etl = ETL(tables=all_tables)
    etl.etl_acronyms()
    etl.etl_emojis()
    etl.etl_okr_perks()
    etl.etl_okr_users()
    etl.etl_quotes()
    etl.etl_responses()
