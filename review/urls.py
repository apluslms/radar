from django.conf.urls import patterns, url


urlpatterns = patterns('review.views',

    url(r'^$', 'index', name='index'),
    url(r'^(?P<course_name>\w+)/$', 'course'),
    url(r'^(?P<course_name>\w+)/(?P<exercise_name>\w+)/$', 'exercise'),
    url(r'^(?P<course_name>\w+)/(?P<exercise_name>\w+)/(?P<g_id>\d+)/$', 'group'),
    url(r'^(?P<course_name>\w+)/(?P<exercise_name>\w+)/(?P<g_id>\d+)/(?P<a_name>\w+)-vs-(?P<b_name>\w+)/$', 'comparison'),
)
