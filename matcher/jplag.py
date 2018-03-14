import hashlib
import logging
from matcher.matcher import TokenMatchSet, TokenMatch

logger = logging.getLogger("radar.matcher")

def match(tokens_a, marks_a, tokens_b, marks_b, min_length):
    """
    Tries to cover a token string with substrings of at least a minimum length
    from the other token string. This "Greedy String Tiling" algorithm is
    credited to Wise, M. (1993) in Prechelt, L., Malpohl, G., Phlippsen, M.
    (2000) 'JPlag: Finding plagiarisms among a set of programs', [Online],
    University of Karlsruhe, Available:
    http://wwwipd.ira.uka.de/~prechelt/Biblio/jplagTR.pdf [8 Jul 2014].
    
    """
    matches = TokenMatchSet()
    if len(tokens_a) < min_length or len(tokens_b) < min_length:
        logger.debug("Token string shorter than minimum length")
        return matches

    # Take the shorter token string as A, the longer as B.
    reverse = len(tokens_b) < len(tokens_a)
    A = tokens_b if reverse else tokens_a
    B = tokens_a if reverse else tokens_b
    A_marks = list(marks_b) if reverse else list(marks_a)
    B_marks = list(marks_a) if reverse else list(marks_b)

    # Create a hash map of unmarked minimum length tiles in B.
    B_hash = {}
    for i in range(0, len(B) - min_length + 1):
        if B_marks[i]:
            continue
        h = hash_for_range(B, i, min_length)
        if h not in B_hash:
            B_hash[h] = []
        B_hash[h].append(i)

    # Iterate until no matches of minimum length exist.
    max_match = min_length + 1
    while max_match > min_length:
        max_match = min_length
        matchset = TokenMatchSet()

        # Travel each still unmarked index in A.
        for a in range(0, len(A) - min_length + 1):
            if A_marks[a]:
                continue

            # Start from possible and unmarked indexes in B.
            h = hash_for_range(A, a, min_length)
            if h not in B_hash:
                continue
            for b in B_hash[h]:

                # Find longest identical token tile.
                i = 0
                while a + i < len(A) and b + i < len(B) \
                    and A[a + i] == B[b + i] \
                    and not A_marks[a + i] and not B_marks[b + i]:
                    i += 1

                # Add non overlapping tile to iteration matches.
                if i == max_match:
                    if matchset.add_non_overlapping(TokenMatch(a, b, i)):
                        logger.debug("Found match %d=%d, length=%d", a, b, i)

                # Reset iteration matches with a longer match tile.
                elif i > max_match:
                    logger.debug("Reset matches %d=%d, length=%d", a, b, i)
                    matchset.clear()
                    matchset.add(TokenMatch(a, b, i))
                    max_match = i

        # Mark matched tokens and store tiles.
        for m in matchset.all():
            for i in range(0, m.length):
                A_marks[m.a + i] = True
                B_marks[m.b + i] = True
        matches.extend(matchset)

    logger.debug("Total %d matching tiles", matches.match_count())
    if reverse:
        return matches.reverse()
    return matches


def hash_for_range(tokens, index, length):
    """
    Calculates a hash for a token range.
    
    """
    return hashlib.md5(tokens[index:(index + length)].encode("utf-8")).digest()
