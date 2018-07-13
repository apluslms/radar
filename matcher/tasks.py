from django.conf import settings
from django.db import models
import celery
from celery.utils.log import get_task_logger

from matchlib.tasks import match_to_others, match_all_combinations
from matcher.matcher import update_submission

from data.models import Exercise, Submission, TaskError


logger = get_task_logger(__name__)


@celery.shared_task(ignore_result=True)
def match_new_submission(submission_id):
    """
    Queue matching of given submission to all existing submissions.
    """
    if submission_id is None:
        # If this task is chained and the preceding task failed, it will pass None as id
        write_error("Cannot match submission with id None")
        return
    submission = Submission.objects.get(pk=submission_id)
    logger.info("Matching new submission %d", submission_id)
    config = {
        "minimum_match_length": submission.exercise.course.minimum_match_tokens,
        "minimum_similarity": settings.MATCH_STORE_MIN_SIMILARITY,
    }
    other_iter = (other.as_dict() for other in submission.submissions_to_compare)
    match_all_task = match_to_others.signature(
        (config, submission.as_dict(), other_iter),
        immutable=True
    )
    celery.chain(match_all_task, handle_match_results.s())()


@celery.shared_task(ignore_result=True)
def match_all_new_submissions_to_exercise(exercise_id):
    """
    Queue matching of all unmatched submissions (not marked invalid) to given exercise.
    """
    logger.info("Matching all submissions to exercise with id %d", exercise_id)
    config = {
        "minimum_match_length": submission.exercise.course.minimum_match_tokens,
        "minimum_similarity": settings.MATCH_STORE_MIN_SIMILARITY,
    }
    exercise = Exercise.objects.get(pk=exercise_id)
    to_compare_iter = (s.as_dict() for s in exercise.valid_unmatched_submissions)
    match_all_task = match_all_combinations.signature(
        (config, to_compare_iter),
        immutable=True,
        options={"queue": "large_tasks"}
    )
    celery.chain(match_all_task, handle_match_results.s())()


@celery.shared_task(ignore_result=True)
def handle_match_results(matches):
    """
    Create Comparison instances from matchlib results and update max similarities of the submission pairs.
    """
    for match in matches:
        a = Submission.objects.get(pk=match["id_a"])
        b = Submission.objects.get(pk=match["id_b"])
        similarity = match["similarity"]
        matches_json = match["match_indexes"]
        Comparison.objects.create(submission_a=a, submission_b=b, similarity=similarity, matches_json=matches_json)
        update_submission(a, similarity)
        update_submission(b, similarity)


def write_error(message):
    logger.error(message)
    TaskError(package="matcher", error_string=message).save()
