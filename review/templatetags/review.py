from django import template
from django.urls import reverse
from ..views import grouped

register = template.Library()


@register.filter
def percent(value):
    if value >= 0:
        return "{:d}%".format(round(100 * value))
    return '-1%'


@register.filter
def get_comparisons_for_student(local_object, student):
    return local_object.comparisons_for_student(student)


@register.inclusion_tag("review/_student.html")
def student_td(course, comparison, b=False):
    submission = comparison.submission_b if b else comparison.submission_a
    return {
        "url": reverse(
            "comparison",
            kwargs={
                "course_key": course.key,
                "exercise_key": comparison.submission_a.exercise.key,
                "ak": comparison.submission_a.student.key,
                "bk": comparison.submission_b.student.key,
                "ck": comparison.pk,
            },
        ),
        "comparison": comparison,
        "submission": submission,
        "student": submission.student,
    }


@register.filter
def group_by(value, arg):
    return grouped(value, arg)
