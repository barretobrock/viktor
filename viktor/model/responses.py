import enum
from sqlalchemy import Column, Integer, TEXT, Enum
# local imports
from .base import Base


class ResponseTypes(enum.Enum):
    stakeholder = 'stakeholder'
    general = 'general'
    sarcastic = 'sarcastic'
    jackhandey = 'jackhandey'


class TableResponses(Base):
    """response table - stores various responses"""
    __tablename__ = 'responses'

    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(Enum(ResponseTypes), default=ResponseTypes.general, nullable=False)
    text = Column(TEXT, nullable=False)


class InsultTypes(enum.Enum):
    standard = 'standard'
    work = 'work'


class TableInsults(Base):
    """response table - stores various responses"""
    __tablename__ = 'insults'

    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(Enum(InsultTypes), default=InsultTypes.standard, nullable=False)
    stage = Column(Integer, nullable=False)
    text = Column(TEXT, nullable=False)


class ComplimentTypes(enum.Enum):
    standard = 'standard'
    work = 'work'


class TableCompliments(Base):
    """response table - stores various responses"""
    __tablename__ = 'compliments'

    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(Enum(ComplimentTypes), default=ComplimentTypes.standard, nullable=False)
    stage = Column(Integer, nullable=False)
    text = Column(TEXT, nullable=False)


class PhraseTypes(enum.Enum):
    standard = 'standard'
    work = 'work'


class TablePhrases(Base):
    """response table - stores various responses"""
    __tablename__ = 'phrases'

    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(Enum(PhraseTypes), default=PhraseTypes.standard, nullable=False)
    stage = Column(Integer, nullable=False)
    text = Column(TEXT, nullable=False)


class FactTypes(enum.Enum):
    standard = 'standard'
    conspiracy = 'conspiracy'


class TableFacts(Base):
    """response table - stores various responses"""
    __tablename__ = 'facts'

    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(Enum(FactTypes), default=FactTypes.standard, nullable=False)
    text = Column(TEXT, nullable=False)
