import logging
import json
from tokenizer.html_parser import TokenizingHTMLParser

logger = logging.getLogger("radar.tokenizer")

def tokenize(source, config):
    """
    Tokenize HTML source using html_parser.TokenizingHTMLParser.
    Currently tokenizes contents in script and style tags only as other-data.
    """
    parser = TokenizingHTMLParser()
    try:
        parser.feed(source)
        token_string, indexes = parser.export_tokens()
        return token_string, json.dumps(indexes)
    except Exception as e:
        logger.error("Failed to tokenize: %s", e)
        if parser.errors:
            logger.error("Errors: %s", parser.errors)
        return ("", "[]")
