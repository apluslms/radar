from django.conf import settings
from django.db import models
from celery import shared_task, chord
from celery.utils.log import get_task_logger

from matcher import matcher
from data.models import Submission, Comparison
import radar.config as config_loaders


logger = get_task_logger(__name__)


# NOTE: Must be synchronized
@shared_task(ignore_result=True)
def match_submission(submission_id):
    """
    Initialize all possible Comparison objects resulting from matching the given submission against all other submissions.
    This task should be used as a synchronization point to prevent data races that result from processing new submissions in parallel, which might leave some submission pairs without comparison.
    For example, use a dedicated worker to consume these tasks from a single queue.
    """
    submission = Submission.objects.get(pk=submission_id)
    pending_comparison_ids = []
    for other in submission.submissions_to_compare:
        comparison = Comparison(submission_a=submission, submission_b=other)
        comparison.save()
        pending_comparison_ids.append(comparison.id)
    # Compute all comparisons in parallel and invoke a callback to join all results when finished
    # Does not block this task
    chord(map(do_comparison.s, pending_comparison_ids))(join_comparison_results.s())


@shared_task
def do_comparison(comparison_id):
    """
    Compute similarity for an initialized but yet unfinished Comparison, consisting of two submissions a and b.
    """
    comparison = Comparison.objects.get(pk=comparison_id)
    logger.debug("Computing similarity for Comparison %s", comparison)

    # Import callable similarity function from string
    function_data = settings.MATCH_ALGORITHMS[comparison.similarity_function]
    similarity_function = config_loaders.named_function(function_data["callable"])

    # Compute similarity

    similarity = 0.0
    matches = TokenMatchSet()
    a, b = comparison.submission_a, comparison.submission_b

    marks_a, count_a, longest_a = a.template_marks()
    marks_b, count_b, longest_b = b.template_marks()
    # TODO why are these 3 lines here?
    a.authored_token_count = count_a
    a.longest_authored_tile = longest_a
    a.save()
    if longest_a < a.exercise.minimum_match_tokens and longest_b < a.exercise.minimum_match_tokens:
        # TODO why do we skip when longest_? is less than min match tokens?
        return comparison_id

    # Special cases, functions that do not take the tokenized string as input
    if function_data["tokenized_input"] is False:
        if comparison.similarity_function == "md5sum" and a.source_checksum == b.source_checksum:
            # Matching checksums implies a match consisting of all tokens
            similarity = function_data["weight"]
            matches.add_non_overlapping(TokenMatch(0, 0, len(a.tokens)))
    # Else, the function accepts tokenized input
    else:
        matches = similarity_function(a.tokens, marks_a, b.tokens, marks_b, a.exercise.minimum_match_tokens)
        w = function_data["weight"]
        s = safe_div(matches.token_count(), (count_a + count_b) / 2)
        similarity = w * s

    if similarity > settings.MATCH_STORE_MIN_SIMILARITY:
        comparison.similarity = similarity
        comparison.matches_json = matches.json()
        comparison.save()

    logger.debug("Comparison %s done", comparison)
    return comparison_id


@shared_task(ignore_result=True)
def join_comparison_results(comparison_ids):
    """
    For a list of ids for Comparison instances of one Submission instance, compute maximum similarity and update the Submission.
    """
    if not comparison_ids:
        return
    comparisons = Comparison.objects.filter(pk__in=comparison_ids)
    new_max_similarity = comparisons.aggregate(models.Max("similarity")).get("similarity__max")
    if new_max_similarity is None:
        new_max_similarity = 0

    # It is reasonable to assume all comparisons being joined are for one submission
    submission = comparisons.first().submission_a

    # Set new similarity
    if submission.max_similarity is None or submission.max_similarity < new_max_similarity:
        submission.max_similarity = new_max_similarity
    # Automatically pause exercise if the arithmetic mean of similarities gets too high.
    if submission.max_similarity > settings.AUTO_PAUSE_MEAN:
        submissions = submission.exercise.matched_submissions
        if submissions.count() > settings.AUTO_PAUSE_COUNT:
            avg_max_similarity = submissions.aggregate(m=models.Avg("max_similarity")).get("m")
            if avg_max_similarity > settings.AUTO_PAUSE_MEAN:
                submission.exercise.paused = True
                submission.exercise.save()


@shared_task(ignore_result=True)
def match_all_missing_comparisons(submission_id):
    """
    Ensure a submission has been compared against all other submissions of the same exercise and create missing comparisons if there are any.
    """
    # TODO implement
    submission = Submission.objects.get(pk=submission_id)
    all_submissions = Submission.objects.filter(exercise=submission.exercise)

