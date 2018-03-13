import html
import collections


TOKEN_TYPES = {
    "declaration",
    "start-{tagname:s}",
    "end-{tagname:s}",
    "style-data",
    "script-data",
    "other-data",
    "processing-instructions"
}


Token = collections.namedtuple("Token", ["type", "start", "end", "data"])


class TokenizingHTMLParser(html.parser.HTMLParser):
    """
    Data inside raw text elements <script> and <style> will be extracted and tokenized separately using the JavaScript and CSS tokenizer, respectively.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.in_style = False
        self.in_script = False
        self.tokens = []

    # TODO ignores linebreaks
    def _offset_column_position(self, offset):
        return self.getpos()[0], self.getpos()[1] + offset

    def handle_starttag(self, tag, attrs):
        # print("Start tag:", tag, " with text: ", self.get_starttag_text())
        if tag == "style":
            self.in_style = True
        elif tag == "script":
            self.in_script = True
        self.tokens.append(Token(
            "start-{tagname:s}".format(tagname=tag),
            self.getpos(),
            self._offset_column_position(len(self.get_starttag_text())),
            self.get_starttag_text()))
        # print("start-%s" % tag, " from ", self.getpos(), " to ", self._offset_column_position(len(self.get_starttag_text())))

    def handle_endtag(self, tag):
        if tag == "style":
            self.in_style = False
        elif tag == "script":
            self.in_script = False
        # tag characters + forward slash and a pair of angle brackets
        endtag_text_length = len(tag) + 3
        self.tokens.append(Token(
            "end-{tagname:s}".format(tagname=tag),
            self.getpos(),
            self._offset_column_position(endtag_text_length),
            tag))
        # print("end-%s" % tag, " from ", self.getpos(), " to ", self._offset_column_position(endtag_text_length))

    def handle_data(self, data):
        starttag_text = self.get_starttag_text()
        tag_type = None
        if self.in_style and not self.in_script and starttag_text.startswith("<style"):
            tag_type = "style-data"
        elif self.in_script and not self.in_style and starttag_text.startswith("<script"):
            tag_type = "script-data"
        else:
            tag_type = "other-data"
        self.tokens.append(Token(
            tag_type,
            self.getpos(),
            self._offset_column_position(len(data)),
            data))
        # print(" from ", self.getpos(), " to ", end_pos)

    def handle_decl(self, decl):
        self.tokens.append(Token(
            "declaration",
            self.getpos(),
            self._offset_column_position(len(decl)),
            decl))
        # print("declaration from ", self.getpos(), " to ", self._offset_column_position(len(decl)))

    def handle_pi(self, data):
        self.tokens.append(Token(
            "processing-instructions",
            self.getpos(),
            self._offset_column_position(len(data)),
            data))
        # print("processing-instructions from ", self.getpos(), " to ", self._offset_column_position(len(data)))

    # The following could be tokenized but are skipped.

    def handle_comment(self, data):
        # e.g. <!-- hello -->
        pass

    # HTMLParser is run with convert_charrefs which converts entity and character references to Unicode characters (except in style/script contents).
    def handle_entityref(self, name):
        # e.g. &lpar; &equals; &gt; etc.
        pass

    def handle_charref(self, name):
        # e.g. &#40; &#61; &#62; etc.
        pass


