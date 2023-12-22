from unittest import (
    TestCase,
    main,
)

from slacktools.block_kit.blocks import PlainTextHeaderBlock

from viktor.core.user_changes import build_profile_diff


class TestUserChanges(TestCase):

    def test_build_profile_diff(self):
        # Set Variables
        # -------------------------------------------------------------------------------------------------------------
        initial_blocks = [
            PlainTextHeaderBlock('Something').asdict()
        ]
        updated_user_dict = {
            'display_name': {
                'old': 'old_name',
                'new': 'new_name'
            }
        }
        # Build / populate mocks
        # -------------------------------------------------------------------------------------------------------------

        # Call
        # -------------------------------------------------------------------------------------------------------------
        blocks = build_profile_diff(blocks=initial_blocks, updated_user_dict=updated_user_dict)
        # Assert
        # -------------------------------------------------------------------------------------------------------------
        self.assertEqual(len(blocks), 4)


if __name__ == '__main__':
    main()
