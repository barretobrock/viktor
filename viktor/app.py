from datetime import datetime
import json
import signal

from flask import (
    Flask,
    make_response,
    request,
)
import requests
from slackeventsapi import SlackEventAdapter
from slacktools.secretstore import SecretStore
from sqlalchemy.sql import (
    and_,
    func,
    not_,
)

from viktor.bot_base import Viktor
from viktor.core.pin_collector import collect_pins
from viktor.core.user_changes import extract_user_change
from viktor.crons import cron
from viktor.db_eng import ViktorPSQLClient
from viktor.logg import get_base_logger
from viktor.model import (
    TableEmoji,
    TableQuote,
)
from viktor.settings import auto_config

bot_name = auto_config.BOT_NICKNAME
logg = get_base_logger()

credstore = SecretStore('secretprops-davaiops.kdbx')
# Set up database connection
conn_dict = credstore.get_entry(f'davaidb-{auto_config.ENV.lower()}').custom_properties
vik_creds = credstore.get_key_and_make_ns(bot_name)

logg.debug('Starting up app...')
app = Flask(__name__)
app.register_blueprint(cron, url_prefix='/cron')

eng = ViktorPSQLClient(props=conn_dict, parent_log=logg)

logg.debug('Instantiating bot...')
Bot = Viktor(eng=eng, bot_cred_entry=vik_creds, parent_log=logg)

# Register the cleanup function as a signal handler
signal.signal(signal.SIGINT, Bot.cleanup)
signal.signal(signal.SIGTERM, Bot.cleanup)

# Events API listener
bot_events = SlackEventAdapter(vik_creds.signing_secret, "/api/events", app)


@app.route('/api/actions', methods=['GET', 'POST'])
@logg.catch
def handle_action():
    """Handle a response when a user clicks a button from a form Slack"""
    event_data = json.loads(request.form["payload"])
    user = event_data['user']['id']
    # if channel empty, it's a shortcut
    if event_data.get('channel') is None:
        # shortcut - grab callback, put in action dict according to expected ac
        action = {
            'action_id': event_data.get('callback_id'),
            'action_value': '',
            'type': 'shortcut'
        }
        channel = auto_config.MAIN_CHANNEL
    elif event_data.get('actions') is None:
        # Most likely a 'message-shortcut' (e.g., from message menu)
        action = {
            'action_id': event_data.get('callback_id'),
            'action_value': '',
            'type': 'message-shortcut'
        }
        channel = auto_config.MAIN_CHANNEL
    else:
        # Action from button click, etc...
        channel = event_data['channel']['id']
        actions = event_data['actions']
        # Not sure if we'll ever receive more than one action?
        action = actions[0]
    # Send that info onwards to determine how to deal with it
    Bot.process_incoming_action(user, channel, action_dict=action, event_dict=event_data)

    # Respond to the initial message and update it
    update_dict = {
        'replace_original': True,
        'text': 'boop boop...beep?'
    }
    if event_data.get('container', {'is_ephemeral': False}).get('is_ephemeral', False):
        update_dict['response_type'] = 'ephemeral'
    response_url = event_data.get('response_url')
    if response_url is not None:
        # Update original message
        if 'shortcut' not in action.get('type'):
            _ = requests.post(event_data['response_url'], json=update_dict,
                              headers={'Content-Type': 'application/json'})

    # Send HTTP 200 response with an empty body so Slack knows we're done
    return make_response('', 200)


@bot_events.on('reaction_added')
@logg.catch
def reaction(event_data: dict):
    event = event_data['event']
    user = event.get('user')
    item = event.get('item')
    channel = item.get('channel')
    reaction_emoji = event.get('reaction')
    # This is the timestamp of the reaction
    # react_ts = event.get('event_ts')
    # This is the timestamp of the message
    msg_ts = item.get('ts')
    unique_event_key = f'{channel}|{user}|{msg_ts}|{datetime.now():%F %H}'
    if unique_event_key in Bot.state_store['reacts']:
        # Event's already been processed
        logg.debug(f'Bypassing react to preexisting event key: {unique_event_key}')
        return make_response('', 200)
    else:
        # Store new react event first
        logg.debug(f'Registering react in {channel}: {unique_event_key}')
        Bot.state_store['reacts'].add(unique_event_key)

    channel_obj = eng.get_channel_from_hash(channel_hash=channel)

    with eng.session_mgr() as session:
        logg.debug('Counting react in db...')
        session.query(TableEmoji).filter(TableEmoji.name == reaction_emoji).update({
            'reaction_count': TableEmoji.reaction_count + 1
        })
        logg.debug('Determining if channel allows bot reactions')
        if channel_obj is not None and not channel_obj.is_allow_bot_react:
            logg.debug('Channel is denylisted for bot reactions. Do nothing...')
            # Channel doesn't allow reactions
            return make_response('', 200)
    if user in [Bot.bot_id, Bot.user_id]:
        logg.debug('Bypassing bot react...')
        # Don't allow this infinite loop
        return make_response('', 200)

    try:
        with eng.session_mgr() as session:
            logg.debug('Randomly selecting an emoji to react with.')
            emoji = session.query(TableEmoji).filter(not_(TableEmoji.is_react_denylisted)).\
                order_by(func.random()).limit(1).one()
            _ = Bot.st.bot.reactions_add(channel=channel, name=emoji.name, timestamp=msg_ts)
        return make_response('', 200)
    except Exception:
        # Sometimes we'll get a 'too_many_reactions' error. Disregard in that case
        pass


@bot_events.on('message')
@logg.catch
def scan_message(event_data: dict):
    Bot.process_event(event_data)


@app.route('/api/slash', methods=['GET', 'POST'])
@logg.catch
def handle_slash():
    """Handles a slash command"""
    event_data = request.form
    # Handle the command
    Bot.process_slash_command(event_data)

    # Send HTTP 200 response with an empty body so Slack knows we're done
    return make_response('', 200)


@bot_events.on('emoji_changed')
@logg.catch
def record_new_emojis(event_data):
    event = event_data['event']
    # Make a post about a new emoji being added in the #emoji_suggestions channel
    event_subtype = event['subtype']
    logg.debug(f'Emoji change detected: {event_subtype}')
    if event_subtype == 'add':
        logg.debug('Attempting to add new emoji')
        emoji = event['name']
        with eng.session_mgr() as session:
            session.add(TableEmoji(name=emoji))
    elif event_subtype == 'rename':
        logg.debug('Attempting to rename an emoji.')
        emoji = event['old_name']
        new_name = event['new_name']
        with eng.session_mgr() as session:
            session.query(TableEmoji).filter(TableEmoji.name == emoji).update({'name': new_name})
    elif event_subtype == 'remove':
        logg.debug('Attempting to remove an emoji')
        # For some reason, this gets passed as a list, so we'll name it accordingly
        emojis = event['names']
        with eng.session_mgr() as session:
            session.query(TableEmoji).filter(TableEmoji.name.in_(emojis)).update({'is_deleted': True})


@bot_events.on('pin_added')
@logg.catch
def store_pins(event_data):
    event = event_data['event']
    tbl_obj = collect_pins(event, psql_client=eng, log=logg)
    # Add to db
    with eng.session_mgr() as session:
        session.add(tbl_obj)

    Bot.st.send_message(channel=event['channel_id'], message='Pin successfully added, kommanderovnik o7')


@bot_events.on('pin_removed')
@logg.catch
def remove_pins(event_data):
    event = event_data['event']
    tbl_obj = collect_pins(event, psql_client=eng, log=logg)
    # Add to db
    with eng.session_mgr() as session:
        session.query(TableQuote).filter(and_(
            TableQuote.message_timestamp == tbl_obj.message_timestamp,
            TableQuote.link == tbl_obj.link
        )).update({TableQuote.is_deleted: True})

    Bot.st.send_message(channel=event['channel_id'], message='Pin successfully removed, kommanderovnik o7')


@bot_events.on('user_change')
@logg.catch
def notify_new_statuses(event_data):
    """Triggered when a user updates their profile info. Gets saved to global dict
    where we then report it in #general"""
    event = event_data['event']
    user_info = event['user']
    extract_user_change(eng=eng, user_info_dict=user_info, log=logg)
