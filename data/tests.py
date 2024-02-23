from django.test import TestCase
import random

from data.models import Course, Submission, Comparison, Student
from aplus_client.django.models import ApiNamespace


# Test for exercise view table generation
class TestExerciseTable(TestCase):
    def test_run_ex_table(self):
        site = ApiNamespace(600)
        site.save()

        course = Course(id=600, api_id=600, namespace_id=600)
        course.save()

        exercise = course.get_exercise("TestCourse")

        comparison_set = []

        for i in range(50):
            student_a = Student(key=i + 1000, course=course)
            student_b = Student(key=i + 2000, course=course)
            submission_a = Submission(
                key=i + 1000, exercise=exercise, student=student_a, matched=True
            )
            submission_b = Submission(
                key=i + 2000, exercise=exercise, student=student_b, matched=True
            )

            comparison = Comparison(
                submission_a=submission_a,
                submission_b=submission_b,
                similarity=random.random(),
            )

            comparison_set.append(comparison)

            student_a.save()
            student_b.save()
            submission_a.save()
            submission_b.save()
            comparison.save()

        sorted_comparison_set = sorted(
            set(comparison_set),
            key=lambda comparison: comparison.similarity,
            reverse=True,
        )

        self.assertQuerySetEqual(sorted_comparison_set, exercise.top_comparisons(100))
