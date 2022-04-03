import json
import signal
import requests
from datetime import (
    datetime,
    timedelta
)
from flask import (
    Flask,
    request,
    make_response
)
from sqlalchemy.sql import (
    and_,
    func,
    not_
)
from slackeventsapi import SlackEventAdapter
from slacktools import (
    SecretStore,
    BlockKitBuilder as bkb
)
from easylogger import Log
import viktor.bot_base as botbase
from viktor.db_eng import ViktorPSQLClient
from viktor.model import (
    TableEmoji,
    TableSlackUser,
    TableSlackUserChangeLog,
    TableQuote
)
from viktor.settings import auto_config
from viktor.utils import collect_pins

bot_name = auto_config.BOT_NICKNAME
logg = Log(bot_name, log_to_file=True)

credstore = SecretStore('secretprops-davaiops.kdbx')
# Set up database connection
conn_dict = credstore.get_entry(f'davaidb-{auto_config.ENV.lower()}').custom_properties
vik_creds = credstore.get_key_and_make_ns(bot_name)

logg.debug('Starting up app...')
# Include a means of halting duplicate requests from being handled
#   until I can figure out a better async protocol
message_limits = {}  # date, count
logg.debug('Building user list')
app = Flask(__name__)
eng = ViktorPSQLClient(props=conn_dict, parent_log=logg)

logg.debug('Instantiating bot...')
Bot = botbase.Viktor(parent_log=logg)

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
        'text': 'boop beep boop'
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


@app.route("/cron/new-emojis", methods=['POST'])
def handle_cron_new_emojis():
    """Check for newly uploaded emojis (triggered by cron task that sends POST req every 10 mins)"""
    # Check emojis uploaded (every 60 mins)
    # This url is hit in crontab as such:
    #       0 * * * * /usr/bin/curl -X POST https://YOUR_APP/cron/new-emojis
    logg.debug('Beginning new emoji report...')
    now = datetime.now()
    interval = (now - timedelta(minutes=60))
    with eng.session_mgr() as session:
        new_emojis = session.query(TableEmoji).filter(TableEmoji.created_date >= interval).all()
        session.expunge_all()
    logg.debug(f'{len(new_emojis)} emojis found.')
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


@app.route("/cron/profile-update", methods=['POST'])
def handle_cron_profile_update():
    """Check for newly updated profile elements (triggered by cron task that sends POST req every 1 hr)"""
    # Check emojis uploaded (every 60 mins)
    # This url is hit in crontab as such:
    #       0 * * * * /usr/bin/curl -X POST https://YOUR_APP/cron/profile-update
    logg.debug('Beginning updated profile report...')
    # TODO: Methodology...
    #   since Slack pushes a /user_change event for every minor change, we should wait before logging that change
    #   so what we'll do here is, every hour, compare what's in the users table against what's in the change log.
    #   We should also expect the situation that the user doesn't appear in the change log, and if that happens,
    #   have an option to 'mute' the announcement for that user.

    # These are attributes to keep track of
    attrs = [
        'real_name',
        'display_name',
        'status_emoji',
        'status_title',
        'role_title',
        'role_desc',
        'avatar_link'
    ]
    updated_users = []
    with eng.session_mgr() as session:
        users = session.query(TableSlackUser).all()

        user: TableSlackUser
        for user in users:
            logg.debug(f'Working on user id: {user.user_id}')
            most_recent_changelog = session.query(TableSlackUserChangeLog).filter(
                TableSlackUserChangeLog.user_key == user.user_id
            ).order_by(TableSlackUserChangeLog.created_date.desc()).limit(1).one_or_none()
            if most_recent_changelog is None:
                # Record the user details without comparison - this is the first instance encountering this user
                logg.debug('Recording user details to changelog - no past changelog entry')
                attr_dict = {k: user.__dict__.get(k) for k in attrs}
                session.add(TableSlackUserChangeLog(user_key=user.user_id, **attr_dict))
            else:
                # Begin comparing to find what's new
                logg.debug('Comparing user details to most recent changelog entry')
                change_dict = {'user_hashname': f'{user.display_name}|{user.slack_user_hash}'}
                for attr in attrs:
                    last_chglog = most_recent_changelog.__dict__.get(attr)
                    cur_user = user.__dict__.get(attr)
                    if last_chglog != cur_user:
                        change_dict[attr] = {
                            'old': last_chglog,
                            'new': cur_user
                        }
                if len(change_dict) > 1:
                    logg.debug(f'Changes detected for {user.display_name}({user.user_id})')
                    # Update the changelog
                    attr_dict = {k: user.__dict__.get(k) for k in attrs}
                    session.add(TableSlackUserChangeLog(user_key=user.user_id, **attr_dict))
                    updated_users.append(change_dict)
    # Now work on splitting the new/old info into a message
    for updated_user in updated_users:
        blocks = [
            bkb.make_context_section(f'*`{updated_user["user_hashname"]}`* changed their profile info recently!'),
            bkb.make_block_divider()
        ]
        for attr in attrs:
            if attr not in updated_user.keys():
                continue
            blocks.append([
                bkb.make_context_section(attr.title()),
                bkb.make_block_section(
                    f"NEW:\n\t{updated_user.get('attr').get('new')}\n\n"
                    f"OLD:\n\t{updated_user.get('attr').get('old')}"),
                bkb.make_block_divider()
            ])
        Bot.st.send_message(channel=Bot.general_channel, message='user profile update!', blocks=blocks)

    return make_response('', 200)


@app.route("/cron/reacts", methods=['POST'])
def handle_cron_reacts():
    """Check for new reactions - if any, run through and react to them"""
    pass
    # Check reactions (every 5 mins)
    # This url is hit in crontab as such:
    #       0 * * * * /usr/bin/curl -X POST https://YOUR_APP/cron/reacts
    # logg.debug(f'Handling new reacts from {hour_ago}...')
    # reacts = Bot.state_store.get('reacts', {})
    # if len(reacts) > 0:
    #     # Begin reacting to new reactions
    #     logg.debug(f'{len(reacts)} reacts found.')
    #     with eng.session_mgr() as session:
    #         emojis = session.query(TableEmoji).filter(TableEmoji.created_date >= hour_ago).all()
    #         session.expunge_all()
    #     for item in Bot.state_store.get('reacts'):
    #         logg.debug(f'Channel|timestamp: {item}')
    #         chan, ts = item.split('|')
    #         Bot.bot.reactions_add(name=choice(emojis), channel=chan, timestamp=ts)
    # return make_response('', 200)


@bot_events.on('reaction_added')
def reaction(event_data: dict):
    event = event_data['event']
    user = event.get('user')
    item = event.get('item')
    channel = item.get('channel')
    reaction_emoji = event.get('reaction')
    # This is the timestamp of the reaction
    react_ts = event.get('event_ts')
    # This is the timestamp of the message
    msg_ts = item.get('ts')
    unique_event_key = f'{channel}|{react_ts}'
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
    except Exception as _:
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
def store_pins(event_data):
    event = event_data['event']
    tbl_obj = collect_pins(event, psql_client=eng, log=logg)
    # Add to db
    with eng.session_mgr() as session:
        session.add(tbl_obj)

    Bot.st.send_message(channel=event['channel_id'], message='Pin successfully added, kommanderovnik o7')


@bot_events.on('pin_removed')
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
def notify_new_statuses(event_data):
    """Triggered when a user updates their profile info. Gets saved to global dict
    where we then report it in #general"""
    event = event_data['event']
    user_info = event['user']
    uid = user_info['id']
    # Look up user in db
    user_obj = eng.get_user_from_hash(user_hash=uid)
    logg.debug(f'User change detected for {uid}')
    if user_obj is None:
        logg.warning(f'Couldn\'t find user: {uid} \n {user_info}')
        return

    # get display name
    profile = user_info.get('profile')
    display_name = profile.get('display_name')
    real_name = profile.get('real_name')
    status_emoji = profile.get('status_emoji', '')
    status_title = profile.get('status_title', '')
    avi_link = profile.get('image_512')
    if any([
        user_obj.display_name != display_name,
        user_obj.real_name != real_name,
        user_obj.status_emoji != status_emoji,
        user_obj.status_title != status_title,
        user_obj.avatar_link != avi_link
    ]):
        # Update the user
        with eng.session_mgr() as session:
            session.refresh(user_obj)
            user_obj.real_name = real_name
            user_obj.display_name = display_name
            user_obj.avatar_link = avi_link
            user_obj.status_emoji = status_emoji
            user_obj.status_title = status_title
        logg.debug(f'User {display_name} updated in db.')

    # if uid in Bot.users_dict.keys():
    #     # Get what info we've already stored on the user
    #     current_user_dict = Bot.users_dict[uid]
    #     # Get the user's newly updated dict
    #     new_user_dict = Bot.st.clean_user_info(user_info)
    #
    #     # Add updated to our updates dict
    #     Bot.user_updates_dict[uid] = {k: v for k, v in zip(['old', 'new'], [current_user_dict, new_user_dict])}
