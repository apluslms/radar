import datetime
import logging
import json
import shutil
import time

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.http.response import JsonResponse, HttpResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect, get_object_or_404
from django.template import loader as template_loader
from celery.result import AsyncResult
from django.utils.timezone import now

from django.db.models import Avg, Max, Q

from data.models import Course, Comparison, Student, Submission
from data import graph
from radar.config import provider_config, configured_function
from review.decorators import access_resource
from review.forms import ExerciseForm, ExerciseTemplateForm, DeleteExerciseFrom
from util.misc import is_ajax
import requests
import data.files
import zipfile
import os
import psutil
import subprocess
import csv

logger = logging.getLogger("radar.review")


@login_required
def index(request):
    return render(
        request,
        "review/index.html",
        {
            "hierarchy": ((settings.APP_NAME, None),),
            "courses": Course.objects.get_available_courses(request.user),
        },
    )


@access_resource
def course(request, course_key=None, course=None):
    context = {
        "hierarchy": ((settings.APP_NAME, reverse("index")), (course.name, None)),
        "course": course,
        "exercises": course.exercises.all(),
    }
    if request.method == "POST":
        # The user can click "Match all unmatched" for a shortcut to match all unmatched submissions for every exercise
        p_config = provider_config(course.provider)
        if "match-all-unmatched-for-exercises" in request.POST:
            configured_function(p_config, 'recompare_unmatched')(course)
            return redirect("course", course_key=course.key)
    return render(request, "review/course.html", context)


@access_resource
def course_histograms(request, course_key=None, course=None):
    return render(
        request,
        "review/course_histograms.html",
        {
            "hierarchy": (
                (settings.APP_NAME, reverse("index")),
                (course.name, reverse("course", kwargs={"course_key": course.key})),
                ("Histograms", None),
            ),
            "course": course,
            "exercises": course.exercises.all(),
        },
    )


@access_resource
def exercise(request, course_key=None, exercise_key=None, course=None, exercise=None):
    rows = int(request.GET.get('rows', settings.SUBMISSION_VIEW_HEIGHT))
    return render(
        request,
        "review/exercise.html",
        {
            "hierarchy": (
                (settings.APP_NAME, reverse("index")),
                (course.name, reverse("course", kwargs={"course_key": course.key})),
                (exercise.name, None),
            ),
            "course": course,
            "exercise": exercise,
            "comparisons": exercise.top_comparisons(rows),
        },
    )


@access_resource
def comparison(
    request,
    course_key=None,
    exercise_key=None,
    ak=None,
    bk=None,
    ck=None,
    course=None,
    exercise=None,
):
    comparison = get_object_or_404(
        Comparison,
        submission_a__exercise=exercise,
        pk=ck,
        submission_a__student__key=ak,
        submission_b__student__key=bk,
    )
    if request.method == "POST":
        result = "review" in request.POST and comparison.update_review(
            request.POST["review"]
        )
        if is_ajax(request):
            return JsonResponse({"success": result})

    reverse_flag = False
    a = comparison.submission_a
    b = comparison.submission_b
    if "reverse" in request.GET:
        reverse_flag = True
        a = comparison.submission_b
        b = comparison.submission_a

    p_config = provider_config(course.provider)
    get_submission_text = configured_function(p_config, "get_submission_text")
    return render(
        request,
        "review/comparison.html",
        {
            "hierarchy": (
                (settings.APP_NAME, reverse("index")),
                (course.name, reverse("course", kwargs={"course_key": course.key})),
                (
                    exercise.name,
                    reverse(
                        "exercise",
                        kwargs={"course_key": course.key, "exercise_key": exercise.key},
                    ),
                ),
                ("%s vs %s" % (a.student.key, b.student.key), None),
            ),
            "course": course,
            "exercise": exercise,
            "comparisons": exercise.comparisons_for_student(a.student),
            "comparison": comparison,
            "reverse": reverse_flag,
            "a": a,
            "b": b,
            "source_a": get_submission_text(a, p_config),
            "source_b": get_submission_text(b, p_config),
        },
    )


@access_resource
def marked_submissions(request, course_key=None, course=None):
    comparisons = (
        Comparison.objects.filter(submission_a__exercise__course=course, review__gte=5)
        .order_by("submission_a__created")
        .select_related(
            "submission_a",
            "submission_b",
            "submission_a__exercise",
            "submission_a__student",
            "submission_b__student",
        )
    )
    suspects = {}
    for c in comparisons:
        for s in (c.submission_a.student, c.submission_b.student):
            if s.id not in suspects:
                suspects[s.id] = {'key': s.key, 'sum': 0, 'comparisons': []}
            suspects[s.id]['sum'] += c.review
            suspects[s.id]['comparisons'].append(c)
    return render(
        request,
        "review/marked.html",
        {
            "hierarchy": (
                (settings.APP_NAME, reverse("index")),
                (course.name, reverse("course", kwargs={"course_key": course.key})),
                ("Marked submissions", None),
            ),
            "course": course,
            "suspects": sorted(suspects.values(), reverse=True, key=lambda e: e['sum']),
        },
    )


@access_resource
def configure_course(request, course_key=None, course=None):
    context = {
        "hierarchy": (
            (settings.APP_NAME, reverse("index")),
            (course.name, reverse("course", kwargs={"course_key": course.key})),
            ("Configure", None),
        ),
        "course": course,
        "provider_data": [
            {
                "description": "{:s}, all submission data are retrieved from here".format(
                    course.provider_name
                ),
                "path": settings.PROVIDERS[course.provider].get("host", "UNKNOWN"),
            },
            {
                "description": "Data providers should POST the IDs of new submissions to this path in order to"
                               " have them automatically downloaded by Radar",
                "path": request.build_absolute_uri(
                    reverse("hook_submission", kwargs={"course_key": course.key})
                ),
            },
            {
                "description": "Login requests using the LTI-protocol should be made to this path",
                "path": request.build_absolute_uri(reverse("lti_login")),
            },
        ],
        "errors": [],
    }

    # The state of the API read task is contained in this dict
    pending_api_read = {
        "task_id": None,
        "poll_URL": reverse("configure_course", kwargs={"course_key": course.key}),
        "ready": False,
        "poll_interval_seconds": 5,
        "config_type": "automatic",
    }

    if request.method == "GET":
        if "true" in request.GET.get("success", ''):
            # All done, show success message
            context["change_success"] = True
        pending_api_read["json"] = json.dumps(pending_api_read)
        context["pending_api_read"] = pending_api_read
        return render(request, "review/configure.html", context)

    if request.method != "POST":
        return HttpResponseBadRequest()

    p_config = provider_config(course.provider)

    if "create-exercises" in request.POST or "overwrite-exercises" in request.POST:
        # API data has been fetched in a previous step, now the user wants to add exercises
        # that were shown in the table
        if "create-exercises" in request.POST:
            # Pre-configured, read-only table
            exercises = json.loads(request.POST["exercises-json"])
            for exercise_data in exercises:
                key_str = str(exercise_data["exercise_key"])
                exercise = course.get_exercise(key_str)
                exercise.set_from_config(exercise_data)
                exercise.save()
                # Queue fetch and match for all submissions for this exercise
                full_reload = configured_function(p_config, "full_reload")
                full_reload(exercise, p_config)
        elif "overwrite-exercises" in request.POST:
            # Manual configuration, editable table, overwrite existing
            checked_rows = (
                key.split("-", 1)[0] for key in request.POST if key.endswith("enabled")
            )
            exercises = (
                {
                    "exercise_key": exercise_key,
                    "name": request.POST[exercise_key + "-name"],
                    "template_source": request.POST.get(
                        exercise_key + "-template-source", ''
                    ),
                    "tokenizer": request.POST[exercise_key + "-tokenizer"],
                    "minimum_match_tokens": request.POST[
                        exercise_key + "-min-match-tokens"
                    ],
                }
                for exercise_key in checked_rows
            )
            for exercise_data in exercises:
                key = str(exercise_data["exercise_key"])
                course.exercises.filter(key=key).delete()
                exercise = course.get_exercise(key)
                exercise.set_from_config(exercise_data)
                exercise.save()
                full_reload = configured_function(p_config, "full_reload")
                full_reload(exercise, p_config)
        return redirect(
            reverse("configure_course", kwargs={"course_key": course.key})
            + "?success=true"
        )

    if not is_ajax(request):
        return HttpResponseBadRequest("Unknown POST request")

    pending_api_read = json.loads(request.body.decode("utf-8"))

    if pending_api_read["task_id"]:
        # Task is pending, check state and return result if ready
        async_result = AsyncResult(pending_api_read["task_id"])
        if async_result.ready():
            pending_api_read["ready"] = True
            pending_api_read["task_id"] = None
            if async_result.state == "SUCCESS":
                exercise_data = async_result.get()
                async_result.forget()
                config_table = template_loader.get_template(
                    "review/configure_table.html"
                )
                exercise_data["config_type"] = pending_api_read["config_type"]
                pending_api_read["resultHTML"] = config_table.render(
                    exercise_data, request
                )
            else:
                pending_api_read["resultHTML"] = ''
        return JsonResponse(pending_api_read)

    if pending_api_read["ready"]:
        # The client might be polling a few times even after it has received the results
        return JsonResponse(pending_api_read)

    # Put full read of provider API on task queue and store the task id for tracking
    has_radar_config = pending_api_read["config_type"] == "automatic"
    async_api_read = configured_function(p_config, "async_api_read")
    pending_api_read["task_id"] = async_api_read(request, course, has_radar_config)
    return JsonResponse(pending_api_read)


@access_resource
def graph_ui(request, course, course_key):
    """Course graph UI without the graph data."""
    context = {
        "hierarchy": (
            (settings.APP_NAME, reverse("index")),
            (course.name, reverse("course", kwargs={"course_key": course.key})),
            ("Graph", None),
        ),
        "course": course,
        "minimum_similarity_threshold": settings.MATCH_STORE_MIN_SIMILARITY,
    }
    return render(request, "review/graph.html", context)


@access_resource
def build_graph(request, course, course_key):
    if request.method != "POST" or not is_ajax(request):
        return HttpResponseBadRequest()

    task_state = json.loads(request.body.decode("utf-8"))

    if task_state["task_id"]:
        # Task is pending, check state and return result if ready
        async_result = AsyncResult(task_state["task_id"])
        if async_result.ready():
            task_state["ready"] = True
            task_state["task_id"] = None
            if async_result.state == "SUCCESS":
                task_state["graph_data"] = async_result.get()
                async_result.forget()
            else:
                task_state["graph_data"] = {}
    elif not task_state["ready"]:
        graph_data = json.loads(course.similarity_graph_json or '{}')
        min_similarity, min_matches = (
            task_state["min_similarity"],
            task_state["min_matches"],
        )
        if (
            graph_data
            and graph_data["min_similarity"] == min_similarity
            and graph_data["min_matches"] == min_matches
        ):
            # Graph was already cached
            task_state["graph_data"] = graph_data
            task_state["ready"] = True
        else:
            # No graph cached, build
            p_config = provider_config(course.provider)
            if not p_config.get("async_graph", True):
                task_state["graph_data"] = graph.generate_match_graph(
                    course.key, float(min_similarity), int(min_matches)
                )
                task_state["ready"] = True
            else:
                async_task = graph.generate_match_graph.delay(
                    course.key, float(min_similarity), int(min_matches)
                )
                task_state["task_id"] = async_task.id

    return JsonResponse(task_state)


@access_resource
def invalidate_graph_cache(request, course, course_key):
    course.similarity_graph_json = ''
    course.save()
    return HttpResponse("Graph cache invalidated")


@access_resource
def exercise_settings(
    request, course_key=None, exercise_key=None, course=None, exercise=None
):
    p_config = provider_config(course.provider)
    context = {
        "hierarchy": (
            (settings.APP_NAME, reverse("index")),
            (course.name, reverse("course", kwargs={"course_key": course.key})),
            ("%s settings" % (exercise.name), None),
        ),
        "course": course,
        "exercise": exercise,
        "provider_reload": "full_reload" in p_config,
        "change_success": set(),
        "change_failure": {},
    }
    if request.method == "POST":
        if "save" in request.POST:
            form = ExerciseForm(request.POST)
            if form.is_valid():
                form.save(exercise)
                context["change_success"].add("save")
        elif "override_template" in request.POST:
            form_template = ExerciseTemplateForm(request.POST)
            if form_template.is_valid():
                form_template.save(exercise)
                context["change_success"].add("override_template")
        elif "clear_and_recompare" in request.POST:
            configured_function(p_config, "recompare")(exercise, p_config)
            context["change_success"].add("clear_and_recompare")
        elif "provider_reload" in request.POST:
            configured_function(p_config, "full_reload")(exercise, p_config)
            context["change_success"].add("provider_reload")
        elif "delete_exercise" in request.POST:
            form = DeleteExerciseFrom(request.POST)
            if form.is_valid() and form.cleaned_data["name"] == exercise.name:
                exercise.delete()
                return redirect("course", course_key=course.key)

            context["change_failure"]["delete_exercise"] = form.cleaned_data["name"]

    template_source = configured_function(p_config, 'get_exercise_template')(
        exercise, p_config
    )
    if exercise.template_tokens and not template_source:
        context["template_source_error"] = True
        context["template_tokens"] = exercise.template_tokens
        context["template_source"] = ''
    else:
        context["template_source"] = template_source
    context["form"] = ExerciseForm(
        {
            "name": exercise.name,
            "paused": exercise.paused,
            "tokenizer": exercise.tokenizer,
            "minimum_match_tokens": exercise.minimum_match_tokens,
        }
    )
    context["form_template"] = ExerciseTemplateForm(
        {
            "template": template_source,
        }
    )
    context["form_delete_exercise"] = DeleteExerciseFrom({"name": ''})
    return render(request, "review/exercise_settings.html", context)


def zip_files(directory, output_dir):
    # Get the base filename from the directory path
    base = os.path.basename(os.path.normpath(directory))

    # Create a zip file with the same name as the directory in the specified location
    output_zip_file = os.path.join(output_dir, f'{base}.zip')
    with zipfile.ZipFile(output_zip_file, 'w') as zip_handle:
        for foldername, subfolders, filenames in os.walk(directory):  # pylint: disable=unused-variable
            for filename in filenames:
                # Create complete filepath of file in directory
                file_path = os.path.join(foldername, filename)

                # Add file to zip
                zip_handle.write(file_path, arcname=filename)


def kill_process(port):
    for proc in psutil.process_iter(['pid', 'name']):
        if str(proc.info['name']).startswith('node'):
            print("Killing process: " + str(proc.info))
            proc.kill()
            return 0


@access_resource
def dolos_view(request, course_key=None, exercise_key=None, course=None, exercise=None):
    """
    Create a Dolos report of this exercise

    Submit a ZIP-file to the Dolos API for plagiarism detection
    and return the URL where the resulting HTML report can be found.
    """

    submissions = exercise.valid_submissions | exercise.invalid_submissions

    # Write metadata to CSV file
    with open(data.files.path_to_exercise(exercise, "") + 'info.csv', 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)

        writer.writerow(['filename', 'label', 'created_at'])

        for submission in submissions:
            filename = data.files.get_submission_file_name(submission)
            created_at = submission.provider_submission_time

            if isinstance(created_at, datetime.datetime):
                created_at = created_at.strftime('%Y-%m-%d %H:%M:%S %z')

            writer.writerow([filename, 'label', created_at])

    zip_files(data.files.path_to_exercise(exercise, ""), os.getcwd() + "")

    report_directory = os.path.join(os.getcwd(), 'dolos-reps', exercise.key)

    if os.path.exists(report_directory):
        shutil.rmtree(report_directory)

    if exercise.tokenizer == 'skip':
        return HttpResponseBadRequest('Cannot determine exercise language')
    else:
        language = exercise.tokenizer

    kill_process(3000)

    command = ("dolos run -f web -l " + language + " -o " + report_directory + " " +
               os.getcwd() + "/" + exercise.key + ".zip")

    print(command)

    result = subprocess.run(command, shell=True, capture_output=True, text=True)

    print(result.stdout)

@access_resource
def students_view(request, course=None, course_key=None):
    """
    Students view listing students and average/max similarity scores of their submissions
    """

    submissions = (
        Submission.objects.filter(exercise__course=course)
        .values('student__key')
        .annotate(max_avg=Avg('max_similarity'), max=Max('max_similarity'))
    )

    context = {
        "hierarchy": (
            (settings.APP_NAME, reverse("index")),
            (course.name, reverse("course", kwargs={"course_key": course.key})),
            ("Students", None),
        ),
        "course": course,
        "submissions": submissions,
    }

    return render(request, "review/students_view.html", context)


@access_resource
def student_view(request, course=None, course_key=None, student=None, student_key=None):

    comparisons = (
        Comparison.objects.filter(submission_a__exercise__course=course)
        .filter(similarity__gt=0.75)
        .select_related(
            "submission_a",
            "submission_b",
            "submission_a__exercise",
            "submission_b__exercise",
            "submission_a__student",
            "submission_b__student",
        )
        .filter(
            Q(submission_a__student__key=student_key)
            | Q(submission_b__student__key=student_key)
        )
        .exclude(submission_b__isnull=True)
    )

    context = {
        "hierarchy": (
            (settings.APP_NAME, reverse("index")),
            (course.name, reverse("course", kwargs={"course_key": course.key})),
            ("Students", reverse("students_view", kwargs={"course_key": course.key})),
            (student_key, None),
        ),
        "course": course,
        "exercises": course.exercises.all(),
        "student": student_key,
        "comparisons": comparisons,
        "row": range(5),
    }

    return render(request, "review/student_view.html", context)


@access_resource
def pair_view(
    request, course=None, course_key=None, a=None, a_key=None, b=None, b_key=None
):

    authors = {a_key, b_key}
    comparisons = (
        Comparison.objects.filter(submission_a__exercise__course=course)
        .filter(similarity__gt=0)
        .select_related(
            "submission_a",
            "submission_b",
            "submission_a__exercise",
            "submission_b__exercise",
            "submission_a__student",
            "submission_b__student",
        )
        .filter(
            Q(submission_a__student__key__in=authors)
            & Q(submission_b__student__key__in=authors)
        )
    )

    context = {
        "hierarchy": (
            (settings.APP_NAME, reverse("index")),
            (course.name, reverse("course", kwargs={"course_key": course.key})),
            ("%s vs %s" % (a_key, b_key), None),
        ),
        "course": course,
        "exercises": course.exercises.all(),
        "a": a_key,
        "b": b_key,
        "comparisons": comparisons,
    }

    return render(request, "review/pair_view.html", context)


@access_resource
def pair_view_summary(
    request, course=None, course_key=None, a=None, a_key=None, b=None, b_key=None
):

    authors = {a_key, b_key}

    a = Student.objects.get(key=a_key, course=course)
    b = Student.objects.get(key=b_key, course=course)

    # Get comparisons of authors marked as plagiarized
    comparisons = (
        Comparison.objects.filter(submission_a__exercise__course=course)
        .filter(similarity__gt=0)
        .select_related(
            "submission_a",
            "submission_b",
            "submission_a__exercise",
            "submission_b__exercise",
            "submission_a__student",
            "submission_b__student",
        )
        .filter(
            Q(submission_a__student__key__in=authors)
            & Q(submission_b__student__key__in=authors)
        )
        .filter(review=settings.REVIEW_CHOICES[4][0])
    )

    p_config = provider_config(course.provider)
    get_submission_text = configured_function(p_config, "get_submission_text")
    sources = []

    # Loop through comparisons and add to sources
    for n in comparisons:
        reverse_flag = False
        student_a = n.submission_a.student.key
        student_b = n.submission_b.student.key
        text_a = n.submission_a
        text_b = n.submission_b
        submission_text_a = get_submission_text(text_a, p_config)
        submission_text_b = get_submission_text(text_b, p_config)
        matches = n.matches_json
        template_comparisons_a = text_a.template_comparison.matches_json
        template_comparisons_b = text_b.template_comparison.matches_json
        indexes_a = text_a.indexes_json
        indexes_b = text_b.indexes_json
        exercise = n.submission_a.exercise.name

        if "reverse" in request.GET:
            reverse_flag = True
            text_a = n.submission_b
            text_b = n.submission_a
        sources.append(
            {
                "text_a": submission_text_a,
                "text_b": submission_text_b,
                "matches": matches,
                "templates_a": template_comparisons_a,
                "templates_b": template_comparisons_b,
                "indexes_a": indexes_a,
                "indexes_b": indexes_b,
                "reverse_flag": reverse_flag,
                "student_a": student_a,
                "student_b": student_b,
                "exercise": exercise,
            }
        )

    context = {
        "hierarchy": (
            (settings.APP_NAME, reverse("index")),
            (course.name, reverse("course", kwargs={"course_key": course.key})),
            (
                "%s vs %s" % (a_key, b_key),
                reverse(
                    "pair_view",
                    kwargs={"course_key": course_key, "a_key": a_key, "b_key": b_key},
                ),
            ),
            ("Summary", None),
        ),
        "course": course,
        "a": a_key,
        "b": b_key,
        "a_object": a,
        "b_object": b,
        "sources": sources,
        "time": now,
    }

    return render(request, "review/pair_view_summary.html", context)


@access_resource
def flagged_pairs(request, course=None, course_key=None):

    # Get comparisons of students with flagged plagiates
    comparisons = (
        Comparison.objects.filter(submission_a__exercise__course=course)
        .select_related(
            "submission_a",
            "submission_b",
            "submission_a__exercise",
            "submission_a__student",
            "submission_b__student",
        )
        .filter(similarity__gt=0)
        .filter(review=settings.REVIEW_CHOICES[4][0])
    )

    context = {
        "hierarchy": (
            (settings.APP_NAME, reverse("index")),
            (course.name, reverse("course", kwargs={"course_key": course.key})),
            ("Flagged pairs", None),
        ),
        "course": course,
        "comparisons": comparisons,
    }

    return render(request, "review/flagged_pairs.html", context)


# TODO: Move to helper functions
# Helper function for presenting submissions in chunks of count
def grouped(iterator, count):
    # Yield successive n-sized chunks from l.
    for i in range(0, len(iterator), count):
        yield iterator[i: i + count]
