from django.conf.urls import patterns, url


urlpatterns = patterns('data.views',

    url(r'^(?P<course_key>\w+)/hook-submission$', 'hook_submission'),
)
