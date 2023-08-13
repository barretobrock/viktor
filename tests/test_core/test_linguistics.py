from unittest import (
    TestCase,
    main,
)

from viktor.core.linguistics import Linguistics

from ..common import make_patcher


class TestLinguistics(TestCase):

    def test_prep_for_xpath(self):
        # Set Variables
        # -------------------------------------------------------------------------------------------------------------
        url = 'not_a-real-url'
        # Build / populate mocks
        # -------------------------------------------------------------------------------------------------------------
        mock_requests = make_patcher(self, 'viktor.core.linguistics.requests')
        mock_etree = make_patcher(self, 'viktor.core.linguistics.etree')
        mock_requests.get().content.decode.return_value = '<html></html>'
        # Call
        # -------------------------------------------------------------------------------------------------------------
        Linguistics._prep_for_xpath(url)
        # Assert
        # -------------------------------------------------------------------------------------------------------------
        mock_requests.get.assert_called_with(url)
        mock_etree.HTMLParser.assert_called()


if __name__ == '__main__':
    main()
