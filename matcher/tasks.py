from django.conf import settings

import celery
from celery.utils.log import get_task_logger

# Matchlib can also be deployed to a Kubernetes node, easing the task load by allowing elastic parallel task processing
from matchlib.tasks import match_all_combinations
from matcher import matcher

from data.models import Exercise, Submission, TaskError, Comparison


logger = get_task_logger(__name__)


@celery.shared_task(ignore_result=True)
def match_exercise(exercise_id, delay=True):
    """
    Match all valid, yet unmatched submissions for a given exercise.
    """
    exercise = Exercise.objects.get(pk=exercise_id)
    for submission in exercise.submissions_currently_matching:
        match_against_template(submission.id)
    if delay:
        match_all_new_submissions_to_exercise.delay(exercise_id)
    else:
        match_all_new_submissions_to_exercise(exercise_id, False)


@celery.shared_task(ignore_result=True)
def match_against_template(submission_id):
    """
    Create template comparison for submission.
    """
    submission = Submission.objects.get(pk=submission_id)
    template_comparison = matcher.match_against_template(submission)
    template_comparison.save()


@celery.shared_task(ignore_result=True)
def match_all_new_submissions_to_exercise(exercise_id, delay=True):
    """
    Match all submissions to Exercise with a given id.
    The exercise and all its submissions must have their matching_start_time timestamps synchronized before
    this task is started, otherwise this does nothing. Also matches every submission to the exercise template.
    The resulting matching task is JSON serializable and can be consumed by any deployed matchlib instance.
    """
    logger.info("Matching all submissions to exercise with id %d", exercise_id)
    exercise = Exercise.objects.get(pk=exercise_id)
    if exercise.matching_start_time is None:
        logger.error(
            "Exercise %s has a None matching_start_time timestamp. E.g. the exercise does not expect results."
        )
        return
    config = {
        "minimum_match_length": exercise.minimum_match_tokens,
        "minimum_similarity": settings.MATCH_STORE_MIN_SIMILARITY,
        "similarity_precision": settings.SIMILARITY_PRECISION,
        "exercise_id": exercise_id,
        # This timestamp is used as a checksum of expected results when the results come in
        "matching_start_time": exercise.matching_start_time,
    }
    # JSON serializable list of submissions
    compare_list = [s.as_dict() for s in exercise.submissions_currently_matching]
    # Match all, then handle results when all matches are available
    if delay:
        match_all_task = match_all_combinations.si(config, compare_list)
        celery.chain(match_all_task, handle_match_results.s())()
    else:
        matches = match_all_combinations(config, compare_list)
        handle_match_results(matches)


@celery.shared_task(ignore_result=True)
def handle_match_results(matches):
    """
    Create Comparison instances from matchlib results and update max similarities of the submission pairs.
    If the exercise with an id given in 'matches' has a different timestamp than the 'matches' object,
    all results will be discarded.
    """
    logger.info(
        "Handling match results, got %d pairs of submissions", len(matches["results"])
    )
    exercise = Exercise.objects.get(pk=matches["config"]["exercise_id"])
    expected_result_count = exercise.submissions_currently_matching.count()
    if expected_result_count == 0:
        logger.error("Exercise %s is not expecting match results", exercise)
        return
    logger.info(
        "Exercise %s is expecting match results for %d submissions",
        exercise,
        expected_result_count,
    )
    if exercise.matching_start_time != matches["config"]["matching_start_time"]:
        logger.warning(
            "Exercise %s is expecting match results with timestamp %s, but results have timestamp %s."
            " Discarding this list of results.",
            exercise,
            exercise.matching_start_time,
            matches["config"]["matching_start_time"],
        )
        return

    submissions_updated = set()
    meta = matches["meta"]
    id_a_key = meta.index("id_a")
    id_b_key = meta.index("id_b")
    similarity_key = meta.index("similarity")
    matches_json_key = meta.index("match_indexes")
    # Update max similarity for every submission
    for match in matches["results"]:
        a = Submission.objects.get(pk=match[id_a_key])
        b = Submission.objects.get(pk=match[id_b_key])
        if a == b or a.student == b.student:
            continue
        submissions_updated.add(id_a_key)
        submissions_updated.add(id_b_key)
        similarity = match[similarity_key]
        matches_json = match[matches_json_key]
        Comparison.objects.create(
            submission_a=a,
            submission_b=b,
            similarity=similarity,
            matches_json=matches_json,
        )
        matcher.update_submission(a, similarity, b)
        matcher.update_submission(b, similarity, a)
    logger.info("Match results processed for %d submissions", len(submissions_updated))
    if len(submissions_updated) < expected_result_count:
        num_missing = expected_result_count - len(submissions_updated)
        if "minimum_similarity" in matches["config"]:
            logger.info(
                "Assuming missing %d submissions had a similarity lower than %.2f",
                num_missing,
                matches["config"]["minimum_similarity"],
            )
        else:
            logger.warning(
                "Missing %d submissions which had no similarity results, but no minimum similarity threshold"
                " for filtering was found in the configuration"
            )
    # Set zero max similarity for all submissions that were not in results but were expecting results
    (
        exercise.submissions.filter(matching_start_time__isnull=False)
        .filter(matching_start_time=exercise.matching_start_time)
        .update(max_similarity=0, matched=True, matching_start_time=None)
    )
    exercise.matching_start_time = None
    exercise.save()


def write_error(message, namespace):
    logger.error(message)
    TaskError(package="matcher", namespace=namespace, error_string=message).save()
