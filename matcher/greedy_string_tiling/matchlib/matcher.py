import celery
import itertools
from ..matchlib.matchers import greedy_string_tiling
from ..matchlib.util import TokenMatchSet
from multiprocessing import Pool
from functools import partial

from data.models import Exercise, Submission, Comparison
from matcher import matcher
from matcher.helper import swap_positions
import time

logger = celery.utils.log.get_task_logger(__name__)

# pylint: disable=inconsistent-return-statements
# pylint: disable=logging-fstring-interpolation
# pylint: disable=use-a-generator
# pylint: disable=logging-not-lazy
# pylint: disable=f-string-without-interpolation

# The keys that will be returned in the result of the matching functions
RESULT_KEYS = ["id_a", "id_b", "match_indexes", "similarity_a", "similarity_b"]

def _match_all_multiprocessing(
        config: dict[str, any], pairs_to_compare: tuple[dict[str, any], dict[str, any]]
    ):
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
            match = [
                a["id"], b["id"], matches.match_list(), optional_round(similarity_a), optional_round(similarity_b)
            ]
            return match


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
            match = [
                a["id"], b["id"], matches.match_list(), optional_round(similarity_a), optional_round(similarity_b)
            ]
            yield match


def match_all_combinations(config: dict[str, any], string_data_iter: list[dict[str, any]], delay: bool = False):
    """
    Given a configuration dict and an iterable of string data,
    do string similarity comparisons for all 2-combinations without replacement for the input data.
    Return an iterator over matches.
    """

    # Get exercise for logging
    exercise = Exercise.objects.get(pk=config["exercise_id"])
    config["exercise_name"] = exercise.name
    config["course_name"] = exercise.course.name

    try:
        logger.info("Multiprocessing: " + f"{exercise.name} | {exercise.course.name}")

        # Create a pool of workers to do the comparisons in parallel
        with Pool() as pool:
            combinations = itertools.combinations(string_data_iter, 2)

            if delay:
                #Get length of combinations for logging
                chunk_size = round(sum(1 for _ in itertools.combinations(string_data_iter, 2)) * 0.1)
                logger.info(f"Submissions pairs: {chunk_size * 10}")
                logger.info(f"Splitting pairs into chunks of size: {chunk_size}")

                tasks_results = []
                results = []

                # Process combinations in chunks
                for index, result in enumerate(
                        pool.imap(partial(_match_all_multiprocessing, config), combinations, chunksize=chunk_size)
                    ):
                    # Collect non-None results
                    if result is not None:
                        results.append(result)

                    # If we have enough results, send them to Celery
                    if len(results) >= chunk_size:
                        tasks_results.append(handle_celery_match_result.delay(results, config))
                        results = []

                    # Log progress
                    if (index + 1) % chunk_size == 0:
                        logger.info(f"Processed {index + 1} submission pairs...")

                # Handle any remaining results
                if len(results) > 0:
                    tasks_results.append(handle_celery_match_result.delay(results, config))

                logger.info(f"Processed {chunk_size * 10} submission pairs in total.")

                # Wait for all Celery tasks to finish
                tasks_done = False

                wait_for = 60

                while not tasks_done:
                    tasks_done = all([x.ready() for x in tasks_results])
                    if not tasks_done:
                        logger.info(f"Waiting for handle_celery_match_result:" +
                                    f" {exercise.name} | {exercise.course.name} to finish...")
                        time.sleep(wait_for)

            else:
                # Non-delayed processing, get all results at once
                results = pool.map(partial(_match_all_multiprocessing, config), combinations)

                # Filter out None results
                results = filter(lambda x: x is not None, results)

    except Exception as e:
        print(f"Error during multiprocessing: {e}")
        print("Matching in single process.")

        # Fallback to single-process matching in case of error
        results = _match_all(config, itertools.combinations(string_data_iter, 2))

        if delay:
            handle_celery_match_result.delay(list(results), config)

    if delay:
        # Set zero max similarity for all submissions that were not in results but were expecting results
        (
            exercise.submissions.filter(matching_start_time__isnull=False)
            .filter(matching_start_time=exercise.matching_start_time)
            .update(max_similarity=0, matched=True, matching_start_time=None)
        )
        exercise.matching_start_time = None
        exercise.save()

    else:
        return results


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


@celery.shared_task()
def handle_celery_match_result(matches: list[list[any]], config: dict[str, any]):
    """
    Create Comparison instances from matchlib results and update max similarities of the submission pairs.
    If the exercise with an id given in 'matches' has a different timestamp than the 'matches' object,
    all results will be discarded.
    """

    exercise_name = config.get("exercise_name")
    course_name = config.get("course_name")

    logger.info(
        f"Handling match results, got {len(matches)} pairs of submissions" +
        f" | {exercise_name} | {course_name}"
    )

    for match in matches:
        # Get keys for the matchlib results
        id_a = match[0]
        id_b = match[1]
        matches_json = match[2]
        similarity_a = match[3]
        similarity_b = match[4]

        a = Submission.objects.get(pk=id_a)
        b = Submission.objects.get(pk=id_b)
        if a != b and a.student != b.student:

            logger.info(
                f"Handling match result for: {a.id} & {b.id}" +
                f" | {exercise_name} | {course_name}"
            )

            # Create Comparison instances for both submissions
            Comparison.objects.create(
                submission_a=a,
                submission_b=b,
                similarity=similarity_a,
                matches_json=matches_json,
            )
            Comparison.objects.create(
                submission_a=b,
                submission_b=a,
                similarity=similarity_b,
                matches_json=swap_positions(matches_json),
            )

            # Update max similarity for both submissions
            matcher.update_submission(a, similarity_a, b)
            matcher.update_submission(b, similarity_b, a)


#https://stackoverflow.com/questions/312443/how-do-i-split-a-list-into-equally-sized-chunks
def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]
