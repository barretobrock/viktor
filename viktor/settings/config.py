"""Configuration setup"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from viktor._version import get_versions
from viktor.model import Base


class Common(object):
    """Configuration items common across all config types"""
    BOT_FIRST_NAME = 'Viktor Boborokodorovich'
    BOT_NICKNAME = 'viktor'
    ADMINS = ['UM35HE6R5']
    TRIGGERS = ['viktor', 'v!']
    _v = get_versions()
    VERSION = _v['version']
    UPDATE_DATE = _v['date']
    DB_PATH = os.path.join(os.path.expanduser('~'), *['data', 'okrdb.db'])
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f'DB_PATH at {DB_PATH} invalid...')
    engine = create_engine(f'sqlite:///{DB_PATH}')
    Base.metadata.bind = engine
    SESSION = sessionmaker(bind=engine)

    TEST_CHANNEL = 'CM376Q90F'
    EMOJI_CHANNEL = 'CLWCPQ2TV'
    GENERAL_CHANNEL = 'CMEND3W3H'


class Development(Common):
    """Configuration for development environment"""
    BOT_LAST_NAME = 'Debugnatov'
    MAIN_CHANNEL = 'CM376Q90F'  # #test
    DEBUG = True


class Production(Common):
    """Configuration for development environment"""
    BOT_LAST_NAME = 'Produdnikov'
    MAIN_CHANNEL = 'CMEND3W3H'  # #general
    DEBUG = False
