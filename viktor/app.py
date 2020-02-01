import os
from random import randint
from slackeventsapi import SlackEventAdapter
from flask import Flask
from .utils import Viktor


bot_name = 'viktor'

key_path = os.path.join(os.path.expanduser('~'), 'keys')
key_dict = {}
for t in ['SIGNING_SECRET', 'XOXB_TOKEN', 'XOXP_TOKEN', 'VERIFY_TOKEN']:
    with open(os.path.join(key_path, f'{bot_name.upper()}_SLACK_{t}')) as f:
        key_dict[t.lower()] = f.read().strip()

Bot = Viktor(bot_name, key_dict['xoxb_token'], key_dict['xoxp_token'])
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


