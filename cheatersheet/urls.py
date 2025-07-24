from django.urls import re_path

from cheatersheet.views import cheatersheet_proxy_web_view, cheatersheet_api_add_comparison

urlpatterns = [
    re_path(
        r'^cheatersheet/create-comparison/(?P<submission_id>\d+)/$',
        cheatersheet_api_add_comparison,
        name='cheatersheet_api_add_comparison'
    ),
    re_path(
        r'^cheatersheet/(?P<path>.*)$',
        cheatersheet_proxy_web_view.as_view(),
        name='cheatersheet'
    ),
]