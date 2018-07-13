import logging

from django.conf import settings
from django.db.models import Avg

from matchlib.util import TokenMatch

from data.models import Comparison
import radar.config as config_loaders


logger = logging.getLogger("radar.matcher")


def safe_div(a, b):
    return a / b if b > 0 else 0.0


def top_marks(length, top):
    return '1' * top + '0' * (length - top)


def update_submission(submission, similarity):
    submission.matched = True
    submission.invalid = False
    if submission.max_similarity < similarity:
        submission.max_similarity = similarity
    if submission.max_similarity > settings.AUTO_PAUSE_MEAN:
        subs = submission.exercise.valid_matched_submissions
        if subs.count() > settings.AUTO_PAUSE_COUNT:
            avg = subs.aggregate(max_sim=Avg("max_similarity"))
            if avg["max_sim"] > settings.AUTO_PAUSE_MEAN:
                submission.exercise.paused = True
                submission.exercise.save()
    submission.save()


def match_against_template(submission):
    """
    Match submission against the exercise template.
    """
    logger.info("Match %s vs template", submission.student.key)
    # Template comparisons are defined as Comparison objects where the other (b) submission is null
    comparison = Comparison(submission_a=submission, submission_b=None, similarity=0.0, matches_json="[]")

    submission_tokens, template_tokens = submission.tokens, submission.exercise.template_tokens

    # Calculate amount of submission tokens that match the beginning of the exercise template
    l = 0
    while (l < len(submission_tokens) and l < len(template_tokens)
           and submission_tokens[l] == template_tokens[l]):
        l += 1
    template_head_match_count = l

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
        submission.exercise.minimum_match_tokens
    )
    # Add the template head match
    if template_head_match_count > 0:
        matches.add_non_overlapping(TokenMatch(0, 0, template_head_match_count))

    comparison.similarity = safe_div(matches.token_count(), len(submission_tokens))
    comparison.matches_json = matches.json()

    return comparison
