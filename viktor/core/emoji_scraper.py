import re
from loguru import logger
from viktor.model import TablePotentialEmoji
from viktor.db_eng import ViktorPSQLClient
from viktor.core.text_cleaner import XPathExtractor


def scrape_emojis(psql_engine: ViktorPSQLClient, log: logger):
    """Scrape a site for emojis to announce newly-added emojis periodically"""
    url = 'https://slackmojis.com/emojis/recent'
    log.debug('Loading recent emojis page...')
    xpath_extractor = XPathExtractor(url)

    emoji_list = xpath_extractor.xpath('//ul[@class="emojis"]', single=True)
    emojis = emoji_list.getchildren()

    # Get a list of ids (tracked by the site) of the past emojis we've collected
    with psql_engine.session_mgr() as session:
        prev_emoji_ids = [x.data_emoji_id for x in session.query(TablePotentialEmoji).
                          order_by(TablePotentialEmoji.data_emoji_id).limit(250).all()]

    new_emojis = []
    for emoji in emojis:
        emo_id = emoji.getchildren()[0].get('data-emoji-id')
        emo_name = emoji.getchildren()[0].getchildren()[1].text.strip()
        if emo_id not in prev_emoji_ids:
            # Get link and add to the id list
            emo_link = emoji.findall('.//img')[0].get('src')
            # Get the epoch timetstamp from the url
            emo_ts = re.search(r'(?<=images/)\d+', emo_link).group()
            if emo_link is not None:
                new_emojis.append(
                    TablePotentialEmoji(name=emo_name, data_emoji_id=emo_id, upload_timestamp=int(emo_ts),
                                        link=emo_link)
                )
    # Add the emojis to the table
    with psql_engine.session_mgr() as session:
        session.add_all(new_emojis)
