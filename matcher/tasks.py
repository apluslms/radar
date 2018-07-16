from django.conf import settings
import celery
from celery.utils.log import get_task_logger

from matchlib.tasks import match_to_others, match_all_combinations
from matcher import matcher

from data.models import Exercise, Submission, TaskError, Comparison


logger = get_task_logger(__name__)


def match_exercise(exercise):
    """
    Put tasks on the queue for matching all submissions to exercise.
    """
    submission_ids = [s.id for s in exercise.valid_unmatched_submissions]
    match_all_to_template = (match_against_template.si(sid) for sid in submission_ids)
    match_all_to_each_other = match_all_new_submissions_to_exercise.si(exercise.id)
    # Match all submissions in parallel to the exercise template, synchronize, and match all submissions to exercise
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
        "similarity_precision": settings.SIMILARITY_PRECISION,
    }
    others = [other.as_dict() for other in submission.submissions_to_compare]
    match_all_task = match_to_others.signature(
        (config, submission.as_dict(), others),
        immutable=True
    )
    celery.chain(match_all_task, handle_match_results.s())()


@celery.shared_task(ignore_result=True)
def match_all_new_submissions_to_exercise(exercise_id):
    """
    Queue matching of all unmatched submissions (not marked invalid) to given exercise.
    Also matches every submission to the exercise template.
    """
    logger.info("Matching all submissions to exercise with id %d", exercise_id)
    exercise = Exercise.objects.get(pk=exercise_id)
    config = {
        "minimum_match_length": exercise.course.minimum_match_tokens,
        "minimum_similarity": settings.MATCH_STORE_MIN_SIMILARITY,
        "similarity_precision": settings.SIMILARITY_PRECISION,
    }
    compare_list = [s.as_dict() for s in exercise.valid_unmatched_submissions]
    match_all_task = match_all_combinations.signature(
        (config, compare_list),
        immutable=True
    )
    celery.chain(match_all_task, handle_match_results.s())()


@celery.shared_task(ignore_result=True)
def handle_match_results(matches):
    """
    Create Comparison instances from matchlib results and update max similarities of the submission pairs.
    """
    logger.info("Handling %d match results", len(matches["results"]))
    meta = matches["meta"]
    id_a_key = meta.index("id_a")
    id_b_key = meta.index("id_b")
    similarity_key = meta.index("similarity")
    matches_json_key = meta.index("match_indexes")
    for match in matches["results"]:
        a = Submission.objects.get(pk=match[id_a_key])
        b = Submission.objects.get(pk=match[id_b_key])
        similarity = match[similarity_key]
        matches_json = match[matches_json_key]
        Comparison.objects.create(submission_a=a, submission_b=b, similarity=similarity, matches_json=matches_json)
        matcher.update_submission(a, similarity)
        matcher.update_submission(b, similarity)


def write_error(message):
    logger.error(message)
    TaskError(package="matcher", error_string=message).save()
