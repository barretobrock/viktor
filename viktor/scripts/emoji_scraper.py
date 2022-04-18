from slacktools.secretstore import SecretStore
from viktor.settings import auto_config
from viktor.logg import get_base_logger
from viktor.db_eng import ViktorPSQLClient
from viktor.core.emoji_scraper import scrape_emojis


bot_name = auto_config.BOT_NICKNAME
logg = get_base_logger()

credstore = SecretStore('secretprops-davaiops.kdbx')
# Set up database connection
conn_dict = credstore.get_entry(f'davaidb-{auto_config.ENV.lower()}').custom_properties
vik_creds = credstore.get_key_and_make_ns(bot_name)

eng = ViktorPSQLClient(props=conn_dict, parent_log=logg)

scrape_emojis(psql_engine=eng, log=logg)
