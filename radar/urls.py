from django.conf.urls import patterns, include, url
from django.contrib import admin

import review.urls
import data.urls


urlpatterns = patterns('',

    url(r'^accounts/login/$', 'django.contrib.auth.views.login', {'template_name': 'login.html'}, name='login'),
    url(r'^accounts/logout/$', 'django.contrib.auth.views.logout_then_login', name='logout'),
    url(r'^lti/login$', 'ltilogin.views.lti_login'),
    url(r'^admin/', include(admin.site.urls)),

    url(r'^', include(data.urls)),
    url(r'^', include(review.urls)),
)
