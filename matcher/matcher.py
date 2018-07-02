import json
import logging

from django.conf import settings
from django.db.models import Avg

from data.models import Comparison, Submission, Exercise
import radar.config as config_loaders
import gc


logger = logging.getLogger("radar.matcher")


def safe_div(a, b):
    return a / b if b > 0 else 0.0


def top_marks(length, top):
    for _ in range(top):
        yield True
    for _ in range(top, length):
        yield False


def match_against_template(submission):
    """
    Match submission against template with all similarity functions.
    """
    logger.debug("Match %s vs template", submission.student.key)
    # Comparisons with single submissions are template comparisons
    comparison = Comparison(submission_a=submission, submission_b=None, similarity=0.0, matches_json="[]")
    comparison.save()

    # TODO: what is this? template offset? could this be removed?
    l = 0
    while (l < len(submission.tokens)
           and l < len(submission.exercise.template_tokens)
           and submission.tokens[l] == submission.exercise.template_tokens[l]):
        l += 1

    for function_name, function_data in settings.MATCH_ALGORITHMS.items():
        if not function_data["tokenized_input"]:
            # Templates consist only of tokenized strings
            continue
        similarity_function = config_loaders.named_function(function_data["callable"])
        matches = similarity_function(
            submission.tokens,
            top_marks(len(submission.tokens), l),
            submission.exercise.template_tokens,
            top_marks(len(submission.exercise.template_tokens), l),
            submission.exercise.minimum_match_tokens
        )
        if l > 0:
            matches.add_non_overlapping(TokenMatch(0, 0, l))
        w = function_data["weight"]
        s = safe_div(matches.token_count(), len(submission.tokens))
        similarity = w * s
        if similarity > comparison.similarity:
            comparison.similarity = similarity
            comparison.matches_json = matches.json()

    comparison.save()


class TokenMatchSet():

    def __init__(self):
        self.store = []

    def extend(self, match_set):
        self.store.extend(match_set.store)

    def add(self, match):
        self.store.append(match)

    def add_non_overlapping(self, match):
        for m in self.store:
            if match.overlaps(m):
                return False
        self.store.append(match)
        return True

    def clear(self):
        del self.store[:]

    def all(self):
        return self.store

    def reverse(self):
        r = TokenMatchSet()
        r.store.extend(map(lambda m: m.reverse(), self.store))
        return r

    def match_count(self):
        return len(self.store)

    def token_count(self):
        return sum(map(lambda m: m.length, self.store))

    def json(self):
        return json.dumps(
            list(map(lambda m: [m.a, m.b, m.length], sorted(self.store, key=lambda m: m.a))),
            separators=(",", ":"))


class TokenMatch():

    def __init__(self, a, b, length):
        self.a = a
        self.b = b
        self.length = length

    def overlaps(self, another):
        return (self.a > another.a - self.length and self.a < another.a + self.length) \
            or (self.b > another.b - self.length and self.b < another.b + self.length)

    def reverse(self):
        return TokenMatch(self.b, self.a, self.length)


def match(a):
    """
    Match given submission against all other, already matched submissions for this exercise.
    """
    logger.info("Matching submission %s", a)
    if Submission.objects.get(pk=a.pk).tokens is None:
        logger.info("Submission is not tokenized.")
        return

    match_against_template(a)

    # TODO what are these
    _, a.authored_token_count, a.longest_authored_tile = a.template_marks()
    a.save()

    # TODO parallel for
    for b in a.submissions_to_compare:
        for similarity_function in settings.MATCH_ALGORITHMS:
            comparison = do_comparison(Comparison(
                submission_a=a, submission_b=b,
                similarity=0.0, similarity_function=similarity_function))
            comparison.save()

    # TODO what is this
    tail = (Comparison.objects
            .filter(submission_a=a)
            .exclude(submission_b__isnull=True)
            .order_by("-similarity")[settings.MATCH_STORE_MAX_COUNT:]
            .values_list("id", flat=True))
    Comparison.objects.filter(pk__in=list(tail)).delete()

    a.matched = True
    a.invalid = False
    a.save()

    # Automatically pause exercise if mean gets too high.
    if a.max_similarity > settings.AUTO_PAUSE_MEAN:
        subs = a.exercise.valid_matched_submissions
        if subs.count() > settings.AUTO_PAUSE_COUNT:
            avg = subs.aggregate(max_sim=Avg("max_similarity"))
            if avg["max_sim"] > settings.AUTO_PAUSE_MEAN:
                a.exercise.paused = True
                a.exercise.save()


def do_comparison(comparison):
    """
    Compute similarity of two submissions a and b.
    Does not commit changes to the database.
    """
    a, b = comparison.submission_a, comparison.submission_b

    marks_a, count_a, longest_a = a.template_marks()
    marks_b, count_b, longest_b = b.template_marks()
    if longest_a < a.exercise.minimum_match_tokens and longest_b < a.exercise.minimum_match_tokens:
        # TODO why do we skip when longest_? is less than min match tokens?
        return comparison

    # Load similarity function settings
    function_data = settings.MATCH_ALGORITHMS[comparison.similarity_function]

    # Compute similarity
    similarity = 0.0
    matches = TokenMatchSet()
    # Regular functions that accept tokenized input
    if function_data["tokenized_input"] is True:
        # Load callable similarity function
        similarity_function = config_loaders.named_function(function_data["callable"])
        # Match tokens of submissions a and b
        matches = similarity_function(a.tokens, marks_a, b.tokens, marks_b, a.exercise.minimum_match_tokens)
        # Apply weight to similarity
        w = function_data["weight"]
        s = safe_div(matches.token_count(), (count_a + count_b) / 2)
        similarity = w * s
    # Special cases, functions that do not take the tokenized string as input
    else:
        if comparison.similarity_function == "md5sum" and a.source_checksum == b.source_checksum:
            # Matching checksums implies a match consisting of all tokens
            similarity = function_data["weight"]
            matches.add_non_overlapping(TokenMatch(0, 0, len(a.tokens)))

    if similarity > settings.MATCH_STORE_MIN_SIMILARITY:
        comparison.similarity = similarity
        comparison.matches_json = matches.json()

    return comparison
