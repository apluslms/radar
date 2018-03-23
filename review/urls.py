from django.conf.urls import url

from review.views import (
    index, course, course_histograms, marked_submissions,
    exercise, exercise_settings, comparison,
    graph,
)


urlpatterns = [
    url(r'^$', index, name='index'),
    url(r'^(?P<course_key>\w+)/$', course, name='course'),
    url(r'^(?P<course_key>\w+)/histogram/$', course_histograms, name='course_histograms'),
    url(r'^(?P<course_key>\w+)/marked/$', marked_submissions, name='marked_submissions'),
    url(r'^(?P<course_key>\w+)/graph/$', graph, name='graph'),
    url(r'^(?P<course_key>\w+)/(?P<exercise_key>\w+)/$', exercise, name='exercise'),
    url(r'^(?P<course_key>\w+)/(?P<exercise_key>\w+)/settings/$', exercise_settings, name='exercise_settings'),
    url(r'^(?P<course_key>\w+)/(?P<exercise_key>\w+)/compare/(?P<ak>\w+)-(?P<bk>\w+)/(?P<ck>\w+)$', comparison, name='comparison'),
]
