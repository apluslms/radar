from django.urls import re_path

from cheatersheet.views import cheatersheet_proxy_web_view

urlpatterns = [
    re_path(
        r'^cheatersheet/(?P<path>.*)$',
        cheatersheet_proxy_web_view.as_view(),
        name='cheatersheet'
    ),
]