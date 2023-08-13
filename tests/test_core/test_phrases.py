from unittest import (
    TestCase,
    main,
)
from unittest.mock import MagicMock

from viktor.core.phrases import PhraseBuilders


class TestPhraseBuilders(TestCase):

    def setUp(self) -> None:
        self.mock_eng = MagicMock(name='ViktorPSQLClient')

        self.pb = PhraseBuilders(self.mock_eng)

    def test_pronoun_objectifier(self):
        # Set Variables
        # -------------------------------------------------------------------------------------------------------------
        phrases = [
            {
                'initial': 'Insult myself',
                'modified': 'Insult you'
            }
        ]
        # Build / populate mocks
        # -------------------------------------------------------------------------------------------------------------

        # Call
        # -------------------------------------------------------------------------------------------------------------
        for phrase_dict in phrases:
            init = phrase_dict['initial']
            exp_modified = phrase_dict['modified']
            resp = self.pb._pronoun_objectifier(init)
            self.assertEqual(exp_modified, resp)
        # Assert
        # -------------------------------------------------------------------------------------------------------------


if __name__ == '__main__':
    main()
