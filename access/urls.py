from django.conf.urls import patterns, url

urlpatterns = patterns('access.views',

    url(r'^$', 'index', name='index'),
    url(r'^(?P<course_name>\w+)/$', 'course'),
    url(r'^(?P<course_name>\w+)/student/(?P<student_name>\w+)/$', 'student'),
    url(r'^(?P<course_name>\w+)/student/(?P<student_name>\w+)/(?P<submission_id>\d+)/$', 'submission'),
    url(r'^(?P<course_name>\w+)/(?P<exercise_name>\w+)/$', 'exercise'),
    url(r'^(?P<course_name>\w+)/(?P<exercise_name>\w+)/(?P<group_id>\d+)/$', 'group'),
    url(r'^(?P<course_name>\w+)/hook-submission$', 'hook_submission'),
)
