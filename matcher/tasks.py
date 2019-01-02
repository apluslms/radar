from django.conf import settings
import celery
from celery.utils.log import get_task_logger

# Matchlib can also be deployed to a Kubernetes node, easing the task load by allowing elastic parallel task processing
from matchlib.tasks import match_to_others, match_all_combinations
from matcher import matcher

from data.models import Exercise, Submission, TaskError, Comparison


logger = get_task_logger(__name__)


def match_exercise(exercise):
    """
    Put tasks on the queue for matching all submissions to exercise.
    """
    if exercise.matching_start_time:
        logger.error("Exercise %s currently has submissions that are being matched, wait for their completion or clear all submissions")
        return
    submission_ids = (s.id for s in exercise.valid_unmatched_submissions)
    match_all_to_template = (match_against_template.si(sid) for sid in submission_ids)
    match_all_to_each_other = match_all_new_submissions_to_exercise.si(exercise.id)
    # For all submissions:
    #   - match in parallel to the exercise template,
    #   - synchronize,
    #   - match in parallel all submissions
    #   - synchronize,
    #   - handle all results when matching is complete
    celery.chord(match_all_to_template)(match_all_to_each_other)


@celery.shared_task
def match_against_template(submission_id):
    """
    Create template comparison for submission.
    """
    submission = Submission.objects.get(pk=submission_id)
    template_comparison = matcher.match_against_template(submission)
    template_comparison.save()


@celery.shared_task(ignore_result=True)
def match_all_new_submissions_to_exercise(exercise_id):
    """
    Match all submissions to Exercise with a given id.
    The Exercise and all submissions will have their matching_start_time timestamps synchronized, which allows checking which submissions got results after matching finishes.
    Also matches every submission to the exercise template.
    The resulting matching task is JSON serializable and can be consumed by any deployed matchlib instance.
    """
    logger.info("Matching all submissions to exercise with id %d", exercise_id)
    exercise = Exercise.objects.get(pk=exercise_id)
    if exercise.matching_start_time is not None:
        logger.warning("Exercise %s is already expecting results. This will override the timestamp and start a new matching task. If the old task returns with results, those results are discarded.", exercise)
    exercise.set_matches_pending_timestamp_to_now()
    config = {
        "minimum_match_length": exercise.course.minimum_match_tokens,
        "minimum_similarity": settings.MATCH_STORE_MIN_SIMILARITY,
        "similarity_precision": settings.SIMILARITY_PRECISION,
        "exercise_id": exercise_id,
        # If this timestamp does not match exercise.matching_start_time when the results return, all results will be discarded
        "matching_start_time": exercise.matching_start_time.isoformat(),
    }
    compare_list = [s.as_dict() for s in exercise.submissions_currently_matching]
    match_all_task = match_all_combinations.signature(
        (config, compare_list),
        immutable=True
    )
    # Match all, then handle results when all matches are available
    celery.chain(match_all_task, handle_match_results.s())()


@celery.shared_task(ignore_result=True)
def handle_match_results(matches):
    """
    Create Comparison instances from matchlib results and update max similarities of the submission pairs.
    If the exercise with an id given in 'matches' has a different timestamp than the 'matches' object, all results will be discarded.
    """
    logger.info("Handling match results, got %d pairs of submissions", len(matches["results"]))
    exercise = Exercise.objects.get(pk=matches["config"]["exercise_id"])
    expected_result_count = exercise.submissions_currently_matching.count()
    if expected_result_count == 0:
        logger.error("Exercise %s is not expecting match results", exercise)
        return
    logger.info("Exercise %s is expecting match results for %d submissions", exercise, expected_result_count)
    if exercise.matching_start_time.isoformat() != matches["config"]["matching_start_time"]:
        logger.error(
            "Exercise %s is expecting match results with timestamp %s, but results have timestamp %s. Discarding this list of results.",
            exercise,
            exercise.matching_start_time.isoformat(),
            matches["config"]["matching_start_time"]
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
        Comparison.objects.create(submission_a=a, submission_b=b, similarity=similarity, matches_json=matches_json)
        matcher.update_submission(a, similarity)
        matcher.update_submission(b, similarity)
    logger.info("Match results processed for %d submissions", len(submissions_updated))
    # Set zero max similarity for all submissions that were not in results but were expecting results
    no_result_count = (exercise.submissions
        .filter(matching_start_time__isnull=False)
        .filter(matching_start_time=exercise.matching_start_time)
        .update(max_similarity=0, matched=True, matching_start_time=None))
    logger.info("No match results for %d submissions", no_result_count)
    exercise.matching_start_time = None
    exercise.save()


def write_error(message, namespace):
    logger.error(message)
    TaskError(package="matcher", namespace=namespace, error_string=message).save()
