from django.conf.urls import patterns, include, url
from django.contrib import admin

urlpatterns = patterns('',
    
    url(r'^(?P<course_name>\w+)/hook-submission$', 'access.views.hook_submission'),
    
    url(r'^admin/', include(admin.site.urls)),
)
