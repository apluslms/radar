"""
This module implements an HTML parser that tokenizes HTML source code into custom
tokens, that are listed in TOKEN_TYPES.keys().
The parser uses HTMLParser from the standard library module html.parser,
and attaches a hook to its updatepos method in order to extract single dimensional
source mappings.
After parsing, the parser instance contains a list of Token namedtuple instances,
that contain the name of the token, a one dimensional source mapping,
and the raw content of the token.

Comments and whitespace are ignored.

Usage:
>>> source = "<!DOCTYPE html><html><head> ... "
>>> parser = TokenizingHTMLParser()
>>> # Start parsing
>>> parser.feed(source)
>>> # Generate a 2-tuple containing a string of single char tokens
>>> # and a JSON string of index pairs
>>> parser.export_tokens()
('¯MJ§°/', [[0, 15], [15, 21], [21, 27], [27, 34], [34, 36], [51, 57]])
>>> # The list of collected Token instances can also be accessed directly
>>> parser.tokens
[Token(type='declaration', range=[0, 15], data='DOCTYPE html'),
 Token(type='start-html', range=...),
 ...]
"""
import collections
import functools
import html.parser
import re

# TODO: there's alot of tokens now, maybe reduce the granularity by grouping? e.g.:
# https://www.w3.org/TR/2017/REC-html52-20171214/fullindex.html#element-content-categories
# https://www.w3.org/TR/2017/REC-html52-20171214/fullindex.html#element-interfaces

# Element tag names extracted from https://www.w3.org/TR/2017/REC-html52-20171214/fullindex.html#index-elements at 13.3.2018
TOKEN_TYPES = collections.OrderedDict([
    # Raw data element contents
    ('script-data', '!'),
    ('style-data', '"'),
    # Opening tags
    ('start-a', '#'),
    ('start-abbr', '$'),
    ('start-address', '%'),
    ('start-area', '&'),
    ('start-article', "'"),
    ('start-aside', '('),
    ('start-audio', ')'),
    ('start-b', '*'),
    ('start-base', '+'),
    ('start-bdi', ','),
    ('start-bdo', '-'),
    ('start-blockquote', '.'),
    ('start-body', '/'),
    ('start-br', '0'),
    ('start-button', '1'),
    ('start-canvas', '2'),
    ('start-caption', '3'),
    ('start-cite', '4'),
    ('start-code', '5'),
    ('start-col', '6'),
    ('start-colgroup', '7'),
    ('start-data', '8'),
    ('start-datalist', '9'),
    ('start-dd', ':'),
    ('start-del', ';'),
    ('start-details', '<'),
    ('start-dfn', '='),
    ('start-dialog', '>'),
    ('start-div', '?'),
    ('start-dl', '@'),
    ('start-dt', 'A'),
    ('start-em', 'B'),
    ('start-embed', 'C'),
    ('start-fieldset', 'D'),
    ('start-figcaption', 'E'),
    ('start-figure', 'F'),
    ('start-footer', 'G'),
    ('start-form', 'H'),
    ('start-h1', 'I'),
    ('start-h2', 'I'),
    ('start-h3', 'I'),
    ('start-h4', 'I'),
    ('start-h5', 'I'),
    ('start-h6', 'I'),
    ('start-head', 'J'),
    ('start-header', 'K'),
    ('start-hr', 'L'),
    ('start-html', 'M'),
    ('start-i', 'N'),
    ('start-iframe', 'O'),
    ('start-img', 'P'),
    ('start-input', 'Q'),
    ('start-ins', 'R'),
    ('start-kbd', 'S'),
    ('start-label', 'T'),
    ('start-legend', 'U'),
    ('start-li', 'V'),
    ('start-link', 'W'),
    ('start-main', 'X'),
    ('start-map', 'Y'),
    ('start-mark', 'Z'),
    ('start-meta', '['),
    ('start-meter', '\\'),
    ('start-nav', ']'),
    ('start-noscript', '^'),
    ('start-object', '_'),
    ('start-ol', '`'),
    ('start-optgroup', 'a'),
    ('start-option', 'b'),
    ('start-output', 'c'),
    ('start-p', 'd'),
    ('start-param', 'e'),
    ('start-picture', 'f'),
    ('start-pre', 'g'),
    ('start-progress', 'h'),
    ('start-q', 'i'),
    ('start-rb', 'j'),
    ('start-rp', 'k'),
    ('start-rt', 'l'),
    ('start-rtc', 'm'),
    ('start-ruby', 'n'),
    ('start-s', 'o'),
    ('start-samp', 'p'),
    ('start-script', 'q'),
    ('start-section', 'r'),
    ('start-select', 's'),
    ('start-small', 't'),
    ('start-source', 'u'),
    ('start-span', 'v'),
    ('start-strong', 'w'),
    ('start-style', 'x'),
    ('start-sub', 'y'),
    ('start-summary', 'z'),
    ('start-sup', '{'),
    ('start-table', '|'),
    ('start-tbody', '}'),
    ('start-td', '~'),
    ('start-template', '¡'),
    ('start-textarea', '¢'),
    ('start-tfoot', '£'),
    ('start-th', '¤'),
    ('start-thead', '¥'),
    ('start-time', '¦'),
    ('start-title', '§'),
    ('start-tr', '¨'),
    ('start-track', '©'),
    ('start-u', 'ª'),
    ('start-ul', '«'),
    ('start-var', '¬'),
    ('start-video', '\xad'),
    ('start-wbr', '®'),
    # Misc
    ('declaration', '¯'),
    ('other-data', '°'),
    ('processing-instructions', '±')
])

Token = collections.namedtuple("Token", ["type", "range", "data"])


# Add a hook to HTMLParser.updatepos that captures the single dimensional source
# mappings before they are converted to two dimensional, row-column mappings.
def updatepos_hook(updatepos):
    if hasattr(updatepos, "__wrapped__"):
        # Already wrapped
        return updatepos

    @functools.wraps(updatepos)
    def set_token_range_and_call_updatepos(parser, i, j, *args, **kwargs):
        if parser.tokens and parser.tokens[-1].range is None:
            # Replace the newest Token instance with an updated range
            parser.tokens[-1] = parser.tokens[-1]._replace(range=[i, j])
        return updatepos(parser, i, j, *args, **kwargs)

    return set_token_range_and_call_updatepos

html.parser.HTMLParser.updatepos = updatepos_hook(html.parser.HTMLParser.updatepos)


class TokenizingHTMLParser(html.parser.HTMLParser):
    """
    html.parser.HTMLParser subclass that accumulates custom HTML tokens
    (Token namedtuple instances) into a self.tokens list.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.reset()

    def all_tokens_valid(self):
        return all(t.type in TOKEN_TYPES and t.range is not None
                   for t in self.tokens)

    def export_tokens(self):
        return (''.join(TOKEN_TYPES[t.type] for t in self.tokens),
                [t.range for t in self.tokens])

    def reset(self):
        self.in_style_element = False
        self.in_script_element = False
        self.tokens = []
        self.errors = []
        # Redundant if this function is called from __init__,
        # but necessary if called explicitly.
        super().reset()

    def error(self, message):
        self.errors.append(message)

    def handle_starttag(self, tag, attrs):
        if tag == "style":
            self.in_style_element = True
        elif tag == "script":
            self.in_script_element = True
        token_type = "start-{:s}".format(tag)
        if token_type not in TOKEN_TYPES:
            self.error("Found a starting tag '{:s}', with exact content '{:s}', that does not have a token specified".format(tag, self.get_starttag_text()))
        else:
            self.tokens.append(Token(
                token_type,
                None,
                self.get_starttag_text()))

    def handle_endtag(self, tag):
        if tag == "style":
            self.in_style_element = False
        elif tag == "script":
            self.in_script_element = False

    def handle_data(self, data):
        starttag_text = self.get_starttag_text()
        tag_type = None
        if (self.in_style_element and
                not self.in_script_element and
                starttag_text.startswith("<style")):
            tag_type = "style-data"
        elif (self.in_script_element and
                  not self.in_style_element and
                  starttag_text.startswith("<script")):
            tag_type = "script-data"
        else:
            tag_type = "other-data"
        # Do not tokenize newlines and whitespace between tokens.
        if not re.fullmatch(r"^\s*$", data):
            self.tokens.append(Token(
                tag_type,
                None,
                data))

    def handle_decl(self, decl):
        self.tokens.append(Token(
            "declaration",
            None,
            decl))

    def handle_pi(self, data):
        self.tokens.append(Token(
            "processing-instructions",
            None,
            data))

    # The following tokens could also be extracted but are skipped.

    def handle_comment(self, data):
        # e.g. <!-- hello -->
        pass

    # HTMLParser is run with convert_charrefs which converts entity and
    # character references to Unicode characters (except in style/script contents).
    # Thus these can be viewed as data inside elements just like other text.
    def handle_entityref(self, name):
        # e.g. &lpar; &equals; &gt; etc.
        pass

    def handle_charref(self, name):
        # e.g. &#40; &#61; &#62; etc.
        pass

