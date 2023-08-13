import unittest
from unittest.mock import MagicMock

from viktor.core.emoji_scraper import scrape_emojis

from ..common import make_patcher


class TestEmojiScraper(unittest.TestCase):

    def test_scrape_emojis(self):
        # Set Variables
        # -------------------------------------------------------------------------------------------------------------
        emoji_url = 'https://slackmojis.com/emojis/recent'
        prev_emoji_id = '12397'
        emoji_id = '12398'
        emoji_name = ':hello-there:'
        emoji_ts = 1691892467
        emoji_src = f'{emoji_url}/images/{emoji_ts}/{emoji_id}/name.png?3298472342'
        # Build / populate mocks
        # -------------------------------------------------------------------------------------------------------------
        mock_psql_client = MagicMock(name='PSQLClient')
        mock_psql_client.session_mgr().__enter__().query().order_by().limit().all.return_value = [
            MagicMock(data_emoji_id=prev_emoji_id)
        ]

        mock_emoji_li = MagicMock(name='li_1')
        mock_emoji_li.getchildren().__getitem__().get.return_value = emoji_id
        mock_emoji_li.getchildren().__getitem__().getchildren().__getitem__().text = f'\n{emoji_name}\n'
        mock_emoji_li.findall().__getitem__().get.return_value = emoji_src

        mock_xpath_response = MagicMock(name='ul')
        mock_xpath_response.getchildren.return_value = [mock_emoji_li]

        mock_xpath_extract = make_patcher(self, 'viktor.core.emoji_scraper.XPathExtractor')
        mock_xpath_extract().xpath.return_value = mock_xpath_response

        # Call
        # -------------------------------------------------------------------------------------------------------------
        scrape_emojis(psql_engine=mock_psql_client)
        # Assert
        # -------------------------------------------------------------------------------------------------------------
        mock_xpath_extract.assert_called_with(emoji_url)
        mock_psql_client.session_mgr().__enter__().add_all.assert_called()


if __name__ == '__main__':
    unittest.main()
