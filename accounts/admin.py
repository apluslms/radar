from django.contrib import admin
from accounts import models

admin.site.register(models.RadarUser)
admin.site.register(models.Token)
