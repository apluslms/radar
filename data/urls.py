from django.conf.urls import url

from data.views import hook_submission


urlpatterns = [
    url(r'^(?P<course_key>\w+)/hook-submission$', hook_submission, name='hook_submission'),
]
