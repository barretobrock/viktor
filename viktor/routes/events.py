from datetime import datetime
import os
from typing import TYPE_CHECKING

from flask import (
    Blueprint,
    make_response,
    request,
)
import numpy as np
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from slack_sdk.errors import SlackApiError
from slacktools.api.events.channel import (
    ChannelArchive,
    ChannelCreated,
    ChannelRename,
    ChannelUnarchive,
)
from slacktools.api.events.emoji import (
    EmojiAdded,
    EmojiRemoved,
    EmojiRenamed,
)
from slacktools.api.events.pin import (
    PinAdded,
    PinRemoved,
)
from slacktools.api.events.reaction import (
    ReactionAdded,
    ReactionRemoved,
)
from slacktools.api.web.conversations import Message
from sqlalchemy.sql import and_

from viktor.core.pin_collector import collect_pins
from viktor.core.user_changes import extract_user_change
from viktor.model import (
    TableEmoji,
    TableQuote,
    TableSlackChannel,
)
from viktor.routes.helpers import (
    get_app_bot,
    get_app_logger,
    get_viktor_eng,
)
from viktor.settings import (
    Development,
    Production,
)

if TYPE_CHECKING:
    pass

bp_events = Blueprint('events', __name__)


ENV = os.getenv('VIK_ENV')
if ENV is None:
    raise ValueError('No set env. Cannot proceed')
if ENV == 'DEV':
    env_class = Development
else:
    env_class = Production

env_class.load_secrets()
props = env_class.SECRETS
bolt_app = App(token=props['xoxb-token'], signing_secret=props['signing-secret'], process_before_response=True)
handler = SlackRequestHandler(app=bolt_app)


@bp_events.route('/api/events', methods=['GET', 'POST'])
def handle_event():
    """Handles a slack event"""
    return handler.handle(req=request)


@bolt_app.event('message')
def scan_message(ack):
    ack()
    event_data = request.json
    get_app_bot().process_event(event_data)


@bolt_app.event('channel_archive')
@bolt_app.event('channel_unarchive')
@bolt_app.event('channel_rename')
@bolt_app.event('channel_created')
def handle_channel_actions():
    event_data = request.json
    logg = get_app_logger()
    eng = get_viktor_eng()

    event_dict = event_data['event']
    event_type = event_dict['type']
    logg.debug(f'Handling channel event: {event_type}')
    match event_type:
        case 'channel_created':
            channel_obj = ChannelCreated(event_dict)
            # Add channel to db
            with eng.session_mgr() as session:
                session.add(TableSlackChannel(
                    slack_channel_hash=channel_obj.channel.id,
                    channel_name=channel_obj.channel.name
                ))
            # Join channel
            get_app_bot().st.bot.conversations_join(channel=channel_obj.channel.id)
            # Announce in channel
            get_app_bot().st.send_message(
                channel=channel_obj.channel.id,
                message='Hewwo! I\'ve joined to help catalogue and react to stuff. '
                        'I have commands to disable this if needed.')

        case 'channel_archive':
            # Mark as archived
            channel_obj = ChannelArchive(event_dict)
            with eng.session_mgr() as session:
                session.query(TableSlackChannel).\
                    filter(TableSlackChannel.slack_channel_hash == channel_obj.channel).\
                    update({
                        TableSlackChannel.is_archived: True
                    })
        case 'channel_unarchive':
            # Mark as archived
            channel_obj = ChannelUnarchive(event_dict)
            with eng.session_mgr() as session:
                session.query(TableSlackChannel). \
                    filter(TableSlackChannel.slack_channel_hash == channel_obj.channel). \
                    update({
                        TableSlackChannel.is_archived: False
                    })
                # Join channel
            get_app_bot().st.bot.conversations_join(channel=channel_obj.channel)
            # Announce in channel
            get_app_bot().st.send_message(
                channel=channel_obj.channel,
                message='Hewwo! I\'ve (re)joined to help catalogue and react to stuff. '
                        'I have commands to disable this if needed.')
        case 'channel_rename':
            # Rename channel
            channel_obj = ChannelRename(event_dict)
            with eng.session_mgr() as session:
                session.query(TableSlackChannel). \
                    filter(TableSlackChannel.slack_channel_hash == channel_obj.channel). \
                    update({
                        TableSlackChannel.channel_name: channel_obj.channel.name
                    })
            get_app_bot().st.send_message(
                channel=channel_obj.channel,
                message='Hewwo! Confirming that this rename is recorded in our scrolls'
            )


@bolt_app.event('reaction_removed')
@bolt_app.event('reaction_added')
def reaction():
    event_data = request.json
    logg = get_app_logger()
    eng = get_viktor_eng()
    static_bot = get_app_bot()

    event_dict = event_data['event']
    event_type = event_dict['type']
    if event_type == 'reaction_added':
        event_obj = ReactionAdded(event_dict)
    elif event_type == 'reaction_removed':
        event_obj = ReactionRemoved(event_dict)
    else:
        raise ValueError(f'Unhandled reaction event {event_type}')

    # This is the timestamp of the reaction
    # react_ts = event.event_ts
    # This is the timestamp of the message
    msg_ts = event_obj.item.ts
    channel = event_obj.item.channel
    current_hour = f'{datetime.now():%F %H}'
    unique_event_key = f'{channel}|{event_obj.user}|{event_type}|{msg_ts}|{current_hour}'
    if unique_event_key in get_app_bot().state_store['react-events']:
        # Event's already been processed
        logg.debug(f'Bypassing react due to preexisting event key: {unique_event_key}')
        return make_response('', 200)
    else:
        # Store new react event first
        logg.debug(f'Registering react in {channel}: {unique_event_key}')
        get_app_bot().state_store['react-events'].add(unique_event_key)

    channel_obj = eng.get_channel_from_hash(channel_hash=channel)

    if event_type == 'reaction_added':
        # Log a used react
        with eng.session_mgr() as session:
            logg.debug('Counting react in db...')
            session.query(TableEmoji).filter(TableEmoji.name == event_obj.reaction).update({
                'reaction_count': TableEmoji.reaction_count + 1
            })
            logg.debug('Determining if channel allows bot reactions')
            if channel_obj is not None and not channel_obj.is_allow_bot_react:
                logg.debug('Channel is denylisted for bot reactions. Do nothing...')
                # Channel doesn't allow reactions
                return make_response('', 200)
            if event_obj.user in [static_bot.bot_id, static_bot.user_id]:
                logg.debug('Bypassing bot react...')
                # Don't allow this infinite loop
                return make_response('', 200)
        logg.debug('Randomly selecting an emoji to react with.')
        emoji = np.random.choice(get_app_bot().state_store['reacts-store'])
        try:
            resp = get_app_bot().st.bot.reactions_add(channel=event_obj.item.channel, name=emoji, timestamp=msg_ts)
        except SlackApiError:
            logg.error(f'Removing did no succeed. Reason: {resp.get("error")}')
    elif event_type == 'reaction_removed':
        # Get available reactions from item
        resp = get_app_bot().st.bot.reactions_get(channel=channel, timestamp=msg_ts)
        msg_obj = Message(resp['message'])
        reacts = msg_obj.reactions
        if reacts is None or len(reacts) == 0:
            logg.debug('No more reacts from item. Skipping process.')
            return make_response('', 200)
        # Otherwise, let's try to select a react to remove
        react = reacts[np.random.randint(len(reacts))]
        logg.debug(f'Attempting to remove react: {react.name}')
        try:
            resp = get_app_bot().st.bot.reactions_remove(channel=channel, timestamp=msg_ts, name=react.name)
        except SlackApiError:
            logg.error(f'Removing did no succeed. Reason: {resp.get("error")}')
    return make_response('', 200)


@bolt_app.event('emoji_changed')
def record_new_emojis():
    """Make a post about a new emoji being added in the #emoji_suggestions channel"""
    event_data = request.json
    event_dict = event_data['event']
    logg = get_app_logger()
    eng = get_viktor_eng()
    logg.debug(f'Emoji change detected: {event_dict["subtype"]}')
    match event_dict['subtype']:
        case 'add':
            event_obj = EmojiAdded(event_dict)
            logg.debug('Attempting to add new emoji')
            with eng.session_mgr() as session:
                session.add(TableEmoji(name=event_obj.name))
        case 'rename':
            event_obj = EmojiRenamed(event_dict)
            logg.debug('Attempting to rename an emoji.')
            with eng.session_mgr() as session:
                session.query(TableEmoji).filter(TableEmoji.name == event_obj.old_name).\
                    update({'name': event_obj.new_name})
        case 'remove':
            event_obj = EmojiRemoved(event_dict)
            logg.debug('Attempting to remove an emoji')
            with eng.session_mgr() as session:
                session.query(TableEmoji).filter(TableEmoji.name.in_(event_obj.names)).update({'is_deleted': True})


@bolt_app.event('pin_added')
def store_pins():
    event_data = request.json
    logg = get_app_logger()
    eng = get_viktor_eng()

    pin_obj = PinAdded(event_dict=event_data['event'])
    tbl_obj = collect_pins(pin_obj=pin_obj, psql_client=eng, log=logg, is_event=True)
    # Add to db
    with eng.session_mgr() as session:
        matches = session.query(TableQuote).filter(and_(
            TableQuote.message_timestamp == tbl_obj.message_timestamp,
            TableQuote.link == tbl_obj.link
        )).all()
        if len(matches) == 0:
            logg.debug('No duplicates found for item - proceeding with pin')
            session.add(tbl_obj)
            msg = 'Pin successfully added, kommanderovnik o7'
        else:
            logg.debug(f'{len(matches)} quote item(s) with duplicate link and message timestamp found '
                       f'- aborting pin')
            msg = 'o7 KOMMANDEROVNIK! ...pin... was not added...  I... have failed you.'

    get_app_bot().st.send_message(channel=pin_obj.channel_id, message=msg)


@bolt_app.event('pin_removed')
def remove_pins():
    event_data = request.json
    logg = get_app_logger()
    eng = get_viktor_eng()
    pin_obj = PinRemoved(event_dict=event_data['event'])
    tbl_obj = collect_pins(pin_obj=pin_obj, psql_client=eng, log=logg, is_event=True)
    # Add to db
    with eng.session_mgr() as session:
        session.query(TableQuote).filter(and_(
            TableQuote.message_timestamp == tbl_obj.message_timestamp,
            TableQuote.link == tbl_obj.link
        )).update({TableQuote.is_deleted: True})

    get_app_bot().st.send_message(channel=pin_obj.channel_id,
                                  message='Pin successfully removed, kommanderovnik o7')


@bolt_app.event('user_change')
def notify_new_statuses():
    """Triggered when a user updates their profile info. Gets saved to global dict
    where we then report it in #general"""
    event_data = request.json
    event = event_data['event']
    user_info = event['user']
    logg = get_app_logger()
    eng = get_viktor_eng()

    extract_user_change(eng=eng, user_info_dict=user_info, log=logg)
