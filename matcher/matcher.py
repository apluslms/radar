import json
import logging

from django.conf import settings
from django.db.models import Avg

from data.models import Comparison, Submission, Exercise
from radar.config import named_function
import gc


logger = logging.getLogger("radar.matcher")


def match(a):
    """
    Matches the submission A against already matched submissions for this exercise.

    """
    logger.info("Matching submission %s", a)
    if Submission.objects.get(pk=a.pk).tokens == None:
        logger.info("Submission is not tokenized.")
        return False

    def safe_div(a, b):
        return a / b if b > 0 else 0.0

    def top_marks(length, top):
        marks = [ False ] * length
        for i in range(0, top):
            marks[i] = True
        return marks

    f = named_function(settings.MATCH_ALGORITHM)

    # Clear any unfinished business.
    Comparison.objects.filter(submission_a=a).delete()

    # Match against template.
    logger.debug("Match %s vs template", a.student.key)
    l = 0
    while l < len(a.tokens) and l < len(a.exercise.template_tokens) and a.tokens[l] == a.exercise.template_tokens[l]:
        l += 1
    ms = f(a.tokens, top_marks(len(a.tokens), l),
           a.exercise.template_tokens, top_marks(len(a.exercise.template_tokens), l),
           a.exercise.minimum_match_tokens)
    if l > 0:
        ms.add_non_overlapping(TokenMatch(0, 0, l))
    c = Comparison(submission_a=a, submission_b=None,
                   similarity=safe_div(ms.token_count(), len(a.tokens)),
                   matches_json=ms.json())
    c.save()
    del c
    del ms

    # Match against previously matched submissions.
    marks_a, count_a, longest_a = a.template_marks()
    if longest_a >= a.exercise.minimum_match_tokens:
        for b in a.submissions_to_compare:

            # Force garbage collection.
            gc.collect()

            logger.debug("Match %s and %s", a.student.key, b.student.key)
            marks_b, count_b, longest_b = b.template_marks()
            if longest_b >= a.exercise.minimum_match_tokens:
                ms = f(a.tokens, marks_a, b.tokens, marks_b, a.exercise.minimum_match_tokens)
                s = safe_div(ms.token_count(), (count_a + count_b) / 2)
                if s > settings.MATCH_STORE_MIN_SIMILARITY:
                    c = Comparison(submission_a=a, submission_b=b, similarity=s, matches_json=ms.json())
                    c.save()
                if s > b.max_similarity:
                    b.max_similarity = s
                    b.save()
                if a.max_similarity is None or s > a.max_similarity:
                    a.max_similarity = s
                    a.save()

        tail = Comparison.objects.filter(submission_a=a).exclude(submission_b__isnull=True)\
            .order_by("-similarity")[settings.MATCH_STORE_MAX_COUNT:].values_list("id", flat=True)
        Comparison.objects.filter(pk__in=list(tail)).delete()

    if a.max_similarity is None:
        a.max_similarity = 0.0
    a.authored_token_count = count_a
    a.longest_authored_tile = longest_a
    a.save()

    # Automatically pause exercise if mean gets too high.
    if a.max_similarity > settings.AUTO_PAUSE_MEAN:
        subs = a.exercise.matched_submissions
        if subs.count() > settings.AUTO_PAUSE_COUNT:
            avg = subs.aggregate(m=Avg("max_similarity"))
            if avg["m"] > settings.AUTO_PAUSE_MEAN:
                a.exercise.paused = True
                a.exercise.save()
                return False

    return True

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
