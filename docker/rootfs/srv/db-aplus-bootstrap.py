import os
import sys
import django
from datetime import timedelta
from django.utils import timezone

def create_default_users():
    from django.contrib.auth.models import User

    ur = User.objects.create(
        username="root",
        email="root@localhost.invalid",
        first_name="Ruth",
        last_name="Robinson",
        is_superuser=True,
        is_staff=True,
    )
    ur.set_password("root")
    ur.save()
    ur.userprofile.student_id = "<admin>"
    ur.userprofile.save()

    ut = User.objects.create(
        username="teacher",
        email="teacher@localhost.invalid",
        first_name="Terry",
        last_name="Teacher",
    )
    ut.set_password("teacher")
    ut.save()
    ut.userprofile.student_id = "<teacher>"
    ut.userprofile.save()

    ua = User.objects.create(
        username="assistant",
        email="assistant@localhost.invalid",
        first_name="Andy",
        last_name="Assistant",
    )
    ua.set_password("assistant")
    ua.save()
    ua.userprofile.student_id = "133701"
    ua.userprofile.save()

    us = User.objects.create(
        username="student",
        email="student@localhost.invalid",
        first_name="Stacy",
        last_name="Student",
    )
    us.set_password("student")
    us.save()
    us.userprofile.student_id = "123456"
    us.userprofile.save()

    return {
        'root': ur.userprofile,
        'teacher': ut.userprofile,
        'assistant': ua.userprofile,
        'student': us.userprofile
    }

def create_default_courses(users):
    from course.models import Course, CourseInstance, Enrollment

    course = Course.objects.create(
        name="Def. Course",
        code="DEF000",
        url="def",
    )
    course.teachers.set([users['teacher']])

    today = timezone.now()
    instance = CourseInstance.objects.create(
        course=course,
        instance_name="Current",
        url="current",
        starting_time=today,
        ending_time=today + timedelta(days=365),
        configure_url="http://grader:8080/default/aplus-json",
    )
    instance.assistants.set([users['assistant']])

    Enrollment.objects.get_or_create(course_instance=instance, user_profile=users['assistant'])
    Enrollment.objects.get_or_create(course_instance=instance, user_profile=users['student'])

    return {'default': instance}

def create_default_services():
    from external_services.models import LTIService

    services = {}

    services['rubyric+'] = LTIService.objects.create(
        url="http://localhost:8090/",
        menu_label="Rubyric+",
        menu_icon_class="save-file",
        consumer_key="foo",
        consumer_secret="bar",
    )

    services['rubyric'] = LTIService.objects.create(
        url="http://localhost:8091/",
        menu_label="Rubyric",
        menu_icon_class="save-file",
        consumer_key="foo",
        consumer_secret="bar",
    )

    return services


if __name__ == '__main__':
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "aplus.settings")
    sys.path.insert(0, '')
    django.setup()

    users = create_default_users()
    courses = create_default_courses(users)
    services = create_default_services()
