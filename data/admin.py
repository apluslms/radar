from django.contrib import admin
from data import models

admin.site.register(models.Course)
admin.site.register(models.Exercise)
admin.site.register(models.Student)
admin.site.register(models.Submission)
admin.site.register(models.Comparison)
