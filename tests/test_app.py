from unittest import TestCase, main
from unittest.mock import MagicMock
from tests.common import (
    get_test_logger,
    random_string
)


class TestApp(TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.log = get_test_logger()


if __name__ == '__main__':
    main()
