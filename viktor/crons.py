import math
from datetime import (
    datetime,
    timedelta
)
from flask import (
    Blueprint,
    make_response
)
from slacktools.block_kit import BlockKitBuilder as BKitB
from viktor.model import (
    TableEmoji,
    TablePotentialEmoji,
    TableSlackUser,
    TableSlackUserChangeLog
)
import viktor.app as mainapp
from viktor.logg import get_base_logger


cron = Blueprint('cron', __name__)
logg = get_base_logger()


@cron.route('/new-emojis', methods=['POST'])
@logg.catch
def handle_cron_new_emojis():
    """Check for newly uploaded emojis (triggered by cron task that sends POST req every 60m mins)

    Set this url so it is accessed with crontab such:
        0 * * * * /usr/bin/curl -X POST https://YOUR_APP/cron/new-emojis
    """
    mainapp.logg.debug('Beginning new emoji report...')
    now = datetime.now()
    interval = (now - timedelta(minutes=60))
    with mainapp.eng.session_mgr() as session:
        new_emojis = session.query(TableEmoji).filter(TableEmoji.created_date >= interval).all()
        session.expunge_all()
    mainapp.logg.debug(f'{len(new_emojis)} emojis found.')
    if len(new_emojis) > 0:
        # Go about notifying channel of newly uploaded emojis
        emojis = [f':{x.name}:' for x in new_emojis]
        emoji_str = ''
        for i in range(0, len(emojis), 10):
            emoji_str += f"{''.join(emojis[i:i + 10])}\n"
        msg_block = [
            BKitB.make_context_section([
                BKitB.markdown_section('Incoming emojis that were added in the last 60 min!')
            ]),
        ]
        mainapp.Bot.st.send_message(mainapp.Bot.emoji_channel, 'new emoji report', blocks=msg_block)
        mainapp.Bot.st.send_message(mainapp.Bot.emoji_channel, emoji_str)
    return make_response('', 200)


@cron.route('/new-potential-emojis', methods=['POST'])
@logg.catch
def handle_cron_new_potential_emojis():
    """Daily check for new potential emojis (triggered by cron task that sends POST req every 10 mins)

    Set this url so it is accessed with crontab such:
        0 * * * * /usr/bin/curl -X POST https://YOUR_APP/cron/new-potential-emojis
    """
    mainapp.logg.debug('Beginning new potential emoji report...')
    interval = (datetime.now() - timedelta(hours=3))
    with mainapp.eng.session_mgr() as session:
        new_potential_emojis = session.query(TablePotentialEmoji).filter(
            TablePotentialEmoji.created_date >= interval).all()
        session.expunge_all()
    mainapp.logg.debug(f'{len(new_potential_emojis)} new potential emojis pulled from db.')
    if len(new_potential_emojis) > 0:
        blocks = [
            BKitB.make_context_section('New Potential Emojis :postal_horn::postal_horn::postal_horn:')
        ]
        emoji: TablePotentialEmoji
        for emoji in new_potential_emojis:
            blocks.append(
                BKitB.make_block_section(
                    BKitB.build_link(url=emoji.link, text=emoji.name),
                    accessory=BKitB.make_image_element(url=emoji.link, alt_txt='emoji'))
            )
        for i in range(0, len(blocks), 50):
            mainapp.logg.debug(f'Sending block {i + 1} of {math.ceil(len(blocks)/50)}')
            mainapp.Bot.st.send_message(channel=mainapp.Bot.emoji_channel, message='New Potential Emoji report!',
                                        blocks=blocks[i: i + 50])
    return make_response('', 200)


@cron.route("/profile-update", methods=['POST'])
@logg.catch
def handle_cron_profile_update():
    """Check for newly updated profile elements (triggered by cron task that sends POST req every 1 hr)"""
    # Check emojis uploaded (every 60 mins)
    # This url is hit in crontab as such:
    #       0 * * * * /usr/bin/curl -X POST https://YOUR_APP/cron/profile-update
    mainapp.logg.debug('Beginning updated profile report...')
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
    with mainapp.eng.session_mgr() as session:
        users = session.query(TableSlackUser).all()

        user: TableSlackUser
        for user in users:
            mainapp.logg.debug(f'Working on user id: {user.user_id}')
            most_recent_changelog = session.query(TableSlackUserChangeLog).filter(
                TableSlackUserChangeLog.user_key == user.user_id
            ).order_by(TableSlackUserChangeLog.created_date.desc()).limit(1).one_or_none()
            if most_recent_changelog is None:
                # Record the user details without comparison - this is the first instance encountering this user
                mainapp.logg.debug('Recording user details to changelog - no past changelog entry')
                attr_dict = {k: user.__dict__.get(k) for k in attrs}
                session.add(TableSlackUserChangeLog(user_key=user.user_id, **attr_dict))
            else:
                # Begin comparing to find what's new
                mainapp.logg.debug('Comparing user details to most recent changelog entry')
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
                    mainapp.logg.debug(f'Changes detected for {user.display_name}({user.user_id})')
                    # Update the changelog
                    attr_dict = {k: user.__dict__.get(k) for k in attrs}
                    session.add(TableSlackUserChangeLog(user_key=user.user_id, **attr_dict))
                    updated_users.append(change_dict)
    # Now work on splitting the new/old info into a message
    for updated_user in updated_users:
        blocks = [
            BKitB.make_context_section(f'*`{updated_user["user_hashname"]}`* '
                                       f'changed their profile info recently!'),
            BKitB.make_block_divider()
        ]
        for attr in attrs:
            if attr not in updated_user.keys():
                continue
            blocks += [
                BKitB.make_context_section(attr.title()),
                BKitB.make_block_section(
                    f"NEW:\n\t{updated_user.get(attr).get('new')}\n\n"
                    f"OLD:\n\t{updated_user.get(attr).get('old')}"),
                BKitB.make_block_divider()
            ]
        mainapp.Bot.st.send_message(channel=mainapp.Bot.general_channel, message='user profile update!',
                                    blocks=blocks)

    return make_response('', 200)


@cron.route("/reacts", methods=['POST'])
@logg.catch
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
