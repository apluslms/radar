from django.core.management.base import BaseCommand

from data import files
from data.files import student_name
from data.models import Exercise, Submission, Student, URLKeyField


class Command(BaseCommand):
    args = "course/exercise <submission_dir submission_dir ...>"
    help = "Inserts submissions to system."

    def handle(self, *args, **options):
        
        if len(args) < 1:
            self.stdout.write("The course/exercise parameter is required.")
            return
        (course_name, exercise_name) = args[0].split("/", 1)
        exercise = Exercise.objects.get(course__name=course_name, name=exercise_name)
        self.stdout.write("Inserting to exercise %s." % (exercise))

        if len(args) < 2:
            self.stdout.write("At least one submission directory is required.")
            return
        for i in range(1, len(args)):
            path = args[i]
            text = files.join_files(files.read_directory(path), exercise.tokenizer)
            student_name = URLKeyField.safe_version(student_name(path))

            student = Student.objects.get_or_create(course=exercise.course, name=student_name)
            submission = Submission(exercise=exercise, student=student)
            submission.save()
            files.put_submission_text(submission, text)
