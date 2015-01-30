from django.conf.urls import patterns, include, url
from django.contrib import admin

urlpatterns = patterns('',
    url(r'^(?P<course>\w+/submissionhook$', 'access.views.hook'),
)
