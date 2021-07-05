from sqlalchemy import Column, VARCHAR, Integer, Float, TEXT, TIMESTAMP
from sqlalchemy.sql import func
# local imports
from .base import Base


class TableUsers(Base):
    """users table"""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    slack_id = Column(VARCHAR(50), nullable=False, unique=True)
    name = Column(VARCHAR(80), nullable=False)
    role = Column(VARCHAR)
    role_desc = Column(TEXT)
    level = Column(Float(5), default=0, nullable=False)
    ltits = Column(Float(5), default=0, nullable=False)
    updated_date = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    created_date = Column(TIMESTAMP, server_default=func.now())
