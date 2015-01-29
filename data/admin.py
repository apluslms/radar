from django.contrib import admin
from data.models import Course, Exercise, Student, Submission, Match, MatchGroup

admin.site.register(Course)
admin.site.register(Exercise)
admin.site.register(Student)
admin.site.register(Submission)
admin.site.register(MatchGroup)
admin.site.register(Match)
