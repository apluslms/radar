from django.test import TestCase
from data.models import Student, Course, Submission
from matcher import tasks
from aplus_client.django.models import ApiNamespace

TOKENS1 = "ABCD, Testing"
TOKENS2 = "123123 Test"


# Test for matcher calls
class TestMatcher(TestCase):

    # Test matcher to see that submissions are matched and comparison objects are created
    def test_run_match_exercise(self):
        site = ApiNamespace(600)
        site.save()

        course = Course(id=600, api_id=600, namespace_id=600)
        course.save()

        exercise = course.get_exercise("TestCourse")

        student_a = Student(key=3000, course=course)
        student_b = Student(key=4000, course=course)
        submission_a = Submission(key=3000, exercise=exercise, student=student_a, matched=False, tokens=TOKENS1)
        submission_b = Submission(key=4000, exercise=exercise, student=student_b, matched=False, tokens=TOKENS2)

        student_a.save()
        student_b.save()
        submission_a.save()
        submission_b.save()

        exercise.touch_all_timestamps()

        tasks.match_exercise(exercise.pk, delay=False)

        self.assertTrue(submission_a in exercise.valid_matched_submissions)
        self.assertTrue(submission_b in exercise.valid_matched_submissions)

# TODO: Create more tests here
