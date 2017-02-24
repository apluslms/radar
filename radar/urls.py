from django.conf.urls import include, url
from django.contrib import admin
from django.contrib.auth.views import login, logout_then_login

from ltilogin.views import lti_login
import data.urls
import review.urls


urlpatterns = [
    url(r'^accounts/login/$', login, {'template_name': 'login.html'}, name='login'),
    url(r'^accounts/logout/$', logout_then_login, name='logout'),
    url(r'^lti/login$', lti_login, name='lti_login'),
    url(r'^admin/', include(admin.site.urls)),

    url(r'^', include(data.urls)),
    url(r'^', include(review.urls)),
]
