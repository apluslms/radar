import logging
from tokenizer.html_parser import TokenizingHTMLParser

logger = logging.getLogger("radar.tokenizer")

def tokenize(source, config):
    """
    Tokenize HTML source using html_parser.TokenizingHTMLParser.
    """
    parser = TokenizingHTMLParser()
    try:
        token_string, indexes = parser.tokenize(source)
        return token_string, indexes
    except Exception as e:
        logger.error("Failed to tokenize: %s", e)
        if parser.errors:
            logger.error("Errors: %s", parser.errors)
        return ("", [])
