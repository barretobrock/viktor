import random
import string
import sys
from unittest.mock import patch

from loguru import logger


def make_patcher(obj, name: str) -> patch:
    """Makes patching a bit easier

    Args:
        obj: this is generally the test object you want the patch applied to. If this is the case, obj=self
        name: the name of the library to be patched. Keep in mind, library paths also work
            (e.g. requests.get)
    """
    patcher = patch(name)
    patched_item = patcher.start()
    obj.addCleanup(patcher.stop)
    return patched_item


def get_test_logger() -> logger:
    """Configures and returns the logger object for running tests.

    Note that this only logs to stdout.
    """
    FORMAT = '<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | ' \
             '<cyan>{name} -> {extra[child_name]}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - ' \
             '<level>{message}</level>'
    config = {
        'handlers': [
            {
                'sink': sys.stdout,
                'level': 'DEBUG',
                'format': FORMAT
            }
        ],
        'extra': {
            'child_name': 'main'
        }
    }
    logger.configure(**config)
    return logger


def random_string(n_chars: int = 10, addl_chars: str = None) -> str:
    """Generates a random string of n characters in length"""
    chars = string.ascii_letters
    if addl_chars is not None:
        chars += addl_chars
    return ''.join([random.choice(chars) for i in range(n_chars)])


def random_float(min_rng: float, max_rng: float) -> float:
    """Randomly selects a float based on a given range"""
    return random.random() * (max_rng - min_rng) + min_rng
