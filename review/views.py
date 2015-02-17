from cgi import escape
import json
import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http.response import Http404
from django.shortcuts import get_object_or_404, render, redirect

from data.files import get_submission_text
from data.models import Course, MatchGroup, Submission
from radar.config import tokenizer
from review.decorators import access_resource


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

    tokenizers = []
    for key in settings.TOKENIZERS:
        tokenizers.append({ "value": key, "name": settings.TOKENIZERS[key]["name"] })

    return render(request, "review/course.html", {
        "hierarchy": (("Courses", reverse("index")), (course.name, None)),
        "course": course,
        "exercises": exercises,
        "tokenizers": tokenizers
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
def exercise_setup(request, course_name=None, exercise_name=None, course=None, exercise=None):
    if request.method == "POST" and "tokenizer" in request.POST and "length" in request.POST:
        tokenizer = request.POST["tokenizer"]
        length = 0
        try:
            length = int(request.POST["length"])
        except ValueError:
            pass
        if tokenizer in settings.TOKENIZERS:
            exercise.override_tokenizer = tokenizer
        if length > 0:
            exercise.override_minimum_match_tokens = length        
        exercise.save()
        exercise.match_groups.all().delete()
        exercise.submissions.all().update(tokens=None, token_positions=None, matching_finished=False)
    return redirect("review.views.course", course_name=course.name)
    

@access_resource
def group(request, course_name=None, exercise_name=None, g_id=None, course=None, exercise=None):
    group = get_object_or_404(MatchGroup, exercise=exercise, pk=g_id)
    matches = []
    def token_html(tokens, b, e):
        if e < len(tokens):
            return "%s<span class=\"match\">%s</span>%s" % (escape(tokens[0:b]), escape(tokens[b:e]), escape(tokens[e:]))
        else:
            return "%s<span class=\"match\">%s</span>" % (escape(tokens[0:b]), escape(tokens[b:]))
    for m in group.matches.all().order_by("-length"):
        matches.append({
            "submission": m.submission,
            "tokens": token_html(m.submission.tokens, m.first_token, m.first_token + m.length)
            })
    return render(request, "review/group.html", {
        "hierarchy": (("Courses", reverse("index")),
                      (course.name, reverse("review.views.course", kwargs={ "course_name": course.name })),
                      (exercise.name, reverse("review.views.exercise", kwargs={ "course_name": course.name, "exercise_name": exercise.name })),
                      ("Group %d" % (group.id), None)),
        "course": course,
        "exercise": exercise,
        "group": group,
        "matches": matches
    })


@access_resource
def submission(request, course_name=None, exercise_name=None, g_id=None, a_id=None, course=None, exercise=None):
    group = get_object_or_404(MatchGroup, exercise=exercise, pk=g_id)
    a = get_object_or_404(Submission, exercise=exercise, pk=a_id)
    match_b = group.matches.exclude(submission__student__name=a.student.name).order_by("-length").first()
    if match_b is None:
        logger.error("Cannot find comparable submission in a group %d", group.pk)
        raise Http404()
    return redirect("review.views.comparison", course_name=course_name, exercise_name=exercise_name,
                    g_id=g_id, a_id=a.pk, b_id=match_b.submission.pk)


@access_resource
def comparison(request, course_name=None, exercise_name=None, g_id=None, a_id=None, b_id=None, course=None, exercise=None):
    group = get_object_or_404(MatchGroup, exercise=exercise, pk=g_id)
    a = get_object_or_404(Submission, exercise=exercise, pk=a_id)
    b = get_object_or_404(Submission, exercise=exercise, pk=b_id)
    match_a = group.matches.filter(submission=a).first()
    match_b = group.matches.filter(submission=b).first()
    if match_a is None or match_b is None:
        raise Http404()
    config = tokenizer(exercise)
    def match_dict(match):
        idx = match.submission.token_position_indexes()
        return [{ "first": idx[match.first_token][0], "last": idx[match.last_token][1],
                "group": match.group.pk, "compare": True }]
    return render(request, "review/comparison.html", {
        "hierarchy": (("Courses", reverse("index")),
                      (course.name, reverse("review.views.course", kwargs={ "course_name": course.name })),
                      (exercise.name, reverse("review.views.exercise", kwargs={ "course_name": course.name, "exercise_name": exercise.name })),
                      ("%s vs %s" % (match_a.submission.student.name, match_b.submission.student.name), None)),
        "course": course,
        "exercise": exercise,
        "lang_class": config["lang_class"],
        "source_a": get_submission_text(match_a.submission),
        "parts_a": json.dumps(match_dict(match_a)),
        "source_b": get_submission_text(match_b.submission),
        "parts_b": json.dumps(match_dict(match_b))
    })

def active_parts(submission, other):
    chars = submission.token_position_indexes()
    other_groups = list(map(lambda i: i.group.pk, other.active_matches()))
    parts = []
    for m in submission.active_matches():
        parts.append({ "first": chars[m.first_token][0], "last": chars[m.last_token][1],
                       "group": m.group.pk, "compare": m.group.pk in other_groups })
    return parts
