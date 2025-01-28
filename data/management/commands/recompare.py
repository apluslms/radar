from django.core.management.base import BaseCommand

from provider.filesystem import recompare
from data.models import Course


class Command(BaseCommand):
    help = (
        "Calculate similarity for all submissions in the exercise."
    )

    def add_arguments(self, parser):
        parser.add_argument('course/exercise', type=str)

    def handle(self, *args, **options):
        (course_key, exercise_key) = options['course/exercise'].split("/", 1)
        course = Course.objects.get(key=course_key)
        exercise = course.get_exercise(exercise_key)

        recompare(exercise, {})
