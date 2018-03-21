import logging

from tokenizer.util import run

logger = logging.getLogger("radar.tokenizer")


def index_string_to_list(line):
    """
    Parses data from a line formatted: <b:Int>-<e:Int>,<b:Int>-<e:Int>,...

    @param line an input line str
    @return json serializable list of lists
    """
    return [[int(c) for c in pair.split("-")]
            for pair in line.split(",")]


def tokenize(source, config):
    """
    Tokenizes Scala code to a sequence of high level structural tokens
    that are independent from names or values.

    Runs a scala subprocess.

    """
    try:
        parsed = run(("scala", "-cp", "tokenizer/scalariform:tokenizer/scalariform/scalariform.jar", "ScalariformTokens"), source)
        lines = parsed.decode("utf-8").split("\n", 1)
        return lines[0].strip(), index_string_to_list(lines[1].strip())
    except Exception as e:
        logger.info("Failed to tokenize: %s", e)
        return ("", [])
