from typing import (
    Dict,
    Optional,
    Union,
)

from loguru import logger
from slacktools.block_kit import BlockKitBuilder as BKitB
from slacktools.slackbot import SlackBotBase
from sqlalchemy.orm import Session

from viktor.db_eng import ViktorPSQLClient
from viktor.model import (
    TableSlackUser,
    TableSlackUserChangeLog,
)

# Attribute map for slack API values and table columns
SLACK_API_ATTR_MAP = {
    # slack_attr: col_name
    'display_name': 'display_name',
    'real_name': 'real_name',
    'status_emoji': 'status_emoji',
    'status_text': 'status_title',
    'image_512': 'avatar_link',
    'what-i-do': 'what_i_do'
}

ALL_IMPORTANT_ATTRS = list(SLACK_API_ATTR_MAP.values()) + ['role_title', 'role_desc']


def extract_user_change(eng: ViktorPSQLClient, user_info_dict: Dict[str, Union[str, Dict]], log: logger):
    """Takes in a dictionary of recent user changes and processes them for logging into the database"""
    uid = user_info_dict['id']
    log.debug(f'User change detected for {uid}. Looking them up in database...')
    user_obj = eng.get_user_from_hash(user_hash=uid)
    if user_obj is None:
        log.warning(f'Couldn\'t find user: {uid} \n {user_info_dict}')
        return

    profile_dict = user_info_dict.get('profile')

    log.debug(f'Scanning attributes for changes for user {user_obj.display_name}...')
    with eng.session_mgr() as session:
        session.add(user_obj)
        for slack_attr_name, table_attr_name in SLACK_API_ATTR_MAP.items():
            slack_attr = profile_dict.get(slack_attr_name)
            table_attr = getattr(user_obj, table_attr_name)
            if slack_attr is None:
                log.debug(f'Skipping attr "{slack_attr_name}" - was None.')
                continue
            elif slack_attr != table_attr:
                log.debug(f'Found attr "{slack_attr_name}" was different than what\'s in the table.')
                setattr(user_obj, table_attr_name, slack_attr)


def process_user_changes(session: Session, user: TableSlackUser, log: logger) -> Optional[Dict]:
    """Processes the profile changes for a single user"""
    # List all attributes we want to monitor - Slack + OKR roles
    log.debug(f'Working on user: {user.display_name}.')
    most_recent_changelog = session.query(TableSlackUserChangeLog).filter(
        TableSlackUserChangeLog.user_key == user.user_id
    ).order_by(TableSlackUserChangeLog.created_date.desc()).limit(1).one_or_none()
    if most_recent_changelog is None:
        log.debug('Recording details to changelog - no past changelog entry.')
        attr_dict = {v: getattr(user, v) for v in ALL_IMPORTANT_ATTRS}
        session.add(TableSlackUserChangeLog(user_key=user.user_id, **attr_dict))
    else:
        log.debug('Comparing user detail to most recent changelog entry')
        change_dict = {
            'user_hashname': f'{user.display_name}|{user.slack_user_hash}'
        }
        for attr in ALL_IMPORTANT_ATTRS:
            last_chglog = most_recent_changelog.__dict__.get(attr)
            cur_user = user.__dict__.get(attr)
            if last_chglog != cur_user:
                change_dict[attr] = {
                    'old': last_chglog,
                    'new': cur_user
                }
        if len(change_dict) > 1:
            log.debug(f'Changes detected for {user.display_name}({user.user_id})')
            # Update the changelog
            attr_dict = {k: user.__dict__.get(k) for k in ALL_IMPORTANT_ATTRS}
            session.add(TableSlackUserChangeLog(user_key=user.user_id, **attr_dict))
            return change_dict
    return None


def process_updated_profiles(eng: ViktorPSQLClient, st: SlackBotBase, log: logger):
    """Handles the periodic scanning of differences between the profile changelog and the user's current profile"""
    updated_users = []
    with eng.session_mgr() as session:
        users = session.query(TableSlackUser).all()
        for user in users:
            change_dict = process_user_changes(session=session, user=user, log=log)
            if change_dict is not None:
                updated_users.append(change_dict)
    log.debug(f'Found {len(updated_users)} users with recent changes.')
    if len(updated_users) > 0:
        for updated_user in updated_users:
            blocks = [
                BKitB.make_context_section(f'*`{updated_user["user_hashname"]}`* '
                                           f'changed their profile info recently!'),
                BKitB.make_block_divider()
            ]
            for attr in ALL_IMPORTANT_ATTRS:
                if attr not in updated_user.keys():
                    continue
                blocks += [
                    BKitB.make_context_section(attr.title()),
                    BKitB.make_block_section(
                        f"NEW:\n\t{updated_user.get(attr).get('new')}\n\n"
                        f"OLD:\n\t{updated_user.get(attr).get('old')}"),
                    BKitB.make_block_divider()
                ]
            st.send_message(channel=st.main_channel, message='user profile update!',
                            blocks=blocks)
