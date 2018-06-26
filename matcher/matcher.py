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


# Legacy sequential monster
# def match(a):
#     """
#     Matches the submission A against already matched submissions for this exercise.

#     """
#     logger.info("Matching submission %s", a)
#     if Submission.objects.get(pk=a.pk).tokens == None:
#         logger.info("Submission is not tokenized.")
#         return False

#     # Clear existing comparisons for given submission
#     Comparison.objects.filter(submission_a=a).delete()

#     # Import all similarity functions
#     similarity_functions = [
#         {
#             "callable": config_loaders.named_function(f.function),
#             "db_object": f
#         } for f in a.exercise.course.similarityfunction_set.all()
#     ]

#     # Match submission 'a' against template with all algorithms
#     template_comparison = Comparison(submission_a=a, submission_b=None)
#     template_comparison.save()

#     # template offset? TODO: could this be avoided?
#     l = 0
#     while l < len(a.tokens) and l < len(a.exercise.template_tokens) and a.tokens[l] == a.exercise.template_tokens[l]:
#         l += 1

#     for function_data in similarity_functions:
#         similarity_function = function_data["db_object"]
#         if not similarity_function.tokenized_input:
#             continue
#         # Match against template.
#         logger.debug("Match %s vs template, with function %s", a.student.key, similarity_function.name)
#         ms = function_data["callable"](a.tokens, top_marks(len(a.tokens), l),
#                a.exercise.template_tokens, top_marks(len(a.exercise.template_tokens), l),
#                a.exercise.minimum_match_tokens)
#         if l > 0:
#             ms.add_non_overlapping(TokenMatch(0, 0, l))
#         if template_comparison.matches_json is None:
#             # Set the match indexes for match visualization
#             template_comparison.matches_json = ms.json()
#             template_comparison.save()
#         similarity = similarity_function.weight * safe_div(ms.token_count(), len(a.tokens))
#         ComparisonResult(similarity=similarity, function=similarity_function, comparison=template_comparison).save()

#     template_comparison.similarity = template_comparison.max_similarity
#     template_comparison.save()

#     # Now, match submission 'a' against all previously matched submissions 'b' of the same exercise.

#     marks_a, count_a, longest_a = a.template_marks()
#     if longest_a >= a.exercise.minimum_match_tokens:
#         for b in a.submissions_to_compare:
#             # Force garbage collection.
#             gc.collect() # is this necessary for correctness or just an optimization attempt?
#             logger.debug("Match %s and %s", a.student.key, b.student.key)
#             marks_b, count_b, longest_b = b.template_marks()
#             if longest_b >= a.exercise.minimum_match_tokens:
#                 # Compute similarity for submission a and b with all similarity functions that accept the tokenized string
#                 ab_comparison = Comparison(submission_a=a, submission_b=b)
#                 results = []

#                 for function_data in similarity_functions:
#                     similarity_function = function_data["db_object"]
#                     if not similarity_function.tokenized_input:
#                         if similarity_function.name == "md5sum":
#                             if a.source_checksum == b.source_checksum:
#                                 similarity = similarity_function.weight
#                                 comparison_result = ComparisonResult(similarity=similarity, function=similarity_function)
#                                 if similarity > settings.MATCH_STORE_MIN_SIMILARITY:
#                                     ms = TokenMatchSet()
#                                     # Matching checksums implies a match consisting of all tokens
#                                     ms.add_non_overlapping(TokenMatch(0, 0, len(a.tokens)))
#                                     results.append({"similarity": similarity, "match_set": ms})
#                                     ab_comparison.save()
#                                     comparison_result.comparison = ab_comparison
#                                     comparison_result.save()
#                     else:
#                         ms = function_data["callable"](a.tokens, marks_a, b.tokens, marks_b, a.exercise.minimum_match_tokens)
#                         similarity = similarity_function.weight * safe_div(ms.token_count(), (count_a + count_b) / 2)
#                         comparison_result = ComparisonResult(similarity=similarity, function=similarity_function)
#                         # Commit comparison result to database only if the specified similarity threshold is exceeded
#                         if similarity > settings.MATCH_STORE_MIN_SIMILARITY:
#                             results.append({"similarity": similarity, "match_set": ms})
#                             ab_comparison.save()
#                             comparison_result.comparison = ab_comparison
#                             comparison_result.save()

#                 # If at least one of the comparisons yielded a similarity result above the min similarity threshold, store the result with maximum similarity
#                 if results:
#                     max_result = max(results, key=lambda r: r["similarity"])
#                     ab_comparison.similarity = max_result["similarity"]
#                     ab_comparison.matches_json = max_result["match_set"].json()
#                     ab_comparison.save()

#         tail = (Comparison.objects
#                 .filter(submission_a=a)
#                 .exclude(submission_b__isnull=True)
#                 .order_by("-similarity")[settings.MATCH_STORE_MAX_COUNT:]
#                 .values_list("id", flat=True))
#         Comparison.objects.filter(pk__in=list(tail)).delete()

#     new_max_similarity = a.max_similarity_from_comparisons()

#     if a.max_similarity is None or a.max_similarity < new_max_similarity:
#         a.max_similarity = new_max_similarity

#     a.authored_token_count = count_a
#     a.longest_authored_tile = longest_a
#     a.save()

#     # Automatically pause exercise if mean gets too high.
#     if a.max_similarity > settings.AUTO_PAUSE_MEAN:
#         subs = a.exercise.matched_submissions
#         if subs.count() > settings.AUTO_PAUSE_COUNT:
#             avg = subs.aggregate(m=Avg("max_similarity"))
#             if avg["m"] > settings.AUTO_PAUSE_MEAN:
#                 a.exercise.paused = True
#                 a.exercise.save()
#                 return False

#     return True
