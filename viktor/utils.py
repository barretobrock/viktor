from datetime import datetime
import pytz
from typing import Dict
from sqlalchemy.orm import Session
from easylogger import Log
from .model import TableUsers, TableQuotes


def collect_pins(pin_dict: Dict, session: Session, log: Log) -> TableQuotes:
    """Attempts to load pinned message into the quotes db"""
    if pin_dict.get('message') is None:
        # Receiving a pin message in-prod is different than when using the historical response from /api/pin_list
        pin_dict = pin_dict.get('item')
    author_sid = pin_dict.get('message').get('user')
    author_name = pin_dict.get('message').get('username')
    if author_sid is None:
        # Try getting bot id
        author_sid = pin_dict.get('message').get('bot_id')
    author = session.query(TableUsers).filter(TableUsers.slack_id == author_sid).one_or_none()
    if author is None:
        # Most probably because it's slackbot. Add user to table
        log.debug(f'Author not found in user table. Adding: {author_sid}')
        author_name = 'UNKNOWN' if author_name is None else author_name
        session.add(TableUsers(slack_id=author_sid, name=author_name))
        session.commit()
        author = session.query(TableUsers).filter(TableUsers.slack_id == author_sid).one_or_none()
    pinner = session.query(TableUsers).filter(TableUsers.slack_id == pin_dict.get('created_by')).one_or_none()
    log.debug('Adding pinned message to table...')

    text = pin_dict.get('message').get('text')
    files = pin_dict.get('message').get('files')
    if files is not None:
        for file in files:
            text += f'\n{file.get("url_private")}'
    if text == '':
        # Try getting attachment info
        for att in pin_dict.get('message').get('attachments'):
            text += att.get('image_url')
    log.debug(f'Passing text: "{text[:10]}"')
    return TableQuotes(
        author=author.id,
        channel=pin_dict.get('channel'),
        pinner=pinner.id,
        text=text,
        link=pin_dict.get('message').get('permalink'),
        message_date=datetime.fromtimestamp(float(pin_dict.get('message').get('ts')),
                                            pytz.timezone('US/Central')),
        pin_date=datetime.fromtimestamp(pin_dict.get('created'), pytz.timezone('US/Central'))
    )
