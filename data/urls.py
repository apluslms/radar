from django.conf.urls import patterns, url


urlpatterns = patterns('data.views',

    url(r'^(?P<course_name>\w+)/hook-submission$', 'hook_submission'),
)
