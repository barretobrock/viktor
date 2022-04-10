from typing import (
    List,
    Union
)
from urllib.request import (
    Request,
    urlopen
)
from lxml import etree
from lxml.etree import (
    _ElementTree,
    _Element
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
