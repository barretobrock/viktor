from datetime import datetime
from typing import Dict
from .channels import random_channel
from .users import random_user

# Response when someone reacts to a normal message (text from another user)
reaction_added_normal = {
    'type': 'reaction_added',
    'user': random_user(),
    'reaction': 'hello',
    'item_user': random_user(),
    'item': {
        'type': 'message',
        'channel': random_channel(),
        'ts': f'{datetime.now().timestamp()}'
    },
    'event_ts': f'{datetime.now().timestamp()}'
}

channel_created = {
    'type': 'channel_created',
    'channel': {
        'id': random_channel(),
        'name': 'the_channel',
        'created': int(datetime.now().timestamp()),
        'creator': random_user()
    }
}


def gen_pin_added(is_bot: bool = False) -> Dict:
    if is_bot:
        message_dict = {
            'bot_id': random_user(is_bot=is_bot),
            'bot_name': 'some bot',
        }
    else:
        message_dict = {
            'user': random_user(is_bot=is_bot),
            'username': 'someone',
        }

    return {
        'type': 'pin_added',
        'user': random_user(),
        'channel_id': random_channel(),
        'item': {
            'message': message_dict,
        },
        'event_ts': f'{datetime.now().timestamp()}'
    }


user_change = {
    'type': 'user_change',
    'user': {
        'id': random_user(),
        'profile': {
            "avatar_hash": "ge3b51ca72de",
            "status_text": "Print is dead",
            "status_emoji": ":books:",
            "status_expiration": 0,
            "real_name": "Egon Spengler",
            "display_name": "spengler",
            "real_name_normalized": "Egon Spengler",
            "display_name_normalized": "spengler",
            "email": "spengler@ghostbusters.example.com",
            "image_original": "https://.../avatar/e3b51ca72dee4ef87916ae2b9240df50.jpg",
            "image_24": "https://.../avatar/e3b51ca72dee4ef87916ae2b9240df50.jpg",
            "image_32": "https://.../avatar/e3b51ca72dee4ef87916ae2b9240df50.jpg",
            "image_48": "https://.../avatar/e3b51ca72dee4ef87916ae2b9240df50.jpg",
            "image_72": "https://.../avatar/e3b51ca72dee4ef87916ae2b9240df50.jpg",
            "image_192": "https://.../avatar/e3b51ca72dee4ef87916ae2b9240df50.jpg",
            "image_512": "https://.../avatar/e3b51ca72dee4ef87916ae2b9240df50.jpg",
            "team": "T012AB3C4"
        }
    }
}
