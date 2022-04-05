from datetime import datetime
from typing import (
    Dict,
    List,
    Union
)
import pytz
from urllib.request import (
    Request,
    urlopen
)
from lxml import etree
from lxml.etree import (
    _Element,
    _ElementTree
)
from sqlalchemy.sql import (
    func,
    or_
)
from sqlalchemy.engine.row import Row
from easylogger import Log
from viktor.db_eng import ViktorPSQLClient
from viktor.model import (
    TableSlackChannel,
    TableSlackUser,
    TableQuote
)


def collect_pins(pin_dict: Dict, psql_client: ViktorPSQLClient, log: Log) -> TableQuote:
    """Attempts to load pinned message into the quotes db"""
    us_ct = pytz.timezone('US/Central')
    if pin_dict.get('message') is None:
        # Receiving a pin message in-prod is different than when using the historical response from /api/pin_list
        pin_dict = pin_dict.get('item')
    author_uid = pin_dict.get('message').get('user')
    author_name = pin_dict.get('message').get('username')
    if author_uid is None:
        # Try getting bot id
        author_uid = pin_dict.get('message').get('bot_id', '')

    with psql_client.session_mgr() as session:
        author = session.query(TableSlackUser).filter(or_(
            TableSlackUser.slack_user_hash == author_uid,
            TableSlackUser.slack_bot_hash == author_uid
        )).one_or_none()

        if author is None and author_uid.startswith('B') and author_name is not None:
            # Probably a bot thing. Check if the user hash begins with 'b'.
            #   If so, try to write that id to the db so next time it goes through
            author = session.query(TableSlackUser).filter(
                func.lower(TableSlackUser.real_name) == author_name.lower()
            ).one_or_none()
        if author is None:
            # If author is still none, use the unknown user
            author = session.query(TableSlackUser).filter(
                TableSlackUser.slack_bot_hash == 'BUNKNOWN'
            ).one_or_none()
        session.expunge(author)

    with psql_client.session_mgr() as session:
        pinner = session.query(TableSlackUser).filter(
            TableSlackUser.slack_user_hash == pin_dict.get('created_by')
        ).one_or_none()
        if pinner is None:
            pinner = session.query(TableSlackUser).filter(
                TableSlackUser.slack_bot_hash == 'BUNKNOWN'
            ).one_or_none()
        session.expunge(pinner)
    log.debug('Adding pinned message to table...')

    text = pin_dict.get('message').get('text')
    files = pin_dict.get('message').get('files')
    if files is not None:
        for file in files:
            text += f'\n{file.get("url_private")}'
    if text == '':
        # Try getting attachment info
        for att in pin_dict.get('message').get('attachments', []):
            text += att.get('image_url')
    log.debug(f'Passing text: "{text[:10]}"')
    with psql_client.session_mgr() as session:
        channel_key = session.query(TableSlackChannel.channel_id).filter(
            TableSlackChannel.slack_channel_hash == pin_dict.get('channel')
        ).one_or_none()
        if isinstance(channel_key, Row):
            # Convert to id
            channel_key = next(iter(channel_key), None)
    return TableQuote(
        text=text,
        author_user_key=author.user_id,
        channel_key=channel_key,
        pinner_user_key=pinner.user_id if pinner is not None else None,
        link=pin_dict.get('message').get('permalink'),
        message_timestamp=datetime.fromtimestamp(float(pin_dict.get('message').get('ts')), us_ct),
        pin_timestamp=datetime.fromtimestamp(pin_dict.get('created'), us_ct)
    )


class XPathExtractor:
    """Builds an HTML tree and allows element selection based on XPath"""
    def __init__(self, url: str):
        self.tree = self._get_tree(url)

    @staticmethod
    def _get_tree(url: str) -> _ElementTree:
        req = Request(url, headers={'User-Agent': 'Magic Browser'})
        resp = urlopen(req)
        if resp.code != 200:
            raise ConnectionError(f'Unexpected response to request: {resp.code}')

        htmlparser = etree.HTMLParser()
        return etree.parse(resp, htmlparser)

    @staticmethod
    def get_inner_html(elem: _Element) -> str:
        """Extracts the HTML as text from a given element"""
        return etree.tostring(elem, encoding='utf-8').decode('utf-8')

    @staticmethod
    def read_str_to_html(string: str) -> _Element:
        """Takes a string and reads it in as HTML elements"""
        return etree.fromstring(string)

    @staticmethod
    def get_nth_child(elem: _Element, n: int) -> _Element:
        """Returns the nth child of an element"""
        return elem.getchildren()[n]

    @staticmethod
    def get_attr_from_elems(elem_list: List[_Element], from_attr: str = 'href') -> List[str]:
        """Extracts an attribute from all the elements in a list having that particular attribute field"""
        return [elem.get(from_attr) for elem in elem_list if elem.get(from_attr) is not None]

    def xpath(self, xpath: str, obj: _Element = None, single: bool = False, get_text: bool = False) -> \
            Union[str, _Element, List[_Element]]:
        """Retrieves element(s) matching the given xpath"""
        method = self.tree.xpath if obj is None else obj.xpath
        elems = method(xpath)
        return self._process_xpath_elems(elems, single, get_text)

    @staticmethod
    def class_contains(cls: str) -> str:
        return f'(@class, "{cls}"'

    @staticmethod
    def _process_xpath_elems(elems: List[_Element], single: bool, get_text: bool) -> \
            Union[str, _Element, List[_Element]]:
        if single:
            elems = [elems[0]]

        if get_text:
            return ''.join([x for e in elems for x in e.itertext()])
        else:
            return elems[0] if single else elems

    def xpath_with_regex(self, xpath: str, obj: _Element = None, single: bool = False, get_text: bool = False) ->\
            Union[str, _Element, List[_Element]]:
        """Leverages xpath with regex
        Example:
            >>> self.xpath_with_regex('//div[re:match(@class, "w?ord.*")]/h1')
        """
        method = self.tree.xpath if obj is None else obj.xpath
        elems = method(xpath, namespaces={"re": "http://exslt.org/regular-expressions"})
        elems = self._process_xpath_elems(elems, single, get_text)
        return elems
