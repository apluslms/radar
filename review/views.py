import logging

import requests
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http.response import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404

from data.files import get_text, get_submission_text
from data.models import Course, Comparison, URLKeyField
from radar.config import provider_config, configured_function
from review.decorators import access_resource
from review.forms import ExerciseForm, ExerciseTokenizerForm, ExerciseOneLineFormSet


logger = logging.getLogger("radar.review")


@login_required
def index(request):
    return render(request, "review/index.html", {
        "hierarchy": (("Radar", None),),
        "courses": Course.objects.get_available_courses(request.user)
    })


@access_resource
def course(request, course_key=None, course=None):
    return render(request, "review/course.html", {
        "hierarchy": (("Radar", reverse("index")), (course.name, None)),
        "course": course,
        "exercises": course.exercises.all()
    })


@access_resource
def course_histograms(request, course_key=None, course=None):
    return render(request, "review/course_histograms.html", {
        "hierarchy": (("Radar", reverse("index")),
                      (course.name, reverse("course", kwargs={ "course_key": course.key })),
                      ("Histograms", None)),
        "course": course,
        "exercises": course.exercises.all()
    })


@access_resource
def exercise(request, course_key=None, exercise_key=None, course=None, exercise=None):
    return render(request, "review/exercise.html", {
        "hierarchy": (("Radar", reverse("index")),
                      (course.name, reverse("course", kwargs={ "course_key": course.key })),
                      (exercise.name, None)),
        "course": course,
        "exercise": exercise,
        "comparisons": exercise.top_comparisons(),
    })


@access_resource
def comparison(request, course_key=None, exercise_key=None, ak=None, bk=None, ck=None, course=None, exercise=None):
    comparison = get_object_or_404(Comparison, submission_a__exercise=exercise, pk=ck,
                                   submission_a__student__key=ak, submission_b__student__key=bk)
    if request.method == "POST":
        result = "review" in request.POST and comparison.update_review(request.POST["review"])
        if request.is_ajax():
            return JsonResponse({ "success": result })

    reverse_flag = False
    a = comparison.submission_a
    b = comparison.submission_b
    if "reverse" in request.GET:
        reverse_flag = True
        a = comparison.submission_b
        b = comparison.submission_a

    return render(request, "review/comparison.html", {
        "hierarchy": (("Radar", reverse("index")),
                      (course.name, reverse("course", kwargs={ "course_key": course.key })),
                      (exercise.name, reverse("exercise",
                                              kwargs={ "course_key": course.key, "exercise_key": exercise.key })),
                      ("%s vs %s" % (a.student.key, b.student.key), None)),
        "course": course,
        "exercise": exercise,
        "comparisons": exercise.comparisons_for_student(a.student),
        "comparison": comparison,
        "reverse": reverse_flag,
        "a": a,
        "b": b,
        "source_a": get_submission_text(a),
        "source_b": get_submission_text(b)
    })


@access_resource
def marked_submissions(request, course_key=None, course=None):
    comparisons = Comparison.objects\
        .filter(submission_a__exercise__course=course, review__gte=5)\
        .order_by("submission_a__created")\
        .select_related("submission_a", "submission_b","submission_a__exercise", "submission_a__student", "submission_b__student")
    suspects = {}
    for c in comparisons:
        for s in (c.submission_a.student, c.submission_b.student):
            if s.id not in suspects:
                suspects[s.id] = { 'key':s.key, 'sum':0, 'comparisons':[] }
            suspects[s.id]['sum'] += c.review
            suspects[s.id]['comparisons'].append(c)
    return render(request, "review/marked.html", {
        "hierarchy": (("Radar", reverse("index")),
                      (course.name, reverse("course", kwargs={ "course_key": course.key })),
                      ("Marked submissions", None)),
        "course": course,
        "suspects": sorted(suspects.values(), reverse=True, key=lambda e: e['sum']),
    })


def request_template_content(url):
    """
    Attempt to GET exercise template contents from url.
    """
    headers = {"content_type": "text/plain",
               "charset": "utf-8"}
    try:
        response = requests.get(url, headers=headers, timeout=(4, 10))
        response.encoding = "utf-8"
        response.raise_for_status()
        return response.text
    except (requests.exceptions.ConnectionError,
            requests.exceptions.ReadTimeout,
            requests.exceptions.HTTPError) as err:
        logger.error(
            "%s when requesting template contents from %s: %s",
            err.__class__.__name__,
            url,
            err)
        return ''


def get_radar_config(exercise):
    """
    Extract relevant Radar data from an AplusApiDict or None if there is no Radar data.
    """
    radar_config = exercise.get("exercise_info", {}).get("radar")
    if not radar_config:
        return None
    data = {
       "name": exercise.get("display_name"),
       "exercise_key": URLKeyField.safe_version(str(exercise.get("id"))),
       "url": exercise.get("html_url"),
       "tokenizer": radar_config.get("tokenizer", "skip"),
       "minimum_match_tokens": radar_config.get("minimum_match_tokens", 15),
    }
    # It is possible to define multiple templates from multiple urls for
    # a single exercise.
    # However, in most cases 'templates' will hold just one url.
    template_urls = exercise.get("templates", None)
    if template_urls:
        template_data = (request_template_content(url) for url in template_urls.split(" ") if url)
        # Join all non-empty templates into a single string, separated by newlines.
        # If there is only one non-empty template in template_data,
        # this will simply evaluate to that template, with no extra newline.
        template_string = '\n'.join(t for t in template_data if t)
        if template_string:
            data["template"] = template_string
    return data


def leafs_with_radar_config(exercises):
    """
    Return an iterator yielding dictionaries of leaf exercises that have Radar configurations.
    """
    if not exercises:
        return
    for exercise in exercises:
        child_exercises = exercise.get("exercises")
        if child_exercises:
            yield from leafs_with_radar_config(child_exercises)
        else:
            radar_config = get_radar_config(exercise)
            if radar_config:
                yield radar_config


@access_resource
def configure_course(request, course_key=None, course=None):
    context = {
        "hierarchy": (("Radar", reverse("index")),
                      (course.name, reverse("course", kwargs={ "course_key": course.key })),
                      ("Configure", None)),
        "course": course,
        "errors": []
    }
    if request.method == "POST":
        if "import_configurations" in request.POST:
            client = request.user.get_api_client(course.namespace)
            response = client.load_data(course.url)
            exercises = response.get("exercises", [])
            if not exercises:
                context["errors"].append("No courses found for course %s", repr(course))
            else:
                exercises = list(leafs_with_radar_config(exercises))
                context["formset"] = ExerciseOneLineFormSet(initial=exercises)
                # TODO check if exercises in database
        if "override_configurations" in request.POST:
            formset = ExerciseOneLineFormSet(request.POST)
            for form in formset:
                if form.is_valid():
                    exercise = course.get_exercise(str(form["exercise_key"]))
                    form.save(exercise)
            context["formset"] = formset
            context["override_success"] = True
    return render(request, "review/configure.html", context)


@access_resource
def exercise_settings(request, course_key=None, exercise_key=None, course=None, exercise=None):
    p_config = provider_config(course.provider)
    if request.method == "POST":
        form = ExerciseForm(request.POST)
        form_tokenizer = ExerciseTokenizerForm(request.POST)
        if "save" in request.POST:
            if form.is_valid():
                form.save(exercise)
                return redirect("course", course_key=course.key)
        if "save_and_clear" in request.POST:
            if form_tokenizer.is_valid():
                form_tokenizer.save(exercise)
                return redirect("course", course_key=course.key)
        if "provider_reload" in request.POST:
            configured_function(p_config, "reload")(exercise, p_config)
            return redirect("course", course_key=course.key)
    else:
        form = ExerciseForm({
            "name": exercise.name,
            "paused": exercise.paused
        })
        form_tokenizer = ExerciseTokenizerForm({
            "tokenizer": exercise.tokenizer,
            "minimum_match_tokens": exercise.minimum_match_tokens,
            "template": get_text(exercise, ".template")
        })
    return render(request, "review/exercise_settings.html", {
        "hierarchy": (("Radar", reverse("index")),
                      (course.name, reverse("course", kwargs={ "course_key": course.key })),
                      ("%s settings" % (exercise.name), None)),
        "course": course,
        "exercise": exercise,
        "form": form,
        "form_tokenizer": form_tokenizer,
        "provider_reload": "reload" in p_config
    })
