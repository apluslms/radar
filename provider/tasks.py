"""
Celery tasks for asynchronous submission processing.
Contains some hard-coded A+ specific stuff that should be generalized.
"""
import hashlib

import celery
from celery.utils.log import get_task_logger

import radar.config as config_loaders
from matcher import matcher, tasks as matcher_tasks
from provider import aplus
from data.models import Course, Submission, Exercise, TaskError
from tokenizer import tokenizer


logger = get_task_logger(__name__)


# class ProviderTaskError(Exception):
#     pass


def create_and_match(submission_key, course_key, submission_api_url):
    """
    Convenience function for chaining create_submission with matcher.tasks.match_new_submission.
    """
    # Make celery signatures from tasks
    create = create_submission.si(submission_key, course_key, submission_api_url)
    match = matcher_tasks.match_new_submission.s()
    # Spawn two tasks to run sequentially:
    # First one creates a new submission and passes the created id to the second one, which matches the submission
    celery.chain(create, match)()


# This task should not ignore its result since it is needed for synchronization when using celery.chord
# Highly I/O bound task, recommended to be consumed by several workers
@celery.shared_task(ignore_result=False)
def create_submission(submission_key, course_key, submission_api_url):
    """
    Fetch submission data for a new submission with provider key submission_key from a given API url, create new submission, and tokenize submission content.
    Return submission id (int) on success and None if skipped.
    """
    course = Course.objects.get(key=course_key)
    if Submission.objects.filter(key=submission_key).exists():
        # raise ProviderTaskError("Submission with key %s already exists, will not create a duplicate." % submission_key)
        write_error("Submission with key %s already exists, will not create a duplicate." % submission_key)
        return

    # We need someone with a token to the A+ API.
    api_client = aplus.get_api_client(course)
    data = api_client.load_data(submission_api_url)
    exercise_data = data["exercise"]
    exercise_name = exercise_data["display_name"]

    # Check if exercise is configured for Radar, if not, skip to next.
    radar_config = aplus.get_radar_config(exercise_data)
    if radar_config is None:
        return

    # Get or create exercise configuration
    exercise = course.get_exercise(str(exercise_data["id"]))
    if exercise.name == "unknown":
        # Get template source
        radar_config["template_source"] = radar_config["get_template_source"]()
        exercise.set_from_config(radar_config)
        exercise.save()

    # A+ allows more than one submitter for a single submission
    # TODO: if there are more than one unique submitters,
    # set as approved plagiate and show this in the UI
    ## for submitter_id in _decode_students(data["submitters"]):
    submitter_id = "_".join(aplus._decode_students(data["submitters"]))
    student = course.get_student(str(submitter_id))
    submission = Submission.objects.create(
        key=submission_key,
        exercise=exercise,
        student=student,
        provider_url=data["html_url"],
        provider_submission_time=data["submission_time"],
        grade=data["grade"],
    )

    provider_config = config_loaders.provider_config(course.provider)
    get_submission_text = config_loaders.configured_function(
        provider_config,
        "get_submission_text"
    )
    submission_text = get_submission_text(submission, provider_config)
    if submission_text is None:
        # raise ProviderTaskError("Failed to get submission text for submission %s" % submission)
        submission.invalid = True
        submission.save()
        write_error("Failed to get submission text for submission %s" % submission)
        return

    tokens, json_indexes = tokenizer.tokenize_submission(
        submission,
        submission_text,
        provider_config
    )
    if not tokens:
        # raise ProviderTaskError("Tokenizer returned an empty token string for submission %s, will not save submission" % submission_key)
        submission.invalid = True
        submission.save()
        write_error("Tokenizer returned an empty token string for submission %s, will not save submission" % submission_key)
        return
    submission.tokens = tokens
    submission.indexes_json = json_indexes

    # Compute checksum of submitted source code for finding exact character matches quickly
    submission_hash = hashlib.md5(submission_text.encode("utf-8"))
    submission.source_checksum = submission_hash.hexdigest()
    submission.save()

    # Compute similarity of submitted tokens to exercise template tokens
    template_comparison = matcher.match_against_template(submission)
    template_comparison.save()

    return submission.id


@celery.shared_task(ignore_result=True)
def reload_exercise_submissions(exercise_id, submissions_api_url):
    """
    Fetch the current submission list from the API url, clear existing submissions, create new submissions, and match all submissions.
    """
    exercise = Exercise.objects.get(pk=exercise_id)
    api_client = aplus.get_api_client(exercise.course)
    submissions_data = api_client.load_data(submissions_api_url)
    if submissions_data is None:
        # raise ProviderTaskError("Invalid submissions data returned from %s for exercise %s: expected an iterable but got None" % (submissions_api_url, exercise))
        write_error("Invalid submissions data returned from %s for exercise %s: expected an iterable but got None" % (submissions_api_url, exercise))
        return
    # We got new submissions data from the provider, delete all current submissions to this exercise
    exercise.submissions.all().delete()
    # Create a group of immutable task signatures for creating each submission from api data
    tasks_create_submissions = (
        create_submission.si(submission["id"], exercise.course.key, submission["url"]).on_error(task_error_handler.s())
        for submission in submissions_data
    )
    # Callback task that matches all submissions to the exercise we are reloading
    task_match_exercise = matcher_tasks.match_all_new_submissions_to_exercise.si(exercise_id)
    # Create all submissions in parallel in independent tasks, synchronize, and match all submissions sequentially in a single task
    celery.chord(tasks_create_submissions)(task_match_exercise)


@celery.shared_task
def task_error_handler(task_id, *args, **kwargs):
    write_error("Failed celery task {}".format(task_id))


def write_error(message):
    logger.error(message)
    TaskError(package="provider", error_string=message).save()
