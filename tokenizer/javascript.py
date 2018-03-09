import logging
import json

from tokenizer.tokenizer import run

logger = logging.getLogger("radar.tokenizer")

def tokenize(source, config):
    """
    Runs the JavaScript tokenizer with Node.js in a subprocess and returns the token string and token index pairs as a JSON string.
    """
    try:
        parsed = run(("node", "tokenizer/esprima/tokenizer.js"), source)
        data = json.loads(parsed.decode("utf-8"))
        return data["tokens"], json.dumps(data["indexes"])
    except Exception as e:
        logger.info("Failed to tokenize: %s", e)
        return ("", "[]")
