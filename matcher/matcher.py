import logging

from django.conf import settings

from matchlib.util import TokenMatch

from data.models import Comparison
import radar.config as config_loaders


logger = logging.getLogger("radar.matcher")


def safe_div(a, b):
    return a / b if b > 0 else 0.0


def top_marks(length, top):
    return '1' * top + '0' * (length - top)


def update_submission(submission_a, similarity, submission_b):
    """
    After matching a submission, update all flags and set new max similarity if the resulting similarity is highest
     so far.
    """
    submission_a.matched = True
    submission_a.matching_start_time = None
    submission_a.invalid = False
    if submission_a.max_similarity < similarity:
        submission_a.max_similarity = similarity
        submission_a.max_with = submission_b
    submission_a.save()

    # We don't need auto pause anymore because all matching tasks are started manually
    # if submission.max_similarity > settings.AUTO_PAUSE_MEAN:
    #     subs = submission.exercise.valid_matched_submissions
    #     if subs.count() > settings.AUTO_PAUSE_COUNT:
    #         avg = subs.aggregate(max_sim=Avg("max_similarity"))
    #         if avg["max_sim"] > settings.AUTO_PAUSE_MEAN:
    #             submission.exercise.paused = True
    #             submission.exercise.save()


def match_against_template(submission):
    """
    Match submission against the exercise template.
    """
    logger.debug("Match %s vs template", submission.student.key)
    # Template comparisons are defined as Comparison objects where the other (b) submission is null
    comparison = Comparison(
        submission_a=submission, submission_b=None, similarity=0.0, matches_json="[]"
    )

    submission_tokens, template_tokens = (
        submission.tokens,
        submission.exercise.template_tokens,
    )

    # Calculate amount of submission tokens that match the beginning of the exercise template
    iterator = 0
    while (
        iterator < len(submission_tokens)
        and iterator < len(template_tokens)
        and submission_tokens[iterator] == template_tokens[iterator]
    ):
        iterator += 1
    template_head_match_count = iterator

    # Skip matching for the template head, we already checked the matches
    submission_marks = top_marks(len(submission_tokens), template_head_match_count)
    template_marks = top_marks(len(template_tokens), template_head_match_count)

    # Import similarity function and do comparison
    similarity_function = config_loaders.named_function(settings.MATCH_ALGORITHM)
    matches = similarity_function(
        submission_tokens,
        submission_marks,
        template_tokens,
        template_marks,
        submission.exercise.minimum_match_tokens,
    )
    # Add the template head match
    if template_head_match_count > 0:
        matches.add_non_overlapping(TokenMatch(0, 0, template_head_match_count))

    comparison.similarity = safe_div(matches.token_count(), len(submission_tokens))
    comparison.matches_json = matches.json()

    return comparison
