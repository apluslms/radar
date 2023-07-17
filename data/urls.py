from django.urls import re_path

from data.views import hook_submission


urlpatterns = [
    re_path(r'^(?P<course_key>\w+)/hook-submission$', hook_submission, name='hook_submission'),
]
