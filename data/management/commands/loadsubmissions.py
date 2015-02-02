from django.core.management.base import BaseCommand

from integration.filesystem import load_submission_dir
from data.models import Course, Exercise, URLKeyField


class Command(BaseCommand):
    args = "course/exercise <submission_dir submission_dir ...>"
    help = "Inserts submissions to system."

    def handle(self, *args, **options):
        
        if len(args) < 1:
            self.stdout.write("The course/exercise parameter is required.")
            return
        (course_name, exercise_name) = args[0].split("/", 1)
        course = Course.objects.get(name=course_name)
        exercise = course.get_exercise(exercise_name)
        self.stdout.write("Inserting to exercise %s" % (exercise))

        if len(args) < 2:
            self.stdout.write("At least one submission directory is required.")
            return
        for i in range(1, len(args)):
            submission = load_submission_dir(exercise, args[i])
            self.stdout.write("Saved submission %s" % (submission))
