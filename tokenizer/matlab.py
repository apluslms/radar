import tokenizer.pygments_lib.helper as helper
from pygments.lexers.matlab import MatlabLexer

def tokenize(source: str, config=None) -> tuple[str, list]:
    """
    Tokenizes MATLAB code by replacing all token strings with a single character.
    Returns the tokenized string and index mappings (as a JSON string) of the tokens to the original string.
    """
    return helper.tokenize_code(source, lexer=MatlabLexer())
