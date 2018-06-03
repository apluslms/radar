import logging
import gst

from matcher.matcher import TokenMatchSet, TokenMatch

logger = logging.getLogger("radar.matcher")


def bitstring(bools):
    """
    Return a string of bits from an iterable over booleans.
    """
    return ''.join(str(int(b)) for b in bools)


def match(tokens_a, marks_a, tokens_b, marks_b, min_length):
    """
    Wrapper of the C++ extension gst.match, which implements the Running Karp-Rabin Greedy String Tiling algorithm by Michael J. Wise.
    """
    matches = TokenMatchSet()
    if len(tokens_a) < min_length or len(tokens_b) < min_length:
        logger.debug("Token string shorter than minimum length")
        return matches

    # Choose the shorter token string to be the pattern and the longer as text
    reverse = len(tokens_b) < len(tokens_a)
    pattern = tokens_b if reverse else tokens_a
    text = tokens_a if reverse else tokens_b
    pattern_marks = bitstring(marks_b if reverse else marks_a)
    text_marks = bitstring(marks_a if reverse else marks_b)

    match_list = gst.match(pattern, pattern_marks, text, text_marks, min_length)
    if reverse:
        matches.store = [TokenMatch(match[1], match[0], match[2]) for match in match_list]
    else:
        matches.store = [TokenMatch(*match) for match in match_list]

    logger.debug("Total %d matching tiles", matches.match_count())
    return matches
