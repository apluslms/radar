import itertools
from ..matchlib.matchers import greedy_string_tiling
from ..matchlib.util import TokenMatchSet
from multiprocessing import Pool
from functools import partial

# The keys that will be returned in the result of the matching functions
RESULT_KEYS = ["id_a", "id_b", "match_indexes", "similarity_a", "similarity_b"]

def _match_all_multiprocessing(
        config: dict[str, any], pairs_to_compare: tuple[dict[str, any], dict[str, any]]
    ) -> list[any] | None:
    """
    Compare all pairs and return an iterator over the matches.
    """

    # Get the configuration values
    minimum_match_length = config.get("minimum_match_length", 1)
    minimum_similarity = config.get("minimum_similarity", -1)
    similarity_precision = config.get("similarity_precision")
    optional_round = (lambda x: round(x, similarity_precision)) if similarity_precision is not None else (lambda x: x)

    # Get the pair of submissions to compare
    a = pairs_to_compare[0]
    b = pairs_to_compare[1]

    if min(a["longest_authored_tile"], b["longest_authored_tile"]) > minimum_match_length:

        # Get the string pair that will be compared
        tokens_a, tokens_b = a["tokens"], b["tokens"]

        # If the checksums match, we can skip the syntax token matching and create a full match of all tokens
        if "checksum" in a and "checksum" in b and a["checksum"] == b["checksum"]:
            # Skip syntax token matching and create a full match of all tokens
            matches = TokenMatchSet.full_match_from_length(min(len(tokens_a), len(tokens_b)))

            # Match of all tokens
            similarity_a = 1.0
            similarity_b = 1.0
        else:
            # Compare unique syntax tokens, ignoring marked tokens
            # If no marks are given, assume no tokens are marked
            marks_a = a.get("ignore_marks", '0' * len(tokens_a))
            marks_b = b.get("ignore_marks", '0' * len(tokens_b))
            matches = greedy_string_tiling(tokens_a, marks_a, tokens_b, marks_b, minimum_match_length)
            similarity_a = matches.token_count() / a["authored_token_count"] if a["authored_token_count"] > 0 else 0
            similarity_b = matches.token_count() / b["authored_token_count"] if b["authored_token_count"] > 0 else 0

        # If the similarity is above the minimum, return the match
        if similarity_a > minimum_similarity or similarity_b > minimum_similarity:
            return [a["id"], b["id"], matches.match_list(), optional_round(similarity_a), optional_round(similarity_b)]

    return None


def _match_all(config, pairs_to_compare):
    """
    Compare all pairs and return an iterator over the matches.
    """
    minimum_match_length = config.get("minimum_match_length", 1)
    minimum_similarity = config.get("minimum_similarity", -1)
    similarity_precision = config.get("similarity_precision")
    optional_round = (lambda x: round(x, similarity_precision)) if similarity_precision is not None else (lambda x: x)

    for a, b, in pairs_to_compare:
        if max(a["longest_authored_tile"], b["longest_authored_tile"]) < minimum_match_length:
            # Skip pairs that have too few unique tokens
            continue
        # Get the string pair that will be compared
        tokens_a, tokens_b = a["tokens"], b["tokens"]

        if "checksum" in a and "checksum" in b and a["checksum"] == b["checksum"]:
            # Skip syntax token matching and create a full match of all tokens
            matches = TokenMatchSet.full_match_from_length(min(len(tokens_a), len(tokens_b)))
            # Match of all tokens
            similarity_a = 1.0
            similarity_b = 1.0

        else:
            # Compare unique syntax tokens, ignoring marked tokens
            # If no marks are given, assume no tokens are marked
            marks_a = a.get("ignore_marks", '0' * len(tokens_a))
            marks_b = b.get("ignore_marks", '0' * len(tokens_b))
            matches = greedy_string_tiling(tokens_a, marks_a, tokens_b, marks_b, minimum_match_length)
            similarity_a = matches.token_count() / a["authored_token_count"] if a["authored_token_count"] > 0 else 0
            similarity_b = matches.token_count() / b["authored_token_count"] if b["authored_token_count"] > 0 else 0

        # If the similarity is above the minimum, return the match
        if similarity_a > minimum_similarity or similarity_b > minimum_similarity:
            yield  [a["id"], b["id"], matches.match_list(), optional_round(similarity_a), optional_round(similarity_b)]


def match_all_combinations(config: dict[str, any], string_data_iter: list[dict[str, any]]) -> list[list[any]]:
    """
    Given a configuration dict and an iterable of string data,
    do string similarity comparisons for all 2-combinations without replacement for the input data.
    Return an iterator over matches.

    try:
        raise Exception("Multiprocessing is not supported in this environment.")
        # Create a pool of workers to do the comparisons in parallel
        with Pool() as pool:
            results = pool.map(partial(_match_all_multiprocessing, config),
            itertools.combinations(string_data_iter, 2))

    except Exception as e:
        print(f"Error during multiprocessing: {e}")
        print(f"Matching in single process.")
        return _match_all(config, itertools.combinations(string_data_iter, 2))

    # Filter out None results
    return filter(lambda x: x is not None, results)
    """
    return _match_all(config, itertools.combinations(string_data_iter, 2))

def match_to_others(
    config: dict[str, any],
    string_data: dict[str, any],
    other_data_iter: list[dict[str, any]]
    ) -> list[list[any]]:
    """
    Compare one string data object to all other objects in other_data_iter.
    Return an iterator over matches.
    """

    # Create a pool of workers to do the comparisons in parallel
    with Pool() as pool:
        results = pool.map(partial(_match_all_multiprocessing, config),
                           ((string_data, other_data) for other_data in other_data_iter))

    # Filter out None results
    return filter(lambda x: x is not None, results)
