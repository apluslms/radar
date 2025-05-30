from django.conf.urls import include
from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import re_path

import data.urls
import review.urls
import cheatersheet.urls

from django.conf import settings


urlpatterns = [
    re_path(
        r'^accounts/login/$',
        LoginView.as_view(template_name='login.html'),
        name='login',
    ),
    re_path(
        r'^accounts/logout/$',
        LogoutView.as_view(template_name='login.html'),
        name='logout',
    ),
    re_path(r'^auth/', include('django_lti_login.urls')),
    re_path(r'^admin/', admin.site.urls),
    re_path(r'^', include(cheatersheet.urls)),
    re_path(r'^', include(data.urls)),
    re_path(r'^', include(review.urls)),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns = [
        re_path(r'^__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns
