import logging
logging.disable(logging.CRITICAL)

from django.conf import settings
from django.test import TestCase

from data.models import Course, Submission, Comparison, Exercise
from matcher.matcher import match
from radar.config import named_function


TOKENS1 = "abcdefghi" # total 9, authored 4, longest 4
TOKENS2 = "abcxxxxxxxxxfgxab" # total 17, authored 4, longest 4
TEMPLATE = "abcdexxxx"

class MatcherTestCase(TestCase):

    def test_algorithm(self):
        f = named_function(settings.MATCH_ALGORITHM)
        a = TOKENS1
        b = TOKENS2
        ms = f(a, [ False ] * len(a), b, [ False ] * len(b), 2)
        self.assertEqual(len(ms.store), 2)
        self.assertEqual(ms.store[0].a, 0)
        self.assertEqual(ms.store[0].b, 0)
        self.assertEqual(ms.store[0].length, 3)
        self.assertEqual(ms.store[1].a, 5)
        self.assertEqual(ms.store[1].b, 12)
        self.assertEqual(ms.store[1].length, 2)

    def test_submission(self):
        self._create_test_course()
        for submission in Submission.objects.filter(max_similarity__isnull=True).order_by("student__key"):
            match(submission)
        s = Submission.objects.get(student__key="001")
        self.assertEqual(s.authored_token_count, 9)
        self.assertEqual(s.longest_authored_tile, 9)
        s = Submission.objects.get(student__key="002")
        self.assertEqual(s.authored_token_count, 17)
        self.assertEqual(s.longest_authored_tile, 17)
        self.assertEqual(Comparison.objects.all().count(), 3)
        cts = Comparison.objects.filter(submission_b__isnull=True)
        self.assertEqual(len(cts), 2)
        self.assertAlmostEqual(cts[0].similarity, 0.0, 1)
        self.assertAlmostEqual(cts[1].similarity, 0.0, 1)
        self.assertEqual(cts[0].matches_json, "[]")
        c = Comparison.objects.exclude(submission_b__isnull=True).first()
        self.assertAlmostEqual(c.similarity, 9 / 26, 1)
        self.assertEqual(c.matches_json, "[[0,0,3],[12,5,2]]")

    def test_template(self):
        self._create_test_course()
        exercise = Exercise.objects.all().first()
        exercise.template_tokens = TEMPLATE
        exercise.save()
        for submission in Submission.objects.filter(max_similarity__isnull=True).order_by("student__key"):
            match(submission)
        s = Submission.objects.get(student__key="001")
        self.assertEqual(s.authored_token_count, 4)
        self.assertEqual(s.longest_authored_tile, 4)
        s = Submission.objects.get(student__key="002")
        self.assertEqual(s.authored_token_count, 10)
        self.assertEqual(s.longest_authored_tile, 10, "Submission with tokens {} should have longest authored tile {}".format(s.tokens, 10))
        self.assertEqual(Comparison.objects.all().count(), 3)
        cts = Comparison.objects.filter(submission_b__isnull=True).order_by("submission_a")
        self.assertEqual(len(cts), 2)
        self.assertAlmostEqual(cts[0].similarity, 5 / 9, 1)
        self.assertAlmostEqual(cts[1].similarity, 7 / 17, 1)
        self.assertEqual(cts[0].matches_json, "[[0,0,5]]")
        self.assertEqual(cts[1].matches_json, "[[0,0,3],[3,5,4]]")
        c = Comparison.objects.exclude(submission_b__isnull=True).first()
        self.assertAlmostEqual(c.similarity, 4 / 14, 1)
        self.assertEqual(c.matches_json, "[[12,5,2]]")

    def _create_test_course(self):
        course = Course(key="test", name="Test", provider="filesystem", tokenizer="scala", minimum_match_tokens=2, api_id="0", namespace_id="0")
        course.save()
        exercise = course.get_exercise("1")
        student1 = course.get_student("001")
        student2 = course.get_student("002")
        s1 = Submission(key="1", exercise=exercise, student=student1, tokens=TOKENS1, indexes_json="[]")
        s1.save()
        s2 = Submission(key="2", exercise=exercise, student=student2, tokens=TOKENS2, indexes_json="[]")
        s2.save()

