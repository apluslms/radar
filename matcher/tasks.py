from django.conf import settings
from django.db import models
import celery
from celery.utils.log import get_task_logger

from matcher import matcher
from data.models import Exercise, Submission, TaskError


logger = get_task_logger(__name__)


@celery.shared_task(ignore_result=True)
def match_all_new_submissions_to_exercise(exercise_id):
    """
    Sequentially match all unmatched submissions (not marked invalid) to given exercise.
    """
    logger.info("Matching all submissions to exercise with id %d", exercise_id)
    exercise = Exercise.objects.get(pk=exercise_id)
    for submission in exercise.valid_unmatched_submissions:
        matcher.match(submission)


@celery.shared_task(ignore_result=True)
def match_new_submission(submission_id):
    if submission_id is None:
        # If this task is chained and the preceding task failed, it will pass None as id
        write_error("Cannot match submission with id None")
        return
    submission = Submission.objects.get(pk=submission_id)
    matcher.match(submission)


@celery.shared_task(ignore_result=True)
def match_all_submissions(submission_ids):
    """
    Sequentially match all submissions with given Submission instance ids.
    """
    for submission in Submission.objects.filter(pk__in=submission_ids):
        matcher.match(submission)


def write_error(message):
    logger.error(message)
    TaskError(package="matcher", error_string=message).save()
