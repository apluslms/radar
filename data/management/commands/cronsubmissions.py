from django.core.management.base import BaseCommand
from radar.config import provider, named_function
from data.models import Course


class Command(BaseCommand):
    args = ""
    help = "Cron work for new submissions: provide, tokenize, match"

    def handle(self, *args, **options):
        for course in Course.objects.filter(archived=False):
            
            # TODO ensure never parallel, file lock
            
            # Provider tasks.
            config = provider(course)
            f = named_function(config, "cron")
            f(course, config)
            
            # TODO run tokenize
            
            # TODO run match
