import json
import signal
import requests
import sqlite3
from random import randint, choice
from flask import Flask, request, make_response
from slacktools import SlackEventAdapter, SecretStore, BlockKitBuilder as bkb
from easylogger import Log
import viktor.bot_base as botbase
from .model import TableEmojis
from .settings import auto_config


bot_name = auto_config.BOT_NICKNAME
logg = Log(bot_name, log_to_file=True)
# This is basically a session maker. We'll use it to ensure that sessions stay independent and short-lived
#   while also not having them become an encumbrance to the state of the code
Session = auto_config.SESSION

credstore = SecretStore('secretprops-bobdev.kdbx')
vik_creds = credstore.get_key_and_make_ns(bot_name)

logg.debug('Instantiating bot...')
Bot = botbase.Viktor(parent_log=logg, session=Session())

# Register the cleanup function as a signal handler
signal.signal(signal.SIGINT, Bot.cleanup)
signal.signal(signal.SIGTERM, Bot.cleanup)

# Include a means of halting duplicate requests from being handled
#   until I can figure out a better async protocol
message_events = []
emoji_events = []
user_events = []
action_timestamps = []
message_limits = {}  # date, count
logg.debug('Building user list')
app = Flask(__name__)

# Events API listener
bot_events = SlackEventAdapter(vik_creds.signing_secret, "/api/events", app)


@app.route('/api/actions', methods=['GET', 'POST'])
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
    else:
        # Action from button click, etc...
        channel = event_data['channel']['id']
        actions = event_data['actions']
        # Not sure if we'll ever receive more than one action?
        action = actions[0]
    # Send that info onwards to determine how to deal with it
    Bot.process_incoming_action(user, channel, action_dict=action, event_dict=event_data, session=Session())

    # Respond to the initial message and update it
    responses = [
        'Thanks, shithead!',
        'Good job, you did a thing!',
        'Look at you, doing things and shit!',
        'Hey, you\'re a real pal!',
        'Thanks, I guess...'
    ]
    update_dict = {
        'replace_original': True,
        'text': choice(responses)
    }
    if event_data.get('container', {'is_ephemeral': False}).get('is_ephemeral', False):
        update_dict['response_type'] = 'ephemeral'
    response_url = event_data.get('response_url')
    if response_url is not None:
        # Update original message
        resp = requests.post(event_data['response_url'], json=update_dict,
                             headers={'Content-Type': 'application/json'})

    # Send HTTP 200 response with an empty body so Slack knows we're done
    return make_response('', 200)


@app.route("/cron/new_emojis", methods=['POST'])
def handle_cron_new_emojis():
    """Check for newly uploaded emojis (triggered by cron task that sends POST req every 10 mins)"""
    # Check emojis uploaded (every 10 mins)
    if len(Bot.new_emoji_set) > 0:
        # Go about notifying channel of newly uploaded emojis
        emojis = [f':{x}:' for x in list(Bot.new_emoji_set)]
        emoji_str = ''
        for i in range(0, len(emojis), 10):
            emoji_str += f"{''.join(emojis[i:i + 10])}\n"
        msg_block = [
            bkb.make_context_section('Incoming emojis that were added in the last 10 min!'),
        ]
        Bot.st.send_message(Bot.emoji_channel, '', blocks=msg_block)
        Bot.st.send_message(Bot.emoji_channel, emoji_str)
        # Reset list of added emojis to an empty set
        Bot.new_emoji_set = set()

    return make_response('', 200)


@app.route("/cron/profile_update", methods=['POST'])
def handle_cron_profile_update():
    """Check for newly updated profile elements (triggered by cron task that sends POST req every 10 mins)"""
    # Check updated profile (every 10 mins)
    # if len(Bot.user_updates_dict) > 0:
    #     # Go about notifying channel of newly uploaded emojis
    #     for uid, change_dict in Bot.user_updates_dict.items():
    #         # we'll currently report on avatar, display name, name, title and status changes.
    #         changes_txt = '*`{display_name}`*\t\t*`{real_name}`*\n:q:{title}:q:\n{status_emoji} {status_text}'
    #         msg_block = [
    #             bkb.make_context_section(f'<@{uid}> changed their profile info recently!'),
    #             bkb.make_block_divider()
    #         ]
    #         # Process new/old data
    #         for data in ['old', 'new']:
    #             transition = 'from' if data == 'old' else 'to'
    #             avi_url = change_dict[data]['avi']
    #             avi_alt = f'{transition} pic'
    #             msg_block += [
    #                 bkb.make_context_section(f'{transition} this...'),
    #                 bkb.make_block_section(changes_txt.format(**change_dict[data]),
    #                                        accessory=bkb.make_image_accessory(avi_url, avi_alt))
    #             ]
    #
    #         Bot.st.send_message(Bot.general_channel, '', blocks=msg_block)
    #         # Make sure the current dict is then updated to reflect changes we've reported
    #         Bot.users_dict[uid] = change_dict['new']
    #     # Reset dict of user profile changes to an empty dict
    #     Bot.user_updates_dict = {}

    return make_response('', 200)


@bot_events.on('reaction_added')
def reaction(event_data: dict):
    session = Session()
    event = event_data['event']
    if event['user'] not in [Bot.bot_id, Bot.user_id]:
        # Keep from reacting to own reaction
        emojis = session.query(TableEmojis).all()
        random_emoji = emojis[randint(0, len(emojis))]
        try:
            Bot.bot.reactions_add(
                name=random_emoji.name,
                channel=event['item']['channel'],
                timestamp=event['item']['ts']
            )
        except Exception as e:
            # Sometimes we'll get a 'too_many_reactions' error. Disregard in that case
            pass


@bot_events.on('message')
def scan_message(event_data: dict):
    session = Session()
    try:
        Bot.process_event(event_data, session=session)
    except sqlite3.ProgrammingError:
        session.rollback()
    # if event_data['event']['user'] == 'UM35HE6R5':
    #     today = f'{datetime.now():%F}'
    #     if today in message_limits.keys():
    #         if message_limits[today] >= 3:
    #             # Bot.st.delete_message(event_data['event'])
    #             Bot.st.user.chat_delete(
    #                 channel=event_data['event']['channel'],
    #                 ts=event_data['event']['ts']
    #             )
    #         else:
    #             message_limits[today] += 1
    #     else:
    #         message_limits[today] = 1


@app.route('/api/slash', methods=['GET', 'POST'])
def handle_slash():
    """Handles a slash command"""
    event_data = request.form
    # Handle the command
    Bot.process_slash_command(event_data, Session())

    # Send HTTP 200 response with an empty body so Slack knows we're done
    return make_response('', 200)


@bot_events.on('emoji_changed')
def notify_new_emojis(event_data):
    session = Session()
    event = event_data['event']
    # Make a post about a new emoji being added in the #emoji_suggestions channel
    if event['subtype'] == 'add':
        emoji = event['name']
        session.add(TableEmojis(name=emoji))


@bot_events.on('user_change')
def notify_new_statuses(event_data):
    """Triggered when a user updates their profile info. Gets saved to global dict
    where we then report it in #general"""
    event = event_data['event']
    user_info = event['user']
    uid = user_info['id']
    # if uid in Bot.users_dict.keys():
    #     # Get what info we've already stored on the user
    #     current_user_dict = Bot.users_dict[uid]
    #     # Get the user's newly updated dict
    #     new_user_dict = Bot.st.clean_user_info(user_info)
    #
    #     # Add updated to our updates dict
    #     Bot.user_updates_dict[uid] = {k: v for k, v in zip(['old', 'new'], [current_user_dict, new_user_dict])}
