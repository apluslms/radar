from django.conf.urls import include, url
from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView

import data.urls
import review.urls

from django.conf import settings


urlpatterns = [
    url(r'^accounts/login/$', LoginView.as_view(template_name='login.html'), name='login'),
    url(r'^accounts/logout/$', LogoutView.as_view(template_name='login.html'), name='logout'),
    url(r'^auth/', include('django_lti_login.urls')),
    url(r'^admin/', admin.site.urls),

    url(r'^', include(data.urls)),
    url(r'^', include(review.urls)),
]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        url(r'^__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns