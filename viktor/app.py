import os
from random import randint
from flask import Flask
from slacktools import SlackEventAdapter
from .utils import Viktor


bot_name = 'viktor'
DEBUG = os.environ['VIKTOR_DEBUG'] == '1'

key_path = os.path.join(os.path.expanduser('~'), 'keys')
key_dict = {}
for t in ['SIGNING_SECRET', 'XOXB_TOKEN', 'XOXP_TOKEN', 'VERIFY_TOKEN', 'ONBOARDING_KEY', 'SPREADSHEET_KEY']:
    with open(os.path.join(key_path, f'{bot_name.upper()}_SLACK_{t}')) as f:
        key_dict[t.lower()] = f.read().strip()

Bot = Viktor(bot_name, key_dict['xoxb_token'], key_dict['xoxp_token'],
             ss_key=key_dict['spreadsheet_key'], onboarding_key=key_dict['onboarding_key'], debug=DEBUG)
# Include a means of halting duplicate requests from being handled
#   until I can figure out a better async protocol
message_events = []
emoji_events = []
user_events = []
users_list = Bot.st.get_channel_members('CLWCPQ2TV')  # get users in general
app = Flask(__name__)

# Events API listener
bot_events = SlackEventAdapter(key_dict['signing_secret'], "/viktor/vikapi/events", app)


@bot_events.on('reaction_added')
def reaction(event_data):
    event = event_data['event']
    if event['user'] != Bot.bot_id:
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
def scan_message(event_data):
    event = event_data['event']
    # Pass event stuff onward to app
    msg_packet = None
    if event['type'] == 'message' and "subtype" not in event:
        trigger, message, raw_message = Bot.st.parse_direct_mention(event['text'])
        if trigger in Bot.triggers:
            # Build a message hash
            msg_hash = f'{event["channel"]}_{event["ts"]}'
            if msg_hash not in message_events:
                message_events.append(msg_hash)
                msg_packet = {
                    'message': message.strip(),
                    'raw_message': raw_message.strip()
                }
                # Add in all the other stuff
                msg_packet.update(event)

    if msg_packet is not None:
        try:
            Bot.handle_command(msg_packet)
        except Exception as e:
            if not isinstance(e, RuntimeError):
                exception_msg = '{}: {}'.format(e.__class__.__name__, e)
                Bot.st.send_message(msg_packet['channel'], "Exception occurred: \n```{}```".format(exception_msg))


@bot_events.on('emoji_changed')
def notify_new_emojis(event_data):
    event = event_data['event']
    # Make a post about a new emoji being added in the #emoji_suggestions channel
    emoji_chan = 'CLWCPQ2TV'
    if event['subtype'] == 'add':
        emoji = event['name']
        if emoji not in emoji_events:
            # Add it for future checks
            emoji_events.append(emoji)
            Bot.st.send_message(emoji_chan, f'New emoji added: :{emoji}:')


@bot_events.on('user_change')
def notify_new_statuses(event_data):
    event = event_data['event']
    # Post to #general
    general_chan = 'CMEND3W3H'
    user_info = event['user']
    uid = user_info['id']
    if uid in [x['id'] for x in users_list]:
        # User's in #general
        # Get user's index in our list of dicts
        user_dict_idx = next((idx for (idx, d) in enumerate(users_list) if d['id'] == uid), None)
        if user_dict_idx is None:
            return None
        # Get what info we've already stored on the user
        user_dict = users_list[user_dict_idx]
        if 'profile' in user_info.keys():
            profile_info = user_info['profile']
            status = profile_info['status_text']
            emoji = profile_info.get('status_emoji', '')
            status_hash = f'{emoji} {status}'
            prev_status_hash = f'{user_dict["status_emoji"]} {user_dict["status_text"]}'
            if status_hash != prev_status_hash:
                user_dict['status_emoji'] = emoji
                user_dict['status_text'] = status
                # Send updated dict to the list of user dicts
                users_list[user_dict_idx] = user_dict
                # Message channel about status update
                msg = f'<@{uid}> updated their status: {status_hash}'
                Bot.st.send_message(general_chan, msg)

