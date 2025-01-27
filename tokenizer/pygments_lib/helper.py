import logging
import tokenizer.pygments_lib.token_type as token_type
from pygments.lexer import RegexLexer

logger = logging.getLogger("radar.tokenizer")

# Token types which are dropped from the tokenized string
SKIP_TOKENS ={
    'TOKEN_COMMENT',
    'TOKEN_COMMENT_HASHBANG',
    'TOKEN_COMMENT_MULTILINE',
    'TOKEN_COMMENT_SINGLE',
    'TOKEN_COMMENT_SPECIAL',

    'TOKEN_TEXT_WHITESPACE',
}


def token_type_to_chr(token_type: int) -> str:
    """
    Returns a single character representation of the given token type.
    Starts from '!'.
    """
    return chr(token_type + 33)


def tokenize_code(source: str, lexer: RegexLexer) -> tuple[str, list]:
    """
    Tokenizes code based on the lexer given by replacing all token strings with a single character.
    Returns the tokenized string and index mappings (as a JSON string) of the tokens to the original string.
    """

    indexes = []
    # utf-8 is default for the str-type
    tokenized_source = ""

    # Get tokens from the lexer
    tokens = lexer.get_tokens_unprocessed(source)

    # Process tokens
    for token in tokens:
        # Convert token type to the name of the token type constant
        token_type_clean = str(token[1]).replace('.', '_').upper()

        # Skip tokens that do not change the semantics of the code
        if token_type_clean not in SKIP_TOKENS:
            try:
                token_type_value = token_type.__dict__[token_type_clean]

                # Check for lexer error
                if token_type_value == 4:
                    raise Exception("Token type is not supported")

                # Convert token type to a single character
                tokenized_source += token_type_to_chr(token_type_value)

            except KeyError:
                logger.error('Unknown token type: %s', token_type_clean)
                raise
            except Exception as e:
                logger.error('Error tokenizing source code: %s', e)
                raise

            # Save the start and end index of the token
            indexes.append([token[0], token[0] + len(token[2])])

    return tokenized_source, indexes
