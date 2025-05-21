import tokenizer.pygments_lib.helpers as helpers
from pygments.lexers.jvm import ScalaLexer

def tokenize(source: str, config=None):
    """
    Tokenizes Scala code by replacing all token strings with a single character.
    Returns the tokenized string and index mappings (as a JSON string) of the tokens to the original string.
    """
    return helpers.tokenize_code(source, lexer=ScalaLexer())
