from datetime import datetime
from typing import Union
from zoneinfo import ZoneInfo

from loguru import logger
from slacktools.api.events.pin import (
    PinAdded,
    PinRemoved,
)
from slacktools.api.web.pins import Pin
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


def collect_pins(pin_obj: Union[PinAdded, PinRemoved, Pin], psql_client: ViktorPSQLClient, log: logger,
                 is_event: bool) -> TableQuote:
    """Attempts to load pinned message into the quotes db"""
    us_ct = ZoneInfo('US/Central')
    if is_event:
        pin_obj: Union[PinAdded, PinRemoved]
        pin_item = pin_obj.item.message
        pin_ts = pin_obj.event_ts
        author_name = pin_item.username
        channel_id = pin_obj.channel_id
    else:
        pin_obj: Pin
        pin_item = pin_obj.message
        pin_ts = pin_obj.created
        author_name = None
        channel_id = pin_obj.channel
    try:
        author_uid = pin_item.user
    except AttributeError:
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

    # Try getting file info
    file_urls_list = []
    for att in getattr(pin_item, 'files', []):
        try:
            pvt_url = getattr(att, 'url_private')
        except AttributeError:
            continue
        if pvt_url is not None:
            file_urls_list.append(pvt_url)

    # Try getting attachment info
    img_urls_list = []
    for att in getattr(pin_item, 'attachments', []):
        try:
            img_url = getattr(att, 'image_url')
        except AttributeError:
            continue
        if img_url is not None:
            img_urls_list.append(img_url)

    log.debug(f'Passing text: "{text[:10]}"')
    with psql_client.session_mgr() as session:
        channel_key = session.query(TableSlackChannel.channel_id).filter(
            TableSlackChannel.slack_channel_hash == channel_id
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
        image_urls=img_urls_list,
        file_urls=file_urls_list,
        message_timestamp=datetime.fromtimestamp(float(pin_item.ts), us_ct),
        pin_timestamp=datetime.fromtimestamp(float(pin_ts), us_ct)
    )
