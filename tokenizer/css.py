import logging
import json

import tokenizer.util as util

logger = logging.getLogger("radar.tokenizer")

TOKEN_TYPE_TO_CHAR = util.parse_from_json("tokenizer/HTML_token_map.json")


def tokenize_no_string(source):
    """
    css.tokenize but return a list of tokens in place of the token string.
    """
    parsed = util.run(("node", "tokenizer/node_scripts/cssTokenizer.js"), source)
    data = json.loads(parsed.decode("utf-8"))
    return data["tokens"], data["indexes"]


def tokenize(source, config):
    """
    Runs the CSS tokenizer with Node.js in a subprocess and returns the token string and token index pairs.
    """
    try:
        tokens, indexes = tokenize_no_string(source)
        return ''.join(TOKEN_TYPE_TO_CHAR[t] for t in tokens), indexes
    except Exception as e:
        logger.info("Failed to tokenize: %s", e)
        return ("", [])
