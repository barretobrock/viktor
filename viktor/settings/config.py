"""Configuration setup"""
import pathlib
from typing import Dict

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from viktor import (
    __update_date__,
    __version__,
)
from viktor.model.base import Base

HOME = pathlib.Path().home()
KEY_DIR = HOME.joinpath('keys')
LOG_DIR = HOME.joinpath('logs')


def read_secrets(path_obj: pathlib.Path) -> Dict:
    secrets = {}
    with path_obj.open('r') as f:
        for item in f.readlines():
            if item.startswith('#'):
                continue
            k, v = item.split('=', 1)
            secrets[k] = v.strip()
    return secrets


class Common(object):
    """Configuration items common across all config types"""
    ENV = 'DEV'
    BOT_FIRST_NAME = 'Viktor Bibbilyboopsnug Ivanovich'
    BOT_NICKNAME = 'viktor'
    ADMINS = ['UM35HE6R5']
    TRIGGERS = ['viktor', 'v!']
    LOG_DIR = HOME.joinpath('logs')

    VERSION = __version__
    UPDATE_DATE = __update_date__

    TEST_CHANNEL = 'CM376Q90F'
    EMOJI_CHANNEL = 'CLWCPQ2TV'
    GENERAL_CHANNEL = 'CMEND3W3H'

    LOG_LEVEL = 'DEBUG'
    PORT = 5003

    SECRETS = None
    SQLALCHEMY_DATABASE_URI = 'postgresql+psycopg2://{usr}:{pwd}@{host}:{port}/{database}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION = None

    @classmethod
    def load_secrets(cls):
        secrets_path = KEY_DIR.joinpath('viktor-secretprops.properties')
        cls.SECRETS = read_secrets(secrets_path)

    @classmethod
    def build_db_engine(cls):
        """Builds database engine, sets SESSION"""
        if cls.SECRETS is None:
            cls.load_secrets()
        cls.SQLALCHEMY_DATABASE_URI = cls.SQLALCHEMY_DATABASE_URI.format(**cls.SECRETS)
        engine = create_engine(cls.SQLALCHEMY_DATABASE_URI, isolation_level='SERIALIZABLE')
        Base.metadata.bind = engine
        cls.SESSION = sessionmaker(bind=engine)


class Development(Common):
    """Configuration for development environment"""
    ENV = 'DEV'
    BOT_LAST_NAME = 'Debugnatov'
    MAIN_CHANNEL = 'C06C22027R6'  # #test
    TRIGGERS = ['biktor', 'b!']
    DEBUG = True
    USE_RELOADER = False


class Production(Common):
    """Configuration for development environment"""
    ENV = 'PROD'
    BOT_LAST_NAME = 'Produdnikov'
    MAIN_CHANNEL = 'CMEND3W3H'  # #general
    TRIGGERS = ['viktor', 'v!']
    DEBUG = False
