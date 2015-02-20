import logging

from django.conf import settings

from data.models import Submission, Match
from radar.config import named_function


logger = logging.getLogger("radar.matcher")


def match(a):
    """
    Matches the submission A against already matched submissions for this exercise.
    
    """
    logger.info("Matching submission %s", a)
    f = named_function(settings.MATCH_ALGORITHM)
    for b in Submission.objects.filter(exercise=a.exercise, matching_finished=True).exclude(student=a.student):
        logger.debug("Match %s and %s", a.student.name, b.student.name)
        for m in f(a.tokens, b.tokens, a.exercise.minimum_match_tokens):
            #TODO add pairwise matches
            Match.objects.record(a, b, m)
    
    a.matching_finished = True
    a.save()


class TokenMatch():

    def __init__(self, a, b, length):
        self.a = a
        self.b = b
        self.length = length

    @property
    def a_end(self):
        return self.a + self.length - 1

    @property
    def b_end(self):
        return self.b + self.length - 1

    def overlaps(self, another):
        return (self.a >= another.a - self.length and self.a < another.a + self.length) \
            or (self.b > another.b - self.length and self.b < another.b + self.length)

    def reverse(self):
        return TokenMatch(self.b, self.a, self.length)
    
    def sub(self, start, end):
        if start < 0 and start >= self.length and not start < end:
            raise ValueError("Not subsection indexes")
        return TokenMatch(self.a + start, self.b + start, min(self.length, end - start))


class TokenMatchSet():

    def __init__(self):
        self.store = []

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
