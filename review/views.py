import json
import logging

from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http.response import Http404
from django.shortcuts import get_object_or_404, render, redirect

from data.files import get_submission_text
from data.models import Course, MatchGroup
from review.decorators import access_resource
from radar.config import tokenizer


logger = logging.getLogger("radar.review")


@login_required
def index(request):
    return render(request, "review/index.html", {
        "hierarchy": (("Courses", None),),
        "courses": Course.objects.get_available_courses(request.user)
    })


@access_resource
def course(request, course_name=None, course=None):
    exercises = course.exercises.all()
    for e in exercises:
        e.group_count = e.active_groups().count()

    return render(request, "review/course.html", {
        "hierarchy": (("Courses", reverse("index")), (course.name, None)),
        "course": course,
        "exercises": exercises
    })


@access_resource
def exercise(request, course_name=None, exercise_name=None, course=None, exercise=None):
    groups = exercise.active_groups()
    n = exercise.size
    for g in groups:
        g.ratio = g.size / n
        g.length = len(g.tokens)

    return render(request, "review/exercise.html", {
        "hierarchy": (("Courses", reverse("index")),
                      (course.name, reverse("review.views.course", kwargs={ "course_name": course.name })),
                      (exercise.name, None)),
        "course": course,
        "exercise": exercise,
        "groups": groups
    })


@access_resource
def group(request, course_name=None, exercise_name=None, g_id=None, course=None, exercise=None):
    group = get_object_or_404(MatchGroup, exercise=exercise, pk=g_id)
    largest = group.matches.all().order_by("-length")[0:2]
    return redirect("review.views.comparison", course_name=course_name, exercise_name=exercise_name,
                    g_id=g_id, a_name=largest[0].submission.student.name, b_name=largest[1].submission.student.name)


@access_resource
def comparison(request, course_name=None, exercise_name=None, g_id=None, a_name=None, b_name=None, course=None, exercise=None):
    group = get_object_or_404(MatchGroup, exercise=exercise, pk=g_id)
    match_a = group.matches.filter(submission__student__name=a_name).first()
    match_b = group.matches.filter(submission__student__name=b_name).first()
    if match_a is None or match_b is None:
        raise Http404()
    
    config = tokenizer(exercise)

    return render(request, "review/comparison.html", {
        "hierarchy": (("Courses", reverse("index")),
                      (course.name, reverse("review.views.course", kwargs={ "course_name": course.name })),
                      (exercise.name, reverse("review.views.exercise", kwargs={ "course_name": course.name, "exercise_name": exercise.name })),
                      ("%s vs %s" % (match_a.submission.student.name, match_b.submission.student.name), None)),
        "course": course,
        "exercise": exercise,
        "lang_class": config["lang_class"],
        "source_a": get_submission_text(match_a.submission),
        "parts_a": json.dumps(active_parts(match_a.submission, match_b.submission)),
        "source_b": get_submission_text(match_b.submission),
        "parts_b": json.dumps(active_parts(match_b.submission, match_a.submission))
    })


def active_parts(submission, other):
    chars = list(map(lambda s: s.split("-"), submission.token_positions.split(",")))
    print(len(chars))
    other_groups = list(map(lambda i: i.group.pk, other.active_matches()))
    parts = []
    for m in submission.active_matches():
        print(m.first_token, m.last_token)
        parts.append({ "first": chars[m.first_token][0], "last": chars[m.last_token][1],
                       "group": m.group.pk, "compare": m.group.pk in other_groups })
    return parts
