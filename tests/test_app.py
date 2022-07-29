from unittest import (
    TestCase,
    main,
)

from tests.common import get_test_logger


class TestApp(TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.log = get_test_logger()


if __name__ == '__main__':
    main()
