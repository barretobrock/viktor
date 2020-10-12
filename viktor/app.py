import os
import json
import signal
import requests
from random import randint
from flask import Flask, request, make_response
from slacktools import SlackEventAdapter
from kavalkilu import Path, Log
from .utils import Viktor


bot_name = 'viktor'
DEBUG = os.environ['VIKTOR_DEBUG'] == '1'
kpath = Path()
logg = Log(bot_name, arg_parse=False)

key_path = kpath.easy_joiner(kpath.keys_dir, f'{bot_name.upper()}_SLACK_KEYS.json')
with open(key_path) as f:
    key_dict = json.loads(f.read())
logg.debug('Instantiating bot...')
Bot = Viktor(bot_name, creds=key_dict, debug=DEBUG)

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
users_list = Bot.st.get_channel_members('CLWCPQ2TV')  # get users in general
app = Flask(__name__)

# Events API listener
bot_events = SlackEventAdapter(key_dict['signing-secret'], "/viktor/vikapi/events", app)


@app.route('/viktor/vikapi/slash', methods=['GET', 'POST'])
def handle_slash():
    """Handles a slash command"""
    event_data = request.form
    # Handle the command
    Bot.st.parse_slash_command(event_data)

    # Send HTTP 200 response with an empty body so Slack knows we're done
    return make_response('', 200)


@app.route('/viktor/vikapi/actions', methods=['GET', 'POST'])
def handle_action():
    """Handle a response when a user clicks a button from a form Slack"""
    event_data = json.loads(request.form["payload"])
    user = event_data['user']['id']
    channel = event_data['channel']['id']
    actions = event_data['actions']
    # Not sure if we'll ever receive more than one action?
    action = actions[0]

    # Send that info onwards to determine how to deal with it
    if action['block_id'] not in action_timestamps:
        Bot.process_incoming_action(user, channel, action)
        action_timestamps.append(action['block_id'])
    # Respond to the initial message and update it
    update_dict = {
        'replace_original': True,
        'text': 'Thanks, shithead!'
    }
    if event_data['container']['is_ephemeral']:
        update_dict['response_type'] = 'ephemeral'
    resp = requests.post(event_data['response_url'], json=update_dict,
                         headers={'Content-Type': 'application/json'})

    # Send HTTP 200 response with an empty body so Slack knows we're done
    return make_response('', 200)


@app.route("/viktor/cron/new_emojis", methods=['POST'])
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
            Bot.bkb.make_context_section('Incoming emojis that were added in the last 10 min!'),
        ]
        Bot.st.send_message(Bot.emoji_channel, '', blocks=msg_block)
        Bot.st.send_message(Bot.emoji_channel, emoji_str)
        # Reset list of added emojis to an empty set
        Bot.new_emoji_set = set()

    return make_response('', 200)


@app.route("/viktor/cron/profile_update", methods=['POST'])
def handle_cron_profile_update():
    """Check for newly updated profile elements (triggered by cron task that sends POST req every 10 mins)"""
    # Check updated profile (every 10 mins)
    if len(Bot.user_updates_dict) > 0:
        # Go about notifying channel of newly uploaded emojis
        for uid, change_dict in Bot.user_updates_dict.items():
            # we'll currently report on avatar, display name, name, title and status changes.
            changes_txt = '*`{display_name}`*\t\t*`{real_name}`*\n:q:{title}:q:\n{status_emoji} {status_text}'
            msg_block = [
                Bot.bkb.make_context_section(f'<@{uid}> changed their profile info recently!'),
                Bot.bkb.make_block_divider()
            ]
            # Process new/old data
            for data in ['old', 'new']:
                transition = 'from' if data == 'old' else 'to'
                avi_url = change_dict[data]['avi']
                avi_alt = f'{transition} pic'
                msg_block += [
                    Bot.bkb.make_context_section(f'{transition} this...'),
                    Bot.bkb.make_block_section(changes_txt.format(**change_dict[data]),
                                               accessory=Bot.bkb.make_image_accessory(avi_url, avi_alt))
                ]

            Bot.st.send_message(Bot.general_channel, '', blocks=msg_block)
            # Make sure the current dict is then updated to reflect changes we've reported
            Bot.users_dict[uid] = change_dict['new']
        # Reset dict of user profile changes to an empty dict
        Bot.user_updates_dict = {}

    return make_response('', 200)


@bot_events.on('reaction_added')
def reaction(event_data: dict):
    event = event_data['event']
    if event['user'] not in [Bot.bot_id, Bot.user_id]:
        # Keep from reacting to own reaction
        emojis = Bot.emoji_list
        random_emoji = emojis[randint(0, len(emojis))]
        try:
            Bot.bot.reactions_add(
                name=random_emoji,
                channel=event['item']['channel'],
                timestamp=event['item']['ts']
            )
        except Exception as e:
            # Sometimes we'll get a 'too_many_reactions' error. Disregard in that case
            pass


@bot_events.on('message')
def scan_message(event_data: dict):
    Bot.st.parse_event(event_data)
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


@bot_events.on('emoji_changed')
def notify_new_emojis(event_data):
    event = event_data['event']
    # Make a post about a new emoji being added in the #emoji_suggestions channel
    if event['subtype'] == 'add':
        emoji = event['name']
        Bot.new_emoji_set.add(emoji)


@bot_events.on('user_change')
def notify_new_statuses(event_data):
    """Triggered when a user updates their profile info. Gets saved to global dict
    where we then report it in #general"""
    event = event_data['event']
    user_info = event['user']
    uid = user_info['id']
    if uid in Bot.users_dict.keys():
        # Get what info we've already stored on the user
        current_user_dict = Bot.users_dict[uid]
        # Get the user's newly updated dict
        new_user_dict = Bot.st.clean_user_info(user_info)

        # Add updated to our updates dict
        Bot.user_updates_dict[uid] = {k: v for k, v in zip(['old', 'new'], [current_user_dict, new_user_dict])}
