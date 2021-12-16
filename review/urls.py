from django.conf.urls import url

from review.views import (
    build_graph,
    comparison,
    configure_course,
    course,
    course_histograms,
    exercise,
    exercise_settings,
    graph_ui,
    index,
    invalidate_graph_cache,
    marked_submissions,
    students_view,
    student_view,
    pair_view,
    pair_view_summary,
    flagged_pairs,
)


urlpatterns = [
    url(r'^$', index, name='index'),
    url(r'^(?P<course_key>\w+)/$', course, name='course'),
    url(r'^(?P<course_key>\w+)/histogram/$', course_histograms, name='course_histograms'),
    url(r'^(?P<course_key>\w+)/marked/$', marked_submissions, name='marked_submissions'),
    url(r'^(?P<course_key>\w+)/configure/$', configure_course, name='configure_course'),
    url(r'^(?P<course_key>\w+)/graph/$', graph_ui, name='graph_ui'),
    url(r'^(?P<course_key>\w+)/students/$', students_view, name='students_view'),
    url(r'^(?P<course_key>\w+)/students/(?P<student_key>\w+)/$', student_view, name='student_view'),
    url(r'^(?P<course_key>\w+)/(?P<a_key>\w+)-(?P<b_key>\w+)/$', pair_view, name='pair_view'),
    url(r'^(?P<course_key>\w+)/(?P<a_key>\w+)-(?P<b_key>\w+)/summary/$', pair_view_summary, name='pair_view_summary'),
    url(r'^(?P<course_key>\w+)/flagged_pairs/$', flagged_pairs, name='flagged_pairs'),
    url(r'^(?P<course_key>\w+)/graph/build$', build_graph, name='build_graph'),
    url(r'^(?P<course_key>\w+)/graph/invalidate$', invalidate_graph_cache, name='invalidate_graph_cache'),
    url(r'^(?P<course_key>\w+)/(?P<exercise_key>\w+)/$', exercise, name='exercise'),
    url(r'^(?P<course_key>\w+)/(?P<exercise_key>\w+)/settings/$', exercise_settings, name='exercise_settings'),
    url(r'^(?P<course_key>\w+)/(?P<exercise_key>\w+)/compare/(?P<ak>\w+)-(?P<bk>\w+)/(?P<ck>\w+)$', comparison, name='comparison'),
]
