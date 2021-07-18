import json
import signal
import requests
from datetime import datetime, timedelta
from random import choice
from flask import Flask, request, make_response
from flask_sqlalchemy import SQLAlchemy
from slacktools import SlackEventAdapter, SecretStore, BlockKitBuilder as bkb
from easylogger import Log
import viktor.bot_base as botbase
from .model import TableEmojis, TableUsers, TableResponses, ResponseTypes
from .settings import auto_config
from .utils import collect_pins

bot_name = auto_config.BOT_NICKNAME
logg = Log(bot_name, log_to_file=True)

credstore = SecretStore('secretprops-bobdev.kdbx')
vik_creds = credstore.get_key_and_make_ns(bot_name)

logg.debug('Starting up app...')
# Include a means of halting duplicate requests from being handled
#   until I can figure out a better async protocol
message_limits = {}  # date, count
logg.debug('Building user list')
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = auto_config.DB_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

logg.debug('Instantiating bot...')
Bot = botbase.Viktor(parent_log=logg)
RESPONSES = [x.text for x in
             db.session.query(TableResponses).filter(TableResponses.type == ResponseTypes.general).all()]

# Register the cleanup function as a signal handler
signal.signal(signal.SIGINT, Bot.cleanup)
signal.signal(signal.SIGTERM, Bot.cleanup)

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
        'text': choice(RESPONSES)
    }
    if event_data.get('container', {'is_ephemeral': False}).get('is_ephemeral', False):
        update_dict['response_type'] = 'ephemeral'
    response_url = event_data.get('response_url')
    if response_url is not None:
        # Update original message
        if 'shortcut' not in action.get('type'):
            resp = requests.post(event_data['response_url'], json=update_dict,
                                 headers={'Content-Type': 'application/json'})

    # Send HTTP 200 response with an empty body so Slack knows we're done
    return make_response('', 200)


@app.route("/cron/new_emojis", methods=['POST'])
def handle_cron_new_emojis():
    """Check for newly uploaded emojis (triggered by cron task that sends POST req every 10 mins)"""
    # Check emojis uploaded (every 60 mins)
    # This url is hit in crontab as such:
    #       0 * * * * /usr/bin/curl -X POST https://YOUR_APP/cron/new_emojis
    now = datetime.utcnow()
    interval = (now - timedelta(minutes=60))
    new_emojis = db.session.query(TableEmojis).filter(TableEmojis.created_date > interval).all()
    if len(new_emojis) > 0:
        # Go about notifying channel of newly uploaded emojis
        emojis = [f':{x.name}:' for x in new_emojis]
        emoji_str = ''
        for i in range(0, len(emojis), 10):
            emoji_str += f"{''.join(emojis[i:i + 10])}\n"
        msg_block = [
            bkb.make_context_section([
                bkb.markdown_section('Incoming emojis that were added in the last 60 min!')
            ]),
        ]
        Bot.st.send_message(Bot.emoji_channel, 'new emoji report', blocks=msg_block)
        Bot.st.send_message(Bot.emoji_channel, emoji_str)
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


@app.route("/cron/reacts", methods=['POST'])
def handle_cron_reacts():
    """Check for new reactions - if any, run through and react to them"""
    # Check emojis uploaded (every 60 mins)
    # This url is hit in crontab as such:
    #       0 * * * * /usr/bin/curl -X POST https://YOUR_APP/cron/reacts
    logg.debug('Handling recent reacts...')
    reacts = Bot.state_store.get('reacts', {})
    if len(reacts) > 0:
        # Begin reacting to new reactions
        logg.debug(f'{len(reacts)} reacts found.')
        emojis = Bot.emoji_list
        for item in Bot.state_store.get('reacts'):
            logg.debug(f'Channel|timestamp: {item}')
            chan, ts = item.split('|')
            Bot.bot.reactions_add(name=choice(emojis), channel=chan, timestamp=ts)
        # Reset the reacts
        Bot.state_store['reacts'] = {}
    return make_response('', 200)


@bot_events.on('reaction_added')
def reaction(event_data: dict):
    event = event_data['event']
    channel = event['item']['channel']
    if channel in auto_config.DENY_LIST_CHANNELS:
        logg.debug(f'Bypassing react in denylisted channel.')
        return
    if event['user'] not in [Bot.bot_id, Bot.user_id]:
        # Keep from reacting to own reaction
        logg.debug(f'Registering react in {channel}')
        try:
            Bot.state_store['reacts'].add(f'{channel}|{event["item"]["ts"]}')
        except Exception as e:
            # Sometimes we'll get a 'too_many_reactions' error. Disregard in that case
            pass


@bot_events.on('message')
def scan_message(event_data: dict):
    Bot.process_event(event_data)


@app.route('/api/slash', methods=['GET', 'POST'])
def handle_slash():
    """Handles a slash command"""
    event_data = request.form
    # Handle the command
    Bot.process_slash_command(event_data)

    # Send HTTP 200 response with an empty body so Slack knows we're done
    return make_response('', 200)


@bot_events.on('emoji_changed')
def notify_new_emojis(event_data):
    event = event_data['event']
    # Make a post about a new emoji being added in the #emoji_suggestions channel
    if event['subtype'] == 'add':
        emoji = event['name']
        db.session.add(TableEmojis(name=emoji))
        db.session.commit()


@bot_events.on('pin_added')
def store_pins(event_data):
    event = event_data['event']
    tbl_obj = collect_pins(event, session=db.session, log=logg)
    # Add to db
    db.session.add(tbl_obj)
    db.session.commit()
    Bot.st.send_message(channel=event['channel_id'], message='Pin successfully added, kommanderovnik o7')


@bot_events.on('user_change')
def notify_new_statuses(event_data):
    """Triggered when a user updates their profile info. Gets saved to global dict
    where we then report it in #general"""
    event = event_data['event']
    user_info = event['user']
    uid = user_info['id']
    # Look up user in db
    user = db.session.query(TableUsers).filter(TableUsers.slack_id == uid).one_or_none()
    if user is not None:
        # get display name
        profile = user_info.get('profile')
        dis_name = profile.get('display_name') if profile.get('display_name') != '' else profile.get('real_name')
        if user.name != dis_name:
            # update the table
            user.name = dis_name
            db.session.commit()
            logg.debug(f'Name {dis_name} updated in db...')
    # if uid in Bot.users_dict.keys():
    #     # Get what info we've already stored on the user
    #     current_user_dict = Bot.users_dict[uid]
    #     # Get the user's newly updated dict
    #     new_user_dict = Bot.st.clean_user_info(user_info)
    #
    #     # Add updated to our updates dict
    #     Bot.user_updates_dict[uid] = {k: v for k, v in zip(['old', 'new'], [current_user_dict, new_user_dict])}
