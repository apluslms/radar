import logging

from django.core.management.base import BaseCommand

from data.models import Course, Submission
from matcher.matcher import match
from radar.config import provider, configured_function, tokenizer


logger = logging.getLogger("radar.cron")

class Command(BaseCommand):
    args = ""
    help = "Cron work for new submissions: provide, tokenize, match"

    def handle(self, *args, **options):

        # TODO ensure never parallel, file lock

        for course in Course.objects.filter(archived=False):
            logger.info("Cron tasks for course %s", course)

            # Run provider tasks.
            p_config = provider(course)
            f = configured_function(p_config, "cron")
            f(course, p_config)

            # Tokenize new submissions.
            for submission in Submission.objects.filter(exercise__course=course, tokens=None):
                t_config = tokenizer(submission.exercise)
                f = configured_function(t_config, "cron")
                f(submission, t_config)

                # While at it match it too.
                match(submission)

            # Check again for yet unmatched submissions.
            for submission in Submission.objects.filter(exercise__course=Course, matching_finished=False):
                match(submission)
