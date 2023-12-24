import re
import time
from typing import (
    Dict,
    List,
)

from pukr import get_logger
from slack_sdk.errors import SlackApiError
from slacktools import (
    SecretStore,
    SlackTools,
)
from slacktools.api.web.pins import Pin
from slacktools.gsheet import GSheetAgent

from viktor.core.pin_collector import collect_pins
from viktor.db_eng import ViktorPSQLClient
from viktor.model import (
    AcronymType,
    Base,
    BotSettingType,
    ResponseCategory,
    ResponseType,
    TableAcronym,
    TableBotSetting,
    TableEmoji,
    TableError,
    TablePerk,
    TablePotentialEmoji,
    TableQuote,
    TableResponse,
    TableSlackChannel,
    TableSlackUser,
    TableSlackUserChangeLog,
    TableUwu,
)
from viktor.settings import (
    Development,
    Production,
)


class ETL:
    """For holding all the various ETL processes, delimited by table name or function of data stored"""
    ALL_TABLES = [
        TableAcronym,
        TableBotSetting,
        TableEmoji,
        TableError,
        TablePerk,
        TablePotentialEmoji,
        TableQuote,
        TableResponse,
        TableSlackChannel,
        TableSlackUser,
        TableSlackUserChangeLog,
        TableUwu
    ]

    TEST_CHANNEL = 'CM376Q90F'
    EMOJI_CHANNEL = 'CLWCPQ2TV'
    GENERAL_CHANNEL = 'CMEND3W3H'
    IMPO_CHANNEL = 'CNPADBLBF'
    CAH_CHANNEL = 'CMPV3K8AE'
    # Prevent automated activity from occurring in these channels
    DENY_LIST_CHANNELS = [IMPO_CHANNEL, CAH_CHANNEL]

    def __init__(self, env: str = 'dev', drop_all: bool = True, incl_services: bool = True):
        self.log = get_logger()
        self.log.debug('Obtaining credential file...')
        if env.upper() == 'PROD':
            Production.load_secrets()
            props = Production.SECRETS
        else:
            Development.load_secrets()
            props = Development.SECRETS

        self.log.debug('Opening up the database...')

        self.psql_client = ViktorPSQLClient(props=props, parent_log=self.log)

        if incl_services:
            self.log.debug('Authenticating credentials for services...')
            credstore = SecretStore('secretprops-davaiops.kdbx')
            vik_creds = credstore.get_key_and_make_ns(Development.BOT_NICKNAME)
            self.gsr = GSheetAgent(sec_store=credstore, sheet_key=vik_creds.spreadsheet_key)
            self.st = SlackTools(props=props, main_channel=Development.MAIN_CHANNEL, use_session=False)
            self.log.debug('Completed loading services')

    def handle_table_drops(self, tables: List = None, create_only: bool = True):
        # Determine tables to drop
        self.log.debug(f'Working on tables: {tables} from db...')
        tbl_objs = []
        for table in tables:
            tbl_objs.append(
                Base.metadata.tables.get(f'{table.__table_args__.get("schema")}.{table.__tablename__}'))
        if not create_only:
            # We're likely doing a refresh - drop/create operations will be for all object
            self.log.debug(f'Dropping {len(tbl_objs)} listed tables...')
            Base.metadata.drop_all(self.psql_client.engine, tables=tbl_objs)
        self.log.debug(f'Creating {len(tbl_objs)} listed tables...')
        Base.metadata.create_all(self.psql_client.engine, tables=tbl_objs)

    def etl_bot_settings(self):
        self.log.debug('Working on settings...')
        bot_settings = []
        for bot_setting in list(BotSettingType):
            value = 1 if bot_setting.name.startswith('IS_') else 0
            bot_settings.append(TableBotSetting(setting_type=bot_setting, setting_int=value))

        with self.psql_client.session_mgr() as session:
            self.log.debug(f'Adding {len(bot_settings)} bot settings.')
            session.add_all(bot_settings)

    def etl_acronyms(self):
        self.log.debug('Working on acronyms...')
        df = self.gsr.get_sheet('acronyms')
        col_mapping = {
            'standard': AcronymType.STANDARD,
            'f': AcronymType.FUN,
            'i': AcronymType.WORK,
            'urban': AcronymType.URBAN
        }
        acro_objs = []
        for col in df.columns.tolist():
            self.log.debug(f'Building list for {col}...')
            word_list = df.loc[df[col].notnull(), col].unique().tolist()
            acro_objs += [TableAcronym(acro_type=col_mapping[col], text=x) for x in word_list]
        with self.psql_client.session_mgr() as session:
            self.log.debug(f'Adding {len(acro_objs)} acronym entries...')
            session.add_all(acro_objs)

    def etl_emojis(self):
        """ETL for emojis"""
        self.log.debug('Working on emojis...')
        emojis = list(self.st.get_emojis().keys())
        regex = re.compile('.*[0-9][-_][0-9].*')
        matches = list(filter(regex.match, emojis))
        items = []
        for emoji in emojis:
            items.append(TableEmoji(name=emoji, is_react_denylisted=emoji in matches))
        self.log.debug(f'Adding {len(items)} to table..')
        with self.psql_client.session_mgr() as session:
            self.log.debug(f'Adding {len(items)} emoji entries...')
            session.add_all(items)

    def etl_okr_users(self):
        # Users
        self.log.debug('Working on OKR users...')
        users = self.st.get_channel_members(channel=self.GENERAL_CHANNEL, humans_only=False)
        roles = self.gsr.get_sheet('okr_roles')
        usr_tbls = []
        for user in users:
            display_name = user.profile.display_name
            real_name = user.real_name
            display_name = real_name if display_name == '' else display_name
            uid = user.id
            role_row = roles.loc[roles['user'] == uid, :]
            params = dict(
                slack_user_hash=uid,
                real_name=real_name,
                display_name=display_name,
                avatar_link=user.profile.image_32
            )
            if not role_row.empty:
                params.update({
                    'role_title': role_row['role'].values[0],
                    'role_desc': role_row['desc'].values[0],
                    'level': role_row['level'].values[0],
                    'ltits': role_row['ltits'].values[0]
                })
            usr_tbls.append(
                TableSlackUser(**params)
            )
        # Add slackbot
        usr_tbls.append(TableSlackUser(slack_user_hash='USLACKBOT', real_name='slackbot', display_name='slackboi'))
        usr_tbls.append(TableSlackUser(slack_user_hash='UUNKNOWN', slack_bot_hash='BUNKNOWN', real_name='abot',
                                       display_name='a-bot'))
        with self.psql_client.session_mgr() as session:
            self.log.debug(f'Adding {len(usr_tbls)} user details to table...')
            session.add_all(usr_tbls)

    def etl_okr_perks(self):
        # Perks
        self.log.debug('Working on OKR perks...')
        perks = self.gsr.get_sheet('okr_perks')
        perk_rows = []
        for i, row in perks.iterrows():
            perk_rows.append(TablePerk(level=row['level'], desc=row['perk']))

        with self.psql_client.session_mgr() as session:
            self.log.debug(f'Adding {len(perk_rows)} rows to table...')
            session.add_all(perk_rows)

    def _parse_df(self, sheet_name: str, tbl_name: str, col_mapping: Dict = None):
        """Parses a dataframe into a series of unique word lists"""
        df = self.gsr.get_sheet(sheet_name=sheet_name)
        finished_rows = []
        for col in df.columns.tolist():
            self.log.debug(f'Reading in {col} word list...')
            word_list = df.loc[(~df[col].isnull()) & (df[col] != ''), col].tolist()
            # Add to table
            if tbl_name == 'responses':
                finished_rows += [TableResponse(response_type=ResponseType.GENERAL, category=col_mapping[col],
                                                text=x) for x in word_list]
            elif tbl_name == 'insults':
                insult, stage = col.split('_')
                finished_rows += [TableResponse(response_type=ResponseType.INSULT, category=col_mapping[insult],
                                                stage=stage, text=x) for x in word_list]
            elif tbl_name == 'compliments':
                cmp, stage = col.split('_')
                finished_rows += [TableResponse(response_type=ResponseType.COMPLIMENT, category=col_mapping[cmp],
                                                stage=stage, text=x) for x in word_list]
            elif tbl_name == 'phrases':
                phrs, stage = col.split('_')
                finished_rows += [TableResponse(response_type=ResponseType.PHRASE, category=col_mapping[phrs],
                                                stage=stage, text=x) for x in word_list]
            elif tbl_name == 'facts':
                finished_rows += [TableResponse(response_type=ResponseType.FACT, category=col_mapping[col],
                                                text=x) for x in word_list]
            elif tbl_name == 'uwu_graphics':
                finished_rows += [TableUwu(graphic_txt=x) for x in word_list]
        with self.psql_client.session_mgr() as session:
            self.log.debug(f'Adding {len(finished_rows)} items to session...')
            session.add_all(finished_rows)

    def etl_responses(self):
        # Responses
        self.log.debug('Working on responses...')
        col_mapping = {
            'stakeholder': ResponseCategory.STAKEHOLDER,
            'general': ResponseCategory.STANDARD,
            'sarcastic': ResponseCategory.SARCASTIC,
            'jackhandey': ResponseCategory.JACKHANDEY
        }
        self._parse_df('responses', tbl_name='responses', col_mapping=col_mapping)

        # Insults
        self.log.debug('Working on insults...')
        col_mapping = {
            'standard': ResponseCategory.STANDARD,
            'i': ResponseCategory.WORK
        }
        self._parse_df('insults', tbl_name='insults', col_mapping=col_mapping)

        # Compliments
        self.log.debug('Working on compliments...')
        col_mapping = {
            'std': ResponseCategory.STANDARD,
            'indeed': ResponseCategory.WORK
        }
        self._parse_df('compliments', tbl_name='compliments', col_mapping=col_mapping)

        # Phrases
        self.log.debug('Working on phrases...')
        col_mapping = {
            'south': ResponseCategory.STANDARD,
            'bs': ResponseCategory.WORK
        }
        self._parse_df('phrases', tbl_name='phrases', col_mapping=col_mapping)

        # Facts
        col_mapping = {
            'facts': ResponseCategory.STANDARD,
            'conspiracy_facts': ResponseCategory.FOILHAT
        }
        self.log.debug('Working on facts...')
        self._parse_df('facts', tbl_name='facts', col_mapping=col_mapping)

        # UWU
        self.log.debug('Working on uwu_graphics...')
        self._parse_df('uwu_graphics', tbl_name='uwu_graphics')
        self.log.debug('Completed response ETL')

    def etl_slack_channels(self):
        """Adds slack channels"""
        channels = []
        channels_resp = self.st.bot.conversations_list(limit=1000, types='public_channel,private_channel')
        for ch in channels_resp.get('channels'):
            ch_name = ch['name']
            ch_id = ch['id']
            if not ch['is_channel'] or ch_name.startswith('shitpost'):
                continue
            self.log.debug(f'Adding {ch_name}')
            channels.append(TableSlackChannel(slack_channel_hash=ch_id, channel_name=ch_name,
                                              is_allow_bot_react=ch_id not in self.DENY_LIST_CHANNELS,
                                              is_allow_bot_response=ch_id not in self.DENY_LIST_CHANNELS,
                                              is_archived=ch['is_archived'],
                                              is_private=ch['is_private']))
        with self.psql_client.session_mgr() as session:
            self.log.debug(f'Adding {len(channels)} channels...')
            session.add_all(channels)

    def etl_quotes(self):
        # Users
        self.log.debug('Working on quotes...')
        # First we get all the channels
        channels = []
        channels_resp = self.st.bot.conversations_list(limit=1000, types='public_channel,private_channel')
        for ch in channels_resp.get('channels'):
            self.log.debug(f'Adding {ch["name"]}')
            channels.append({'id': ch['id'], 'name': ch['name'], 'is_archived': ch['is_archived']})
        # Then we iterate through the channels and collect the pins
        total_objs = 0
        for i, chan in enumerate(channels):
            tbl_objs = []
            self.log.debug(f'Working on channel {i}/{len(channels)}')
            c_name = chan['name']
            if c_name.startswith('shitpost'):
                continue
            c_id = chan['id']
            c_is_archived = chan['is_archived']
            self.log.debug(f'Getting pins for channel: {c_name} ({c_id})')
            try:
                pins_resp = self.st.bot.pins_list(channel=c_id)
            except SlackApiError as err:
                # Check if the error is associated with not being in the channel
                resp = err.response.get('error')
                if resp == 'not_in_channel' and not c_is_archived:
                    # Try to join the channel
                    self.log.warning(f'Joining channel {c_name} real quick...')
                    self.st.bot.conversations_join(channel=c_id)
                    time.sleep(1)
                    pins_resp = self.st.bot.pins_list(channel=c_id)
                else:
                    self.log.error(f'Received error response: {resp}')
                    pins_resp = {'items': []}
            pins = pins_resp.get('items')
            for pin in pins:
                pin_obj = Pin(pin)
                tbl_objs.append(collect_pins(pin_obj, psql_client=self.psql_client, log=self.log, is_event=False))
            # Wait so we don't exceed call limits
            self.log.debug('Cooling off')
            time.sleep(5)
            with self.psql_client.session_mgr() as session:
                session.add_all(tbl_objs)
                total_objs += len(tbl_objs)
        self.log.debug(f'Added {total_objs} pins')


if __name__ == '__main__':
    from viktor.model import TableResponse

    # etl = ETL(env='dev')
    # etl.handle_table_drops(tables=ETL.ALL_TABLES, create_only=False)
    # etl.etl_acronyms()
    # etl.etl_emojis()
    # etl.etl_okr_perks()
    # etl.etl_okr_users()
    # etl.etl_slack_channels()
    # etl.etl_quotes()
    # etl.etl_responses()
    # etl.etl_bot_settings()
