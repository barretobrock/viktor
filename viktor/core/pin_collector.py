from datetime import datetime
from typing import Union

from loguru import logger
import pytz
from slacktools.api.events.pin_added_or_removed import PinEvent
from slacktools.api.web.pins import PinApiObject
from sqlalchemy.engine.row import Row
from sqlalchemy.sql import (
    func,
    or_,
)

from viktor.db_eng import ViktorPSQLClient
from viktor.model import (
    TableQuote,
    TableSlackChannel,
    TableSlackUser,
)


def collect_pins(pin_obj: Union[PinEvent, PinApiObject], psql_client: ViktorPSQLClient, log: logger, is_event: bool) -> TableQuote:
    """Attempts to load pinned message into the quotes db"""
    us_ct = pytz.timezone('US/Central')
    if is_event:
        pin_obj: PinEvent
        pin_item = pin_obj.item.message
    else:
        pin_obj: PinApiObject
        pin_item = pin_obj.message
    # if pin_dict.get('message') is None:
    #     # Receiving a pin message in-prod is different than when using the historical response from /api/pin_list
    #     pin_dict = pin_dict.get('item')
    author_uid = pin_item.user
    author_name = pin_item.username
    if author_uid is None:
        # Try getting bot id
        author_uid = pin_item.bot_id

    with psql_client.session_mgr() as session:
        author = session.query(TableSlackUser).filter(or_(
            TableSlackUser.slack_user_hash == author_uid,
            TableSlackUser.slack_bot_hash == author_uid
        )).one_or_none()

        if author is None and author_uid.startswith('B') and author_name is not None:
            # Probably a bot thing. Check if the user hash begins with 'b'.
            #   If so, try to write that id to the db so next time it goes through
            author = session.query(TableSlackUser).filter(
                func.lower(TableSlackUser.real_name) == author_name.lower()
            ).one_or_none()
        if author is None:
            # If author is still none, use the unknown user
            author = session.query(TableSlackUser).filter(
                TableSlackUser.slack_bot_hash == 'BUNKNOWN'
            ).one_or_none()
        session.expunge(author)

    with psql_client.session_mgr() as session:
        pinner = session.query(TableSlackUser).filter(
            TableSlackUser.slack_user_hash == pin_obj.created_by
        ).one_or_none()
        if pinner is None:
            pinner = session.query(TableSlackUser).filter(
                TableSlackUser.slack_bot_hash == 'BUNKNOWN'
            ).one_or_none()
        session.expunge(pinner)
    log.debug('Adding pinned message to table...')

    text = pin_item.text
    files = pin_item.files
    if files is not None:
        for file in files:
            text += f'\n{file.get("url_private")}'
    if text == '':
        # Try getting attachment info
        for att in getattr(pin_item, 'attachments', []):
            text += att.get('image_url')
    log.debug(f'Passing text: "{text[:10]}"')
    with psql_client.session_mgr() as session:
        channel_key = session.query(TableSlackChannel.channel_id).filter(
            TableSlackChannel.slack_channel_hash == pin_obj.channel
        ).one_or_none()
        if isinstance(channel_key, Row):
            # Convert to id
            channel_key = next(iter(channel_key), None)
    return TableQuote(
        text=text,
        author_user_key=author.user_id,
        channel_key=channel_key,
        pinner_user_key=pinner.user_id if pinner is not None else None,
        link=pin_item.permalink,
        message_timestamp=datetime.fromtimestamp(float(pin_item.ts), us_ct),
        pin_timestamp=datetime.fromtimestamp(pin_obj.created, us_ct)
    )
