import hashlib

from celery import shared_task
from celery.utils.log import get_task_logger

import radar.config as config_loaders
from matcher import matcher
from provider import aplus
from data.models import Course, Submission, Exercise
from tokenizer import tokenizer

logger = get_task_logger(__name__)


class ProviderTaskError(Exception):
    pass


@shared_task(ignore_result=True)
def create_submission(submission_key, course_key, submission_api_url):
    """
    Fetch submission data for a new submission with provider key submission_key from a given API url, save submission and tokenize submission content.
    """
    course = Course.objects.get(key=course_key)
    logger.info("Processing submission with key %s for %s", submission_key, course)
    if Submission.objects.filter(key=submission_key).exists():
        raise ProviderTaskError("Submission with key %s already exists, will not create a duplicate." % submission_key)

    # We need someone with a token to the A+ API.
    api_client = aplus.get_api_client(course)
    logger.debug("Fetching submission data from %s", submission_api_url)
    data = api_client.load_data(submission_api_url)
    exercise_data = data["exercise"]
    exercise_name = exercise_data["display_name"]

    # Check if exercise is configured for Radar, if not, skip to next.
    radar_config = aplus.get_radar_config(exercise_data)
    if radar_config is None:
        logger.info("Exercise '%s' has no Radar configuration, submission ignored.", exercise_name)
        return
    logger.debug("Exercise '%s' has a Radar configuration with tokenizer '%s', proceeding to create a submission.", exercise_name, radar_config["tokenizer"])

    # Get or create exercise configuration
    exercise = course.get_exercise(str(exercise_data["id"]))
    if exercise.name == "unknown":
        logger.debug("Exercise '%s' with key %d does not yet exist in Radar, creating a new entry.", exercise_name, exercise_data["id"])
        exercise.set_from_config(radar_config)
        exercise.save()

    logger.debug("Creating a submission for exercise '%s'.", exercise_name)
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

    logger.debug("Retrieving contents of submission %s", submission_key)
    provider_config = config_loaders.provider_config(course.provider)
    get_submission_text = config_loaders.configured_function(
        provider_config,
        "get_submission_text"
    )
    submission_text = get_submission_text(submission, provider_config)
    if submission_text is None:
        raise ProviderTaskError("Failed to get submission text for submission %s", submission)

    logger.debug("Tokenizing contents of submission %s", submission_key)
    tokenizer.tokenize_submission(
        submission,
        submission_text,
        provider_config
    )
    logger.debug("Compute checksum of submission source %s", submission_key)
    submission_hash = hashlib.md5(submission_text.encode("utf-8"))
    submission.source_checksum = submission_hash.hexdigest()
    submission.save()

    logger.debug("Successfully processed submission with key %s for %s", submission_key, course)


@shared_task(ignore_result=True)
def reload_exercise_submissions(exercise_key, submissions_api_url):
    """
    Fetch the current submission list from the API url, clear existing submissions, and queue newly fetched submissions for work.
    """
    exercise = Exercise.objects.get(key=exercise_key)
    api_client = aplus.get_api_client(exercise.course)
    submissions_data = api_client.load_data(submissions_api_url)
    if submissions_data is None:
        raise ProviderTaskError("Invalid submissions data returned from %s for exercise %s: expected an iterable but got None" % (submissions_api_url, exercise))
    exercise.submissions.all().delete()
    for submission in submissions_data:
        if not Submission.objects.filter(key=submission["id"]).exists():
            create_submission.delay(
                submission["id"],
                exercise.course.key,
                submission["url"]
            )
        else:
            logger.error("Got a duplicate submission with key %s from %s", submission["id"], submissions_api_url)


@shared_task(ignore_result=True)
def match_all_unmatched_submissions(course_key=None):
    courses = []
    if course_key is None:
        courses = Course.objects.filter(archived=False)
    elif not Course.objects.filter(key=course_key).exists():
        raise ProviderTaskError("Cannot match submissions for course that does not exist, key was %s" % course_key)
    else:
        courses.append(Course.objects.get(key=course_key))
    for course in courses:
        submissions = Submission.objects.filter(
            exercise__course=course,
            exercise__paused=False,
            max_similarity__isnull=True
        )
        for submission in submissions:
            matcher.match(submission)

