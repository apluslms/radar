from django.conf.urls import url

from review.views import (
    index, course, course_histograms, marked_submissions,
    configure_course, exercise, exercise_settings, comparison,
    graph, invalidate_graph_cache,
)


urlpatterns = [
    url(r'^$', index, name='index'),
    url(r'^(?P<course_key>\w+)/$', course, name='course'),
    url(r'^(?P<course_key>\w+)/histogram/$', course_histograms, name='course_histograms'),
    url(r'^(?P<course_key>\w+)/marked/$', marked_submissions, name='marked_submissions'),
    url(r'^(?P<course_key>\w+)/configure/$', configure_course, name='configure_course'),
    url(r'^(?P<course_key>\w+)/graph/$', graph, name='graph'),
    url(r'^(?P<course_key>\w+)/graph/invalidate$', invalidate_graph_cache, name='invalidate_graph_cache'),
    url(r'^(?P<course_key>\w+)/(?P<exercise_key>\w+)/$', exercise, name='exercise'),
    url(r'^(?P<course_key>\w+)/(?P<exercise_key>\w+)/settings/$', exercise_settings, name='exercise_settings'),
    url(r'^(?P<course_key>\w+)/(?P<exercise_key>\w+)/compare/(?P<ak>\w+)-(?P<bk>\w+)/(?P<ck>\w+)$', comparison, name='comparison'),
]
