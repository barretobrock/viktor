from datetime import datetime
from typing import TYPE_CHECKING

from flask import (
    Blueprint,
    make_response,
    request,
)
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler

from viktor.routes.helpers import (
    get_app_bot,
    get_app_logger,
    get_viktor_eng,
)
from viktor.settings import Production
from viktor.core.pin_collector import collect_pins
from viktor.core.user_changes import extract_user_change

if TYPE_CHECKING:
    pass

bp_events = Blueprint('events', __name__)


Production.load_secrets()
props = Production.SECRETS
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


@bolt_app.event('reaction_added')
def reaction(ack):
    ack()
    event_data = request.json
    logg = get_app_logger()
    eng = get_viktor_eng()

    # TODO: This below should be in a method

    event = ReactionEvent(event_data['event'])

    # This is the timestamp of the reaction
    # react_ts = event.event_ts
    # This is the timestamp of the message
    msg_ts = event.item.ts
    unique_event_key = f'{event.item.channel}|{event.user}|{msg_ts}|{datetime.now():%F %H}'
    if unique_event_key in get_app_bot().state_store['reacts']:
        # Event's already been processed
        logg.debug(f'Bypassing react to preexisting event key: {unique_event_key}')
        return make_response('', 200)
    else:
        # Store new react event first
        logg.debug(f'Registering react in {event.item.channel}: {unique_event_key}')
        get_app_bot().state_store['reacts'].add(unique_event_key)

    channel_obj = eng.get_channel_from_hash(channel_hash=event.item.channel)

    with eng.session_mgr() as session:
        logg.debug('Counting react in db...')
        session.query(TableEmoji).filter(TableEmoji.name == event.reaction).update({
            'reaction_count': TableEmoji.reaction_count + 1
        })
        logg.debug('Determining if channel allows bot reactions')
        if channel_obj is not None and not channel_obj.is_allow_bot_react:
            logg.debug('Channel is denylisted for bot reactions. Do nothing...')
            # Channel doesn't allow reactions
            return make_response('', 200)
    if event.user in [Bot.bot_id, Bot.user_id]:
        logg.debug('Bypassing bot react...')
        # Don't allow this infinite loop
        return make_response('', 200)

    try:
        with eng.session_mgr() as session:
            logg.debug('Randomly selecting an emoji to react with.')
            emoji = session.query(TableEmoji).filter(not_(TableEmoji.is_react_denylisted)).\
                order_by(func.random()).limit(1).one()
            _ = get_app_bot().st.bot.reactions_add(channel=event.item.channel, name=emoji.name, timestamp=msg_ts)
        return make_response('', 200)
    except Exception:
        # Sometimes we'll get a 'too_many_reactions' error. Disregard in that case
        pass


@bolt_app.event('emoji_changed')
def record_new_emojis(ack):
    """Make a post about a new emoji being added in the #emoji_suggestions channel"""
    ack()
    event_data = request.json
    # TODO: This below should be in a method
    logg = get_app_logger()
    event = decide_emoji_event_class(event_dict=event_data['event'])
    logg.debug(f'Emoji change detected: {event.subtype}')
    match event.subtype:
        case 'add':
            event: EmojiAdded
            logg.debug('Attempting to add new emoji')
            with eng.session_mgr() as session:
                session.add(TableEmoji(name=event.name))
        case 'rename':
            event: EmojiRenamed
            logg.debug('Attempting to rename an emoji.')
            with eng.session_mgr() as session:
                session.query(TableEmoji).filter(TableEmoji.name == event.old_name).update({'name': event.new_name})
        case 'remove':
            event: EmojiRemoved
            logg.debug('Attempting to remove an emoji')
            with eng.session_mgr() as session:
                session.query(TableEmoji).filter(TableEmoji.name.in_(event.names)).update({'is_deleted': True})


@bolt_app.event('pin_added')
def store_pins(ack):
    ack()
    event_data = request.json
    logg = get_app_logger()
    eng = get_viktor_eng()

    pin_obj = PinEvent(event_dict=event_data['event'])
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

    get_app_bot().st.send_message(channel=pin_obj.item.message.channel, message=msg)


@bolt_app.event('pin_removed')
def remove_pins(ack):
    ack()
    event_data = request.json
    pin_obj = PinEvent(event_dict=event_data['event'])
    tbl_obj = collect_pins(pin_obj=pin_obj, psql_client=eng, log=logg, is_event=True)
    # Add to db
    with eng.session_mgr() as session:
        session.query(TableQuote).filter(and_(
            TableQuote.message_timestamp == tbl_obj.message_timestamp,
            TableQuote.link == tbl_obj.link
        )).update({TableQuote.is_deleted: True})

    get_app_bot().st.send_message(channel=pin_obj.item.message.channel,
                                  message='Pin successfully removed, kommanderovnik o7')


@bolt_app.event('user_change')
def notify_new_statuses(ack):
    """Triggered when a user updates their profile info. Gets saved to global dict
    where we then report it in #general"""
    ack()
    event_data = request.json
    event = event_data['event']
    user_info = event['user']
    logg = get_app_logger()
    eng = get_viktor_eng()

    extract_user_change(eng=eng, user_info_dict=user_info, log=logg)


