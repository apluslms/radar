import logging
import time

from django.core.management.base import BaseCommand

from matcher.tasks import match_exercise
from data.models import Course


class Command(BaseCommand):
    help = "Calculates remaining matches for an exercise."

    def add_arguments(self, parser):
        parser.add_argument('course/exercise', type=str)

    def handle(self, *args, **options):
        (course_key, exercise_key) = options['course/exercise'].split("/", 1)
        course = Course.objects.get(key=course_key)
        exercise = course.get_exercise(exercise_key)
        
        self.stdout.write("Matching for exercise %s" % (exercise))
        match_exercise(exercise.pk, False)
