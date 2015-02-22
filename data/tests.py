from django.conf import settings
from django.test import TestCase

from data.models import Course, Submission, Comparison, Exercise
from matcher.matcher import match
from radar.config import named_function


TOKENS1 = "abcdefghi"
TOKENS2 = "abcxxxxxxxxxfgxab"
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
        self.assertEqual(Comparison.objects.all().count(), 3)
        cts = Comparison.objects.filter(submission_b__isnull=True)
        self.assertEqual(len(cts), 2)
        self.assertAlmostEqual(cts[0].similarity, 0.0, 1)
        self.assertAlmostEqual(cts[1].similarity, 0.0, 1)
        self.assertEqual(cts[0].matches_json, "[]")
        c = Comparison.objects.exclude(submission_b__isnull=True).first()
        self.assertAlmostEqual(c.similarity, 5 / len(TOKENS1), 1)
        self.assertEqual(c.matches_json, "[[0,0,3],[12,5,2]]")
        
    def test_template(self):
        self._create_test_course()
        exercise = Exercise.objects.all().first()
        exercise.template_tokens = TEMPLATE
        exercise.save()
        for submission in Submission.objects.filter(max_similarity__isnull=True).order_by("student__key"):
            match(submission)
        self.assertEqual(Comparison.objects.all().count(), 3)
        cts = Comparison.objects.filter(submission_b__isnull=True).order_by("submission_a")
        self.assertEqual(len(cts), 2)
        print(cts[1].matches_json)
        self.assertAlmostEqual(cts[0].similarity, 5 / len(TOKENS1), 1)
        self.assertAlmostEqual(cts[1].similarity, 7 / len(TOKENS2), 1)
        self.assertEqual(cts[0].matches_json, "[[0,0,5]]")
        self.assertEqual(cts[1].matches_json, "[[0,0,3],[3,5,4]]")
        c = Comparison.objects.exclude(submission_b__isnull=True).first()
        self.assertAlmostEqual(c.similarity, 2 / (len(TOKENS1) - 5), 1)
        self.assertEqual(c.matches_json, "[[12,5,2]]")
        
    def _create_test_course(self):
        course = Course(key="test", name="Test", provider="filesystem", tokenizer="scala", minimum_match_tokens=2)
        course.save()
        exercise = course.get_exercise("1")
        student1 = course.get_student("001")
        student2 = course.get_student("002")
        s1 = Submission(exercise=exercise, student=student1, tokens=TOKENS1, indexes_json="[]")
        s1.save()
        s2 = Submission(exercise=exercise, student=student2, tokens=TOKENS2, indexes_json="[]")
        s2.save()
