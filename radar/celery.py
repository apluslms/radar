import os
import celery

from data.models import TaskError


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'radar.settings')

app = celery.Celery('radar')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print('Request: {0!r}'.format(self.request))


@app.task()
def task_error_handler(request, exc, traceback):
    TaskError(error_string=str(exc), full_traceback=traceback).save()
