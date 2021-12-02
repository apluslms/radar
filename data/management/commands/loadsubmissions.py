from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
from django.conf import settings

from provider.filesystem import load_submission_dir
from data.models import Course


class MockApiObj:

    def __init__(self):
        self.id = 0
        self.url = 'http://localhost/mock_api'
    
    def __getitem__(self, k):
        if k == 'api_id':
            return self.id
        return None


class Command(BaseCommand):
    help = "Inserts submissions for an exercise."

    def add_arguments(self, parser):
        parser.add_argument('course/exercise', type=str)
        parser.add_argument('submission_path', nargs='+', type=str)

    def handle(self, *args, **options):
        (course_key, exercise_key) = options['course/exercise'].split("/", 1)
        try:
            course = Course.objects.get(key=course_key)
        except ObjectDoesNotExist:
            course = Course.objects.create(
                MockApiObj(),
                key=course_key,
                name=course_key.capitalize(),
                provider='filesystem',
                tokenizer='python',
                minimum_match_tokens=15,
                archived=False,
                similarity_graph_json=''
            )
        exercise = course.get_exercise(exercise_key)
        self.stdout.write("Inserting to exercise %s" % (exercise))

        for path in options['submission_path']:
            submission = load_submission_dir(exercise, path)
            if submission is not None:
                self.stdout.write("Saved submission %s" % (submission))
