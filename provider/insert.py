import hashlib

from data.models import Submission
from tokenizer import tokenizer
from matcher import matcher
import radar.config as config_loaders


class InsertError(Exception):
    pass


def submission_exists(submission_key):
    return Submission.objects.filter(key=submission_key).exists()


def insert_submission(exercise, submission_key, submitter_id, data={}):
    student = exercise.course.get_student(str(submitter_id))
    return Submission.objects.create(
        key=submission_key,
        exercise=exercise,
        student=student,
        provider_url=data.get("html_url"),
        provider_submission_time=data.get("submission_time"),
        grade=data.get("grade", 0),
    )


def prepare_submission(submission, matching_start_time=''):

    if matching_start_time:
        # The exercise of this submission has been marked for matching, this submission is going directly to matching.
        submission.matching_start_time = matching_start_time

    provider_config = config_loaders.provider_config(submission.exercise.course.provider)
    get_submission_text = config_loaders.configured_function(
        provider_config,
        "get_submission_text"
    )
    submission_text = get_submission_text(submission, provider_config)
    if submission_text is None:
        submission.invalid = True
        submission.save()
        raise InsertError("Failed to get submission text for submission %s" % submission)

    tokens, json_indexes = tokenizer.tokenize_submission(
        submission,
        submission_text,
        provider_config
    )
    if not tokens:
        submission.invalid = True
        submission.save()
        raise InsertError("Tokenizer returned an empty token string for submission %s, will not save submission" % submission_key)
    submission.tokens = tokens
    submission.indexes_json = json_indexes

    # Compute checksum of submitted source code for finding exact character matches quickly
    # This line will not be reached if submission_text contains data not encodable in utf-8, since it is checked in tokenizer.tokenize_submission
    submission_hash = hashlib.md5(submission_text.encode("utf-8"))
    submission.source_checksum = submission_hash.hexdigest()
    submission.save()

    # Compute similarity of submitted tokens to exercise template tokens
    template_comparison = matcher.match_against_template(submission)
    template_comparison.save()
