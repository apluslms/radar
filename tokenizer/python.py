import io
import json
import logging
import tokenize as stdlib_tokenize

logger = logging.getLogger("radar.tokenizer")


# Token types which are dropped from the tokenized string
SKIP_TOKENS = {
    stdlib_tokenize.COMMENT,
    # As opposed to NEWLINE tokens at the end of lines, NL tokens are simply "air between lines".
    stdlib_tokenize.NL,
    # Tokens which have no visible strings.
    stdlib_tokenize.ENCODING,
    stdlib_tokenize.ENDMARKER,
    stdlib_tokenize.DEDENT,
}


def tok_name_single_char(toktype):
    """
    Returns a single character representation of the given token type.
    Starts from '0'.
    """
    return chr(toktype + 48)


def token_generator_from_source(source):
    """
    Returns a generator of tokenize.TokenInfo namedtuples, tokenized from source.
    """
    readable_source = io.BytesIO(source.encode("utf-8")).readline
    return stdlib_tokenize.tokenize(readable_source)


def tokenize_no_indexes(source):
    """
    Optimization of tokenize.
    Returns only the tokenized string, without index mappings to the source.
    """
    try:
        token_generator = token_generator_from_source(source)
        # utf-8 is default for the str-type
        tokenized_source = ""

        for source_token in token_generator:
            toktype = source_token.exact_type
            if toktype not in SKIP_TOKENS:
                tokenized_source += tok_name_single_char(toktype)

        return tokenized_source

    except Exception as e:
        logger.error("Failed to tokenize Python source, %s", e)
        return ""


def tokenize(source, config=None):
    """
    Tokenizes Python code by replacing all token strings with a single character.
    Returns the tokenized string and index mappings (as a JSON string) of the tokens to the original string.
    """
    try:
        token_generator = token_generator_from_source(source)

        indexes = []
        # utf-8 is default for the str-type
        tokenized_source = ""

        # stdlib_tokenize.tokenize works with two-dimensional indexes,
        # which need to be converted into one dimension.
        index_offset = prevrow = prevcol = 0
        prevline = ""

        for source_token in token_generator:
            srow, scol = source_token.start
            erow, ecol = source_token.end
            toktype = source_token.exact_type
            string = source_token.string

            # If this token is on the same line as the previous token,
            # offset by the column difference of the tokens.
            if srow == prevrow:
                index_offset += scol - prevcol
            # If this token is below the previous token,
            # offset by the starting column of this token.
            elif srow > prevrow:
                index_offset += scol
                # There might be whitespace to the right of the last column position
                # if the line ends with an escaped newline character.
                previous_row_whitespace = len(prevline) - prevcol
                if previous_row_whitespace > 0:
                    index_offset += previous_row_whitespace
            # This is probably redundant.
            else:
                raise Exception("Unexpected Python token positions, {}".format(source_token))

            start_index = index_offset
            end_index = start_index + len(string)

            if srow == erow:
                index_offset += ecol - scol
            else:
                index_offset += len(string)

            if toktype not in SKIP_TOKENS:
                tokenized_source += tok_name_single_char(toktype)
                indexes.append([start_index, end_index])

            prevrow, prevcol = erow, ecol
            prevline = source_token.line

        logger.info("Returning tokenized Python: %s", repr(tokenized_source))
        return tokenized_source, json.dumps(indexes)

    except Exception as e:
        logger.info("Failed to tokenize Python source, %s", e)
        return "", "[]"

