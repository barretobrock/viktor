"""
Cron endpoints that get hit with a cadence defined either in crontab or elsewhere.

Set URLs so they can be accessed
    0 * * * * /usr/bin/curl -X POST https://YOUR_APP/cron/ENDPOINT
"""

from datetime import (
    datetime,
    timedelta,
)
import math

from flask import (
    Blueprint,
    make_response,
)
from slacktools.block_kit.blocks import (
    DividerBlock,
    MarkdownContextBlock,
    MarkdownSectionBlock,
)
from slacktools.block_kit.elements.formatters import TextFormatter

from viktor.core.user_changes import build_profile_diff
from viktor.model import (
    TableEmoji,
    TablePotentialEmoji,
    TableSlackUser,
    TableSlackUserChangeLog,
)
from viktor.routes.helpers import (
    get_app_bot,
    get_app_logger,
    get_viktor_eng,
)

bp_crons = Blueprint('crons', __name__, url_prefix='/api/crons')


@bp_crons.route('/new-emojis', methods=['POST'])
def handle_cron_new_emojis():
    """Check for newly uploaded emojis (triggered by cron task that sends POST req every 60m mins)
    """
    logg = get_app_logger()
    logg.debug('Beginning new emoji report...')
    emoji_channel = get_app_bot().emoji_channel
    now = datetime.now()
    interval = (now - timedelta(minutes=60))
    with get_viktor_eng().session_mgr() as session:
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
            MarkdownContextBlock('Incoming emojis that were added in the last 60 min!'),
            MarkdownSectionBlock(emoji_str)
        ]
        get_app_bot().st.send_message(emoji_channel, 'new emoji report', blocks=msg_block)
    return make_response('', 200)


@bp_crons.route('/new-potential-emojis', methods=['POST'])
def handle_cron_new_potential_emojis():
    """Daily check for new potential emojis (triggered by cron task that sends POST req every 10 mins)
    """
    logg = get_app_logger()
    logg.debug('Beginning new potential emoji report...')
    emoji_channel = get_app_bot().emoji_channel
    interval = (datetime.now() - timedelta(hours=3))
    with get_viktor_eng().session_mgr() as session:
        new_potential_emojis = session.query(TablePotentialEmoji).filter(
            TablePotentialEmoji.created_date >= interval).all()
        session.expunge_all()
    logg.debug(f'{len(new_potential_emojis)} new potential emojis pulled from db.')
    if len(new_potential_emojis) > 0:
        blocks = [
            MarkdownContextBlock('New Potential Emojis :postal_horn::postal_horn::postal_horn:'),
        ]
        emoji: TablePotentialEmoji
        for emoji in new_potential_emojis:
            blocks.append(
                MarkdownSectionBlock(TextFormatter.build_link(emoji.link, emoji.name),
                                     image_url=emoji.link, image_alt_txt=emoji.name)
            )
        for i in range(0, len(blocks), 50):
            logg.debug(f'Sending block {i + 1} of {math.ceil(len(blocks)/50)}')
            get_app_bot().st.send_message(channel=emoji_channel, message='New Potential Emoji report!',
                                          blocks=blocks[i: i + 50], unfurl_media=False)
    return make_response('', 200)


@bp_crons.route("/profile-update", methods=['POST'])
def handle_cron_profile_update():
    """Check for newly updated profile elements (triggered by cron task that sends POST req every 1 hr)"""
    logg = get_app_logger()
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
    with get_viktor_eng().session_mgr() as session:
        users = session.query(TableSlackUser).all()

        user: TableSlackUser
        for user in users:
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
                    logg.debug(f'{len(change_dict)} changes detected for '
                               f'{user.display_name}(uid:{user.user_id})')
                    # Update the changelog
                    attr_dict = {k: user.__dict__.get(k) for k in attrs}
                    session.add(TableSlackUserChangeLog(user_key=user.user_id, **attr_dict))
                    updated_users.append(change_dict)
    # Now work on splitting the new/old info into a message
    for updated_user in updated_users:
        blocks = [
            MarkdownContextBlock(f'*`{updated_user["user_hashname"]}`* changed their profile info recently!'),
            DividerBlock()
        ]
        blocks = build_profile_diff(blocks=blocks, updated_user_dict=updated_user)
        get_app_bot().st.send_message(channel=get_app_bot().general_channel, message='user profile update!',
                                      blocks=blocks)

    return make_response('', 200)


@bp_crons.route("/reacts", methods=['POST'])
def handle_cron_reacts():
    """Check for new reactions - if any, run through and react to them"""
    pass
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
