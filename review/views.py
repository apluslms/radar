import logging
import json

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.http.response import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404

from provider import aplus
from data.models import Course, Comparison
from data.graph import generate_match_graph
from radar.config import provider_config, configured_function
from review.decorators import access_resource
from review.forms import ExerciseForm, ExerciseTokenizerForm


logger = logging.getLogger("radar.review")


@login_required
def index(request):
    return render(request, "review/index.html", {
        "hierarchy": ((settings.APP_NAME, None),),
        "courses": Course.objects.get_available_courses(request.user)
    })


@access_resource
def course(request, course_key=None, course=None):
    return render(request, "review/course.html", {
        "hierarchy": ((settings.APP_NAME, reverse("index")), (course.name, None)),
        "course": course,
        "exercises": course.exercises.all()
    })


@access_resource
def course_histograms(request, course_key=None, course=None):
    return render(request, "review/course_histograms.html", {
        "hierarchy": ((settings.APP_NAME, reverse("index")),
                      (course.name, reverse("course", kwargs={ "course_key": course.key })),
                      ("Histograms", None)),
        "course": course,
        "exercises": course.exercises.all()
    })


@access_resource
def exercise(request, course_key=None, exercise_key=None, course=None, exercise=None):
    return render(request, "review/exercise.html", {
        "hierarchy": ((settings.APP_NAME, reverse("index")),
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

    p_config = provider_config(course.provider)
    get_submission_text = configured_function(p_config, "get_submission_text")
    return render(request, "review/comparison.html", {
        "hierarchy": ((settings.APP_NAME, reverse("index")),
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
        "source_a": get_submission_text(a, p_config),
        "source_b": get_submission_text(b, p_config)
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
        "hierarchy": ((settings.APP_NAME, reverse("index")),
                      (course.name, reverse("course", kwargs={ "course_key": course.key })),
                      ("Marked submissions", None)),
        "course": course,
        "suspects": sorted(suspects.values(), reverse=True, key=lambda e: e['sum']),
    })


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
            radar_config = aplus.get_radar_config(exercise)
            if radar_config:
                yield radar_config


@access_resource
def configure_course(request, course_key=None, course=None):
    context = {
        "hierarchy": ((settings.APP_NAME, reverse("index")),
                      (course.name, reverse("course", kwargs={ "course_key": course.key })),
                      ("Configure", None)),
        "course": course,
        #TODO postable form for editing weights
        "similarity_functions": course.similarityfunction_set.all(),
        "errors": []
    }
    if "retrieve_exercise_data" in request.POST:
        client = request.user.get_api_client(course.namespace)
        if client is None:
            exercises = []
            context["errors"].append("This user does not have correct credentials to use the API of %s" % repr(course))
        else:
            response = client.load_data(course.url)
            exercises = response.get("exercises", [])
        if not exercises:
            context["errors"].append("No exercises found for %s" % repr(course))
        else:
            # Partition all radar configs into unseen and existing as an exercise
            new_exercises, old_exercises = [], []
            for radar_config in leafs_with_radar_config(exercises):
                if course.has_exercise(radar_config["exercise_key"]):
                    old_exercises.append(radar_config)
                else:
                    new_exercises.append(radar_config)
            context["exercises"] = {
                "old": old_exercises,
                "new": new_exercises,
                "new_json": json.dumps(new_exercises),
            }
    elif "create_exercises" in request.POST:
        p_config = provider_config(course.provider)
        exercises = json.loads(request.POST["exercises_json"])
        # TODO gather list of invalid exercise data and render as errors
        for exercise_data in exercises:
            # Create an exercise instance into the database
            key_str = str(exercise_data["exercise_key"])
            exercise = course.get_exercise(key_str)
            exercise.set_from_config(exercise_data)
            exercise.save()
            # Queue fetching all submissions for this exercise
            aplus.reload(exercise, p_config)
        context["create_exercises_success"] = True
    return render(request, "review/configure.html", context)


@access_resource
def graph(request, course, course_key):
    min_similarity = 0.05 # TODO parametrize in UI
    graph_data = generate_match_graph(course, min_similarity)
    context = {
        "hierarchy": (
            (settings.APP_NAME, reverse("index")),
            (course.name, reverse("course", kwargs={ "course_key": course.key })),
            ("Graph", None)
        ),
        "course": course,
        "graph": {
            "min_similarity": min_similarity,
            "graph_json": json.dumps(graph_data),
            "is_empty": not graph_data["nodes"],
        },
    }
    return render(request, "review/graph.html", context)


@access_resource
def exercise_settings(request, course_key=None, exercise_key=None, course=None, exercise=None):
    p_config = provider_config(course.provider)
    context = {
        "hierarchy": (
            (settings.APP_NAME, reverse("index")),
            (course.name, reverse("course", kwargs={ "course_key": course.key })),
            ("%s settings" % (exercise.name), None)
        ),
        "course": course,
        "exercise": exercise,
        "provider_reload": "reload" in p_config
    }
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
        context["form"] = ExerciseForm({
            "name": exercise.name,
            "paused": exercise.paused
        })
        # TODO: Show warning if tokenized(template_source) != exercise.template_tokens
        template_source = aplus.load_exercise_template(exercise, p_config)
        if exercise.template_tokens and not template_source:
            context["template_source_error"] = True
            context["template_tokens"] = exercise.template_tokens
        context["form_tokenizer"] = ExerciseTokenizerForm({
            "tokenizer": exercise.tokenizer,
            "minimum_match_tokens": exercise.minimum_match_tokens,
            "template": template_source,
        })
    return render(request, "review/exercise_settings.html", context)
