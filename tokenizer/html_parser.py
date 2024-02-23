"""
This module extends the HTMLParser from the html.parser to implement an HTML parser that tokenizes HTML source code
into custom tokens. After parsing, the parser instance contains a list of Token namedtuple instances,
that contain the name of the token, a one dimensional source mapping,
and the raw content of the token.

Token definitions can be found from the JSON files in the same directory as this module.
Definitions can be generated and updated with _generate_token_map_json.py and scripts in the tools directory.

Comments and whitespace are ignored.

Usage:
>>> source = "<!DOCTYPE html><html><head> ... "
>>> parser = TokenizingHTMLParser()
>>> # Parse the source and get the token string and index mappings:
>>> parser.tokenize(source)
('09ggg2gggggtrrd72cckjnmnkjnnnn', [[0, 15], [16, 22], [24, 30], ... ])
>>> # Parsed but 'uncompressed' tokens are still available:
>>> parser.tokens
[Token(type='declaration', range=[0, 15], data='DOCTYPE html'),
 Token(type='html-the-root-element', range=[16, 22], data='<html>'),
 Token(type='html-documet-metadata-elements', range=[24, 30], data='<meta charset="utf-8">'),
 ...]
>>> # Tokens can be compressed single characters with export_tokens
"""

import collections
import functools
import html.parser
import re

import tokenizer.util as util

from tokenizer.javascript import tokenize_no_string as tokenize_js
from tokenizer.css import tokenize_no_string as tokenize_css

# TODO hardcoded relative paths
HTML_GROUP_TO_ELEMENTS = util.parse_from_json("tokenizer/HTML_group_to_elements.json")
HTML_ELEMENT_TO_GROUP = util.key_to_list_mappings_inverted(HTML_GROUP_TO_ELEMENTS)
HTML_TOKEN_TYPES = [
    "declaration",
    "processing-instructions",
    "other-data",
    "script-data",
    "style-data",
    "other-elements",
] + list(HTML_GROUP_TO_ELEMENTS.keys())
HTML_TOKEN_TYPES = ["html-" + token_type for token_type in HTML_TOKEN_TYPES]
TOKEN_TYPE_TO_CHAR = util.parse_from_json("tokenizer/HTML_token_map.json")

Token = collections.namedtuple("Token", ["type", "range", "data"])


# Add a hook to HTMLParser.updatepos that captures the single dimensional source
# mappings before they are converted to two dimensional, row-column mappings.
def updatepos_hook(updatepos):
    if hasattr(updatepos, "__wrapped__"):
        # Already wrapped
        return updatepos

    @functools.wraps(updatepos)
    def set_token_range_and_call_updatepos(parser, i, j, *args, **kwargs):
        assert isinstance(
            parser, TokenizingHTMLParser
        ), "Expected parser to be an instance of TokenizingHTMLParser but it was not"
        if parser.tokens and parser.tokens[-1].range is None:
            # Replace the newest Token instance with an updated range
            parser.tokens[-1] = parser.tokens[-1]._replace(range=[i, j])
        return updatepos(parser, i, j, *args, **kwargs)

    return set_token_range_and_call_updatepos


html.parser.HTMLParser.updatepos = updatepos_hook(html.parser.HTMLParser.updatepos)


def tokenize_data_token(data_token, tokenizer):
    """
    Return an iterator over tokens resulting from tokenizing data_token.data with tokenizer.
    """
    index_offset = data_token.range[0]
    for token_name, t_range in zip(*tokenizer(data_token.data)):
        range_in_data = [index_offset + t_range[0], index_offset + t_range[1]]
        token_data = data_token.data[t_range[0] : t_range[1]]
        yield Token(token_name, range_in_data, token_data)


class TokenizingHTMLParser(html.parser.HTMLParser):
    """
    html.parser.HTMLParser subclass that accumulates custom HTML tokens
    (Token namedtuple instances) into a self.tokens list.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.reset()

    def reset(self):
        self.in_style_element = False
        self.in_script_element = False
        self.tokens = []
        self.errors = []
        # Redundant if this function is called from __init__,
        # but necessary if called explicitly.
        super().reset()

    def export_tokens(self):
        return (
            ''.join(TOKEN_TYPE_TO_CHAR[t.type] for t in self.tokens),
            [t.range for t in self.tokens],
        )

    def tokenize_js_and_css(self):
        new_tokens = []
        for token in self.tokens:
            if token.type == "html-style-data":
                new_tokens.extend(list(tokenize_data_token(token, tokenize_css)))
            elif token.type == "html-script-data":
                new_tokens.extend(list(tokenize_data_token(token, tokenize_js)))
            else:
                new_tokens.append(token)
        self.tokens = new_tokens

    def tokenize(self, source):
        self.reset()
        self.feed(source)
        self.tokenize_js_and_css()
        return self.export_tokens()

    def error(self, message):
        self.errors.append(message)

    def handle_starttag(self, tag, attrs):
        if tag == "style":
            self.in_style_element = True
        elif tag == "script":
            self.in_script_element = True
        if tag not in HTML_ELEMENT_TO_GROUP:
            token_type = 'html-other-elements'
        else:
            token_type = 'html-' + HTML_ELEMENT_TO_GROUP[tag]
        self.tokens.append(Token(token_type, None, self.get_starttag_text()))

    def handle_endtag(self, tag):
        if tag == "style":
            self.in_style_element = False
        elif tag == "script":
            self.in_script_element = False

    def handle_data(self, data):
        # Do not tokenize newlines and whitespace between tokens.
        if re.fullmatch(r"^\s*$", data):
            return
        starttag_text = self.get_starttag_text()
        tag_type = None
        if self.in_style_element and not self.in_script_element:
            assert starttag_text.startswith(
                "<style"
            ), ("Inconsistent parsing state, parser was expected to be inside a style element,"
                " but the opening tag for this element does not start with '<style'")
            tag_type = "html-style-data"
        elif self.in_script_element and not self.in_style_element:
            assert starttag_text.startswith(
                "<script"
            ), ("Inconsistent parsing state, parser was expected to be inside a script element,"
                " but the opening tag for this element does not start with '<script'")
            tag_type = "html-script-data"
        else:
            tag_type = "html-other-data"
        self.tokens.append(Token(tag_type, None, data))

    def handle_decl(self, decl):
        self.tokens.append(Token("html-declaration", None, decl))

    def handle_pi(self, data):
        self.tokens.append(Token("html-processing-instructions", None, data))

    # The following tokens could also be extracted but are skipped.

    def handle_comment(self, data):
        # e.g. <!-- hello -->
        pass

    # HTMLParser is run with convert_charrefs which converts entity and
    # character references to corresponding Unicode characters (except in style/script contents).
    # Thus these can be viewed as data inside elements just like other text.
    def handle_entityref(self, name):
        # e.g. &lpar; &equals; &gt; etc.
        pass

    def handle_charref(self, name):
        # e.g. &#40; &#61; &#62; etc.
        pass
