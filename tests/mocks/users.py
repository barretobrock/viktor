from random import choice
from string import ascii_uppercase


def random_user(is_bot: bool = False) -> str:
    """Generates a random user id"""
    prefix = 'B' if is_bot else 'U'
    user = ''.join(choice(ascii_uppercase) for _ in range(10))
    return f'{prefix}{user}'
