from django.conf import settings
from django.db import models
import celery
from celery.utils.log import get_task_logger

from matcher import matcher
from data.models import Exercise, Submission


logger = get_task_logger(__name__)


@celery.shared_task(ignore_result=True)
def match_all_new_submissions_to_exercise(exercise_id):
    """
    Sequentially match all unmatched submissions to given exercise.
    """
    logger.info("Matching all submissions to exercise with id %d", exercise_id)
    exercise = Exercise.objects.get(pk=exercise_id)
    for submission in exercise.unmatched_submissions:
        matcher.match(submission)


@celery.shared_task(ignore_result=True)
def match_new_submission(submission_id):
    submission = Submission.objects.get(pk=submission_id)
    matcher.match(submission)


@celery.shared_task(ignore_result=True)
def match_all_submissions(submission_ids):
    """
    Sequentially match all submissions with given Submission instance ids.
    """
    for submission in Submission.objects.filter(pk__in=submission_ids):
        matcher.match(submission)


# @celery.shared_task(ignore_result=True)
# def match_all_missing_comparisons(submission_id):
#     """
#     Ensure a submission has been compared against all other submissions of the same exercise and create missing comparisons if there are any.
#     """
#     # TODO implement
#     # TODO run only on 1 hour old submissions
#     submission = Submission.objects.get(pk=submission_id)
#     all_submissions = Submission.objects.filter(exercise=submission.exercise)

