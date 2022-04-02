"""Configuration setup"""
from sqlalchemy import create_engine
from sqlalchemy.engine.url import URL
from sqlalchemy.orm import sessionmaker
from viktor._version import get_versions
from viktor.model import Base


class Common(object):
    """Configuration items common across all config types"""

    @classmethod
    def start_engine(cls, params_dict):
        cls.DB_URI = URL.create(
            drivername='postgresql+psycopg2',
            username=params_dict.get('usr'),
            password=params_dict.get('pwd'),
            host=params_dict.get('host'),
            port=params_dict.get('port'),
            database=params_dict.get('database')
        )
        cls.engine = create_engine(cls.DB_URI, isolation_level='SERIALIZABLE')
        Base.metadata.bind = cls.engine
        cls.SESSION = sessionmaker(bind=cls.engine)

    BOT_FIRST_NAME = 'Viktor Boborkdork Ivanovich'
    BOT_NICKNAME = 'viktor'
    ADMINS = ['UM35HE6R5']
    _v = get_versions()
    VERSION = _v['version']
    UPDATE_DATE = _v['date']
    DB_URI = 'postgresql+psycopg2://{usr}:{pwd}@{host}:{port}/{database}'
    engine = None

    TEST_CHANNEL = 'CM376Q90F'
    EMOJI_CHANNEL = 'CLWCPQ2TV'
    GENERAL_CHANNEL = 'CMEND3W3H'
    IMPO_CHANNEL = 'CNPADBLBF'
    CAH_CHANNEL = 'CMPV3K8AE'
    # Prevent automated activity from occurring in these channels
    DENY_LIST_CHANNELS = [IMPO_CHANNEL, CAH_CHANNEL]


class Development(Common):
    """Configuration for development environment"""
    ENV = 'DEV'
    BOT_LAST_NAME = 'Debugnatov'
    MAIN_CHANNEL = 'CM376Q90F'  # #test
    TRIGGERS = ['diktor', 'd!']
    DEBUG = True


class Production(Common):
    """Configuration for development environment"""
    ENV = 'PROD'
    BOT_LAST_NAME = 'Produdnikov'
    MAIN_CHANNEL = 'CMEND3W3H'  # #general
    TRIGGERS = ['viktor', 'v!']
    DEBUG = False
