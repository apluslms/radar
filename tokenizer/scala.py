from tokenizer.tokenizer import run, indexes_to_json
import logging

logger = logging.getLogger("radar.tokenizer")

def tokenize(source, config):
    """
    Tokenizes Scala code to a sequence of high level structural tokens
    that are independent from names or values.
    
    Runs a scala subprocess.
    
    """
    try:
        parsed = run(("scala", "-cp", "tokenizer/scalariform:tokenizer/scalariform/scalariform.jar", "ScalariformTokens"), source)
        lines = parsed.decode("utf-8").split("\n", 1)
        return (lines[0].strip(), indexes_to_json(lines[1].strip()))
    except Exception as e:
        logger.info("Failed to tokenize: %s", e)
        return ("", "[]")
