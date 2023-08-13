from unittest import (
    TestCase,
    main,
)
from unittest.mock import MagicMock
from io import StringIO

from viktor.core.text_cleaner import XPathExtractor

from ..common import make_patcher


class TestXPathExtractor(TestCase):

    def setUp(self) -> None:
        # Set Variables
        # -------------------------------------------------------------------------------------------------------------
        url = 'some-fake-url'
        # Build / populate mocks
        # -------------------------------------------------------------------------------------------------------------

        self.mock_request = make_patcher(self, 'viktor.core.text_cleaner.Request')
        self.mock_urlopen = make_patcher(self, 'viktor.core.text_cleaner.urlopen')
        self.mock_etree = make_patcher(self, 'viktor.core.text_cleaner.etree')
        # self.mock_urlopen().code = 200
        self.mock_urlopen.return_value = MagicMock(
            return_value=StringIO('<html><body><ul><li>Hello</li></ul></body></html>'),
            code=200
        )
        self.mock_request.return_value = self.mock_urlopen

        self.xp = XPathExtractor(url=url)

    def test_get_nth_child(self):
        # Set Variables
        # -------------------------------------------------------------------------------------------------------------

        # Build / populate mocks
        # -------------------------------------------------------------------------------------------------------------

        # Call
        # -------------------------------------------------------------------------------------------------------------
        self.xp.get_nth_child(self.xp.tree, 0)
        # Assert
        # -------------------------------------------------------------------------------------------------------------
        self.mock_etree.parse.assert_called()


if __name__ == '__main__':
    main()
