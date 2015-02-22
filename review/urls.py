from django.conf.urls import patterns, url


urlpatterns = patterns('review.views',

    url(r'^$', 'index', name='index'),
    url(r'^(?P<course_key>\w+)/$', 'course'),
    url(r'^(?P<course_key>\w+)/histogram/$', 'course_histograms'),
    url(r'^(?P<course_key>\w+)/(?P<exercise_key>\w+)/$', 'exercise'),
    url(r'^(?P<course_key>\w+)/(?P<exercise_key>\w+)/json/$', 'exercise_json'),
    url(r'^(?P<course_key>\w+)/(?P<exercise_key>\w+)/json/(?P<student_key>\w+)$', 'exercise_json'),
    url(r'^(?P<course_key>\w+)/(?P<exercise_key>\w+)/settings/$', 'exercise_settings'),
    url(r'^(?P<course_key>\w+)/(?P<exercise_key>\w+)/compare/(?P<ak>\w+)-(?P<bk>\w+)/(?P<ck>\w+)$', 'comparison'),
)
