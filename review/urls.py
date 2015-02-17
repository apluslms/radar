from django.conf.urls import patterns, url


urlpatterns = patterns('review.views',

    url(r'^$', 'index', name='index'),
    url(r'^(?P<course_name>\w+)/$', 'course'),
    url(r'^(?P<course_name>\w+)/(?P<exercise_name>\w+)/$', 'exercise'),
    url(r'^(?P<course_name>\w+)/(?P<exercise_name>\w+)/setup$', 'exercise_setup'),
    url(r'^(?P<course_name>\w+)/(?P<exercise_name>\w+)/(?P<g_id>\d+)/$', 'group'),
    url(r'^(?P<course_name>\w+)/(?P<exercise_name>\w+)/(?P<g_id>\d+)/(?P<a_id>\w+)$', 'submission'),
    url(r'^(?P<course_name>\w+)/(?P<exercise_name>\w+)/(?P<g_id>\d+)/(?P<a_id>\w+)/(?P<b_id>\w+)/$', 'comparison'),
)
