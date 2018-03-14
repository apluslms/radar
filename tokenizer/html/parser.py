"""
This module implements an HTML parser that tokenizes HTML source code into tokens
as defined in the token_types file.
The parser uses HTMLParser from the standard library module html.parser,
and attaches a hook to its updatepos method in order to extract single dimensional
source mappings.
After parsing, the parser instance contains a list of Token namedtuple instances,
that contain the name of the token, a one dimensional source mapping,
and the raw content of the token.

Comments and whitespace are ignored.

Usage:
>>> source = "<!DOCTYPE html> ... "
>>> parser = TokenizingHTMLParser()
>>> # Start parsing
>>> parser.feed(source)
>>> # Get list of Token instances
>>> parser.tokens
"""
import collections
import functools
import html.parser
import re


# Element tag names extracted from https://www.w3.org/TR/2017/REC-html52-20171214/fullindex.html#index-elements at 13.3.2018
TOKEN_TYPES = frozenset((
    # Raw data element contents
    "script-data",
    "style-data",
    # Opening tags
    "start-a",
    "start-abbr",
    "start-address",
    "start-area",
    "start-article",
    "start-aside",
    "start-audio",
    "start-b",
    "start-base",
    "start-bdi",
    "start-bdo",
    "start-blockquote",
    "start-body",
    "start-br",
    "start-button",
    "start-canvas",
    "start-caption",
    "start-cite",
    "start-code",
    "start-col",
    "start-colgroup",
    "start-data",
    "start-datalist",
    "start-dd",
    "start-del",
    "start-details",
    "start-dfn",
    "start-dialog",
    "start-div",
    "start-dl",
    "start-dt",
    "start-em",
    "start-embed",
    "start-fieldset",
    "start-figcaption",
    "start-figure",
    "start-footer",
    "start-form",
    "start-h1",
    "start-head",
    "start-header",
    "start-hr",
    "start-html",
    "start-i",
    "start-iframe",
    "start-img",
    "start-input",
    "start-ins",
    "start-kbd",
    "start-label",
    "start-legend",
    "start-li",
    "start-link",
    "start-main",
    "start-map",
    "start-mark",
    "start-meta",
    "start-meter",
    "start-nav",
    "start-noscript",
    "start-object",
    "start-ol",
    "start-optgroup",
    "start-option",
    "start-output",
    "start-p",
    "start-param",
    "start-picture",
    "start-pre",
    "start-progress",
    "start-q",
    "start-rb",
    "start-rp",
    "start-rt",
    "start-rtc",
    "start-ruby",
    "start-s",
    "start-samp",
    "start-script",
    "start-section",
    "start-select",
    "start-small",
    "start-source",
    "start-span",
    "start-strong",
    "start-style",
    "start-sub",
    "start-summary",
    "start-sup",
    "start-table",
    "start-tbody",
    "start-td",
    "start-template",
    "start-textarea",
    "start-tfoot",
    "start-th",
    "start-thead",
    "start-time",
    "start-title",
    "start-tr",
    "start-track",
    "start-u",
    "start-ul",
    "start-var",
    "start-video",
    "start-wbr",
    # Misc
    "declaration",
    "other-data",
    "processing-instructions",
))


Token = collections.namedtuple("Token", ["type", "range", "data"])


# Add hook to HTMLParser.updatepos that captures the single dimensional source
# mappings before they are converted two two dimensional, row-column mappings.
def updatepos_hook(updatepos):
    if hasattr(updatepos, "__wrapped__"):
        # Already wrapped
        return updatepos

    @functools.wraps(updatepos)
    def set_token_range_and_call_updatepos(parser, i, j, *args, **kwargs):
        if parser.tokens and parser.tokens[-1].range is None:
            # Replace the newest Token instance with an updated range
            parser.tokens[-1] = parser.tokens[-1]._replace(range=(i, j))
        return updatepos(parser, i, j, *args, **kwargs)

    return set_token_range_and_call_updatepos

html.parser.HTMLParser.updatepos = updatepos_hook(html.parser.HTMLParser.updatepos)


class TokenizingHTMLParser(html.parser.HTMLParser):
    """
    html.parser.HTMLParser subclass that accumulates custom HTML tokens
    (Token namedtuple instances) into a self.tokens list.
    Valid token types are listed in the module level TOKEN_TYPES set.

    Data inside raw text elements <script> and <style> will be extracted and
    tokenized separately using the JavaScript and CSS tokenizer, respectively.
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

    def error(self, message):
        self.errors.append(message)

    def handle_starttag(self, tag, attrs):
        if tag == "style":
            self.in_style_element = True
        elif tag == "script":
            self.in_script_element = True
        self.tokens.append(Token(
            "start-{tagname:s}".format(tagname=tag),
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
        if self.in_style_element and not self.in_script_element and starttag_text.startswith("<style"):
            tag_type = "style-data"
        elif self.in_script_element and not self.in_style_element and starttag_text.startswith("<script"):
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

    # HTMLParser is run with convert_charrefs which converts entity and character references to Unicode characters (except in style/script contents).
    # Thus these can be viewed as data inside elements just like other text.
    def handle_entityref(self, name):
        # e.g. &lpar; &equals; &gt; etc.
        pass

    def handle_charref(self, name):
        # e.g. &#40; &#61; &#62; etc.
        pass

