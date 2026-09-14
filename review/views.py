import concurrent.futures
import csv
import datetime
import functools
import io
import json
import logging
import mimetypes
import os
import re
import shutil
import tempfile
import time
import zipfile
from urllib.parse import urljoin

import pytz
import requests
from celery.result import AsyncResult
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache, caches
from django.core.handlers.wsgi import WSGIRequest
from django.db.models import Avg, F, OuterRef, Q, Subquery
from django.http import FileResponse
from django.http.response import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template import loader as template_loader
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.timezone import now
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_POST
from kombu import Connection

from cheatersheet.views import send_cheatersheet_comparison
from data import graph
from data.models import Comparison, Course, Exercise, ExerciseDolosReport, Student, Submission
from provider import aplus
from provider.tasks import generate_course_dolos_task, recompare_all
from radar.celery import app
from radar.config import configured_function, provider_config
from radar.settings import (
    CELERY_DEBUG,
    DOLOS_API_SERVER_URL,
    DOLOS_PROXY_API_URL,
    DOLOS_PROXY_WEB_URL,
    DOLOS_WEB_SERVER_URL,
)
from review.decorators import access_resource
from review.dolos_reports import (
    course_progress_cache_key,
    dolos_language,
    write_dataset,
    zip_dataset,
)
from review.forms import DeleteExerciseFrom, ExerciseForm, ExerciseTemplateForm
from review.helpers import build_clusters_for, handle_async_task
from util.misc import is_ajax

# A pending/PROGRESS course-wide report task older than this is treated as
# failed: PENDING is Celery's state for both "queued, worker will start
# soon" and "no worker will ever pick this up", so a hard ceiling is the only
# way to stop the UI from spinning forever when no worker is running.
COURSE_REPORT_STALE_SECONDS = 15 * 60
# After this long with still no progress at all, show a non-fatal hint so the
# user knows this isn't normal instead of silently waiting.
COURSE_REPORT_SLOW_START_HINT_SECONDS = 45

# pylint: disable=no-else-return

logger = logging.getLogger("radar.review")


@login_required
def index(request):
    # Default to Legacy Radar when the mode has not been selected yet.
    request.session.setdefault("legacy_radar", True)
    return render(
        request,
        "review/index.html",
        {
            "hierarchy": ((settings.APP_NAME, None),),
            "courses": Course.objects.get_available_courses(request.user),
        },
    )


@login_required
def toggle_radar_mode(request):
    """Flip between Legacy Radar (default) and New Radar (Dolos) navigation."""
    # Toggle from a Legacy default so first-time users switch to New Radar.
    request.session["legacy_radar"] = not request.session.get("legacy_radar", True)
    request.session.save()
    referer = request.META.get("HTTP_REFERER", "")
    # Only bounce back to a same-site page (avoid open redirects).
    if url_has_allowed_host_and_scheme(referer, allowed_hosts={request.get_host()}):
        return redirect(referer)
    return redirect("index")


@access_resource
def course(request, course_key=None, course=None):
    # Legacy Radar (default) shows the classic management table.
    # New Radar (Dolos) is enabled when legacy_radar is False.
    if request.method == "GET" and not request.session.get("legacy_radar", True):
        first_exercise = course.exercises.first()
        if first_exercise is not None:
            return redirect("dolos_hub_exercise", course_key=course.key, exercise_key=first_exercise.key)
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

        if "recompare_all" in request.POST:
            if not settings.DEBUG or CELERY_DEBUG:
                recompare_all.delay(course.id)
            else:
                recompare_all(course.id)
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


# Render the exercise page (Dolos launcher)
@access_resource
def exercise(
    request: WSGIRequest,
    course_key: str | None = None,
    exercise_key: str | None = None,
    course: Course | None = None,
    exercise: Exercise | None = None
) -> HttpResponse:

    # Legacy Radar (default) shows the classic comparison view.
    # New Radar (Dolos) is enabled when legacy_radar is False.
    if not request.session.get("legacy_radar", True):
        return redirect("dolos_hub_exercise", course_key=course.key, exercise_key=exercise.key)

    rows = int(request.GET.get('rows', settings.SUBMISSION_VIEW_HEIGHT))
    one_pair_per_match = request.GET.get('one_pair_per_match', 'false').lower() == 'true'
    best_submissions = request.GET.get('best_submissions', 'false').lower() == 'true'
    comparisons = exercise.top_comparisons(rows, one_pair_per_match, best_submissions)
    flagged_comparisons = exercise.flagged_comparisons(False)

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
            "comparisons": comparisons,
            "flagged_comparisons": flagged_comparisons,
        },
    )


@access_resource
def configure_course(request, course_key=None, course=None): #pylint: disable=too-many-branches
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
        if not settings.DEBUG:
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
        else:
            # Debug mode, return result immediately
            print("DEBUG MODE")
            pending_api_read["ready"] = True
            exercise_data = pending_api_read['task_id']
            config_table = template_loader.get_template("review/configure_table.html")
            exercise_data["config_type"] = pending_api_read["config_type"]
            pending_api_read["resultHTML"] = config_table.render(exercise_data, request)
            pending_api_read["task_id"] = None
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
            set_use_staff_submissions(request, exercise)
            configured_function(p_config, "recompare")(exercise, p_config)
            context["change_success"].add("clear_and_recompare")
        elif "provider_reload" in request.POST:
            set_use_staff_submissions(request, exercise)
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
    context["use_staff_submissions"] = exercise.use_staff_submissions
    return render(request, "review/exercise_settings.html", context)

# Functions for toggling the use of staff submissions
def set_use_staff_submissions(request, exercise):
    if "use_staff_submissions" in request.POST:
        exercise.use_staff_submissions = True
    else:
        exercise.use_staff_submissions = False
    exercise.save()

def download_file(output_dir, submission, local_course):
    filename = "student" + submission.student.key
    p_config = provider_config(local_course.provider)
    get_submission_text = configured_function(p_config, "get_submission_text")

    with open(os.path.join(output_dir, filename + "|" + str( "Points: " + str(submission.grade))), 'w') as f:
        submission_text = get_submission_text(submission, p_config)
        print("Writing something with length: ", len(submission_text))
        f.write(submission_text)

def download_files(output_dir, local_exercise, local_course, submissions):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(download_file, output_dir, sub, local_course) for
                   sub in submissions]
        concurrent.futures.wait(futures)

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


def write_metadata_for_dolos(exercise_directory, local_exercise, submissions) -> None:
    # Write metadata to CSV file
    with open(exercise_directory + '/info.csv', 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)

        writer.writerow(['filename', 'label', 'created_at'])

        for submission in submissions:
            filename = "student" + submission.student.key + "|" + "Points: " + str(submission.grade)
            created_at = submission.provider_submission_time

            if isinstance(created_at, datetime.datetime):
                created_at = created_at.strftime('%Y-%m-%d %H:%M:%S %z')

            writer.writerow([filename, submission.student.key, created_at])


def go_to_dolos_view(request, course_key=None, exercise_key=None) -> HttpResponse:
    course = Course.objects.get(key=course_key)
    exercise = course.get_exercise(exercise_key)
    if exercise.dolos_report_key != "":
        exercise.dolos_report_status = exercise.dolos_report_status + "\n Could not find report"
        exercise.save()

        return redirect(f"{DOLOS_PROXY_WEB_URL}/#/share/{exercise.dolos_report_id}")
    return HttpResponse("No report generated yet")


@access_resource
def generate_dolos_view(
    request, course_key=None, exercise_key=None, course=None, exercise=None, best_submissions=False, flagged=False
                        ) -> HttpResponse:
    """
    Create a Dolos report of this exercise and redirect to the report visualization
    """
    # Generate new report if timestamp is over 1 hour old or if one does not exist. Disabled for testing
    temp_submissions_dir = os.path.join(os.path.abspath(os.getcwd()), "temp_submission_files")
    if not os.path.exists(temp_submissions_dir):
        os.mkdir(temp_submissions_dir)

    new_submissions_dir = os.path.join(temp_submissions_dir, exercise.key)
    if not os.path.exists(new_submissions_dir):
        os.mkdir(new_submissions_dir)

    submissions = (exercise.valid_submissions | exercise.invalid_submissions)
    if best_submissions == 'true':
        submissions = exercise.best_submissions
    elif flagged == 'true':
        submissions = exercise.flagged_submissions

    # Remove staff submissions
    if exercise.use_staff_submissions is False:
        submissions = submissions.exclude(student__is_staff=True)

    print("Submissions", submissions)

    download_files(new_submissions_dir, exercise, course, submissions.distinct())
    write_metadata_for_dolos(new_submissions_dir, exercise, submissions.distinct())
    zip_files(new_submissions_dir, temp_submissions_dir)

    timestamp = time.time()
    date_and_time = datetime.datetime.fromtimestamp(timestamp, pytz.timezone('Europe/Helsinki'))
    time_string = date_and_time.strftime('Day: %Y-%m-%d - Time: %H.%M.%S')

    programming_language = dolos_language(exercise.tokenizer)

    response = requests.post(
        DOLOS_API_SERVER_URL + '/reports',
        files={'dataset[zipfile]': open(temp_submissions_dir + "/" + exercise.key + ".zip", 'rb')},
        data={'dataset[name]': exercise.name + " | " + time_string,
            'dataset[programming_language]': programming_language},
    )
    # Remove the files in the folder new_submissions_dir
    for file in os.listdir(new_submissions_dir):
        os.remove(os.path.join(new_submissions_dir, file))
    os.remove(temp_submissions_dir + "/" + exercise.key + ".zip")

    try:
        json = response.json()
    except ValueError:
        print("Response is not in JSON format")

    exercise = course.get_exercise(exercise_key)
    exercise.dolos_report_status = "SENT"
    exercise.dolos_report_id = json['id']
    exercise.dolos_report_timestamp = time_string
    exercise.dolos_report_raw_timestamp = timestamp
    exercise.dolos_report_generated = True
    exercise.dolos_report_key = json['html_url']
    exercise.save()

    return go_to_dolos_view(request, course_key, exercise_key)

@method_decorator(csrf_exempt, name='dispatch')
class dolos_proxy_api_view(View):
    # Proxy the request to the Dolos API
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs) -> HttpResponse:
        path = kwargs.get('path', '')
        # Rewrite the URL: prepend the path with the upstream URL
        true_url = urljoin(DOLOS_API_SERVER_URL, path)

        # Prepare the headers
        headers = {key: value for (key, value) in request.META.items() if key.startswith('HTTP_')}
        headers.update({
            'content-type': "*/*",
            'content-length': str(len(request.body)),
        })

        # Prepare the files
        files = list(request.FILES.items())

        # If the path starts with 'static', download and save the file
        if path.startswith('static') or path.startswith('assets') or path.startswith('api/assets'):
            local_file_path = settings.BASE_DIR + "/dolos-api-proxy/" + path

            # Ensure the directory exists
            if not os.path.exists(os.path.dirname(local_file_path)):
                os.makedirs(os.path.dirname(local_file_path), exist_ok=True)

            with requests.get(true_url, stream=True) as r:
                r.raise_for_status()
                with open(local_file_path, 'wb') as f:
                    f.write(r.content)

            if not path.endswith('.ttf') and not path.endswith('.woff2'):
                with open(local_file_path, 'r') as file:
                    filedata = file.read()
                    filedata = filedata.replace(DOLOS_API_SERVER_URL, DOLOS_PROXY_API_URL)
                with open(local_file_path, 'w') as file:
                    file.write(filedata)

            # Determine the file's MIME type
            content_type, _ = mimetypes.guess_type(local_file_path)

            # Send the file as a response
            return FileResponse(open(local_file_path, 'rb'), content_type=content_type)

        # Send the proxied request to the upstream service
        response = requests.request(
            method=request.method,
            url=true_url,
            data=request.body,
            headers=headers,
            files=files,
            cookies=request.COOKIES,
            allow_redirects=True,
        )

        response_content = response.content.replace(DOLOS_API_SERVER_URL.encode(), DOLOS_PROXY_API_URL.encode())

        # Create a Django HttpResponse from the upstream response
        proxy_response = HttpResponse(
            content=response_content,
            status=response.status_code,
        )

        # Add the Access-Control-Allow-Origin header
        proxy_response['Access-Control-Allow-Origin'] = '*'

        # Set the Content-Type header based on the file type
        if request.path.endswith('.css'):
            proxy_response['Content-Type'] = 'text/css'
        elif request.path.endswith('.js'):
            proxy_response['Content-Type'] = 'application/javascript'
        elif request.path.endswith('.ttf'):
            proxy_response['Content-Type'] = 'font/ttf'
        elif request.path.endswith('.woff'):
            proxy_response['Content-Type'] = 'font/woff'
        elif request.path.endswith('.woff2'):
            proxy_response['Content-Type'] = 'font/woff2'
        elif request.path.endswith('.csv'):
            proxy_response['Content-Type'] = 'text/csv'

        return proxy_response

@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(xframe_options_sameorigin, name='dispatch')
class dolos_proxy_view(View):
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs) -> HttpResponse:
        path = kwargs.get('path', '')
        # Rewrite the URL: prepend the path with the upstream URL
        true_url = urljoin(DOLOS_WEB_SERVER_URL, path)

        # Prepare the headers
        headers = {key: value for (key, value) in request.META.items() if key.startswith('HTTP_')}
        headers.update({
            'content-type': "*/*",
            'content-length': str(len(request.body)),
        })

        # Prepare the files
        files = list(request.FILES.items())

        # If the path starts with 'static', download and save the file
        if path.startswith('static') or path.startswith('assets') or path.startswith('api/assets'):
            local_file_path = settings.BASE_DIR + "/dolos-proxy/" + path

            # Ensure the directory exists
            if not os.path.exists(os.path.dirname(local_file_path)):
                os.makedirs(os.path.dirname(local_file_path), exist_ok=True)

            with requests.get(true_url, stream=True) as r:
                r.raise_for_status()
                with open(local_file_path, 'wb') as f:
                    f.write(r.content)

            # If a file contains localhost:3000, replace it with localhost:8000/dolos-api-proxy.
            # But only if the file is not a tff or woff2 file
            if not path.endswith('.ttf') and not path.endswith('.woff2'):
                with open(local_file_path, 'r') as file:
                    filedata = file.read()
                    filedata = filedata.replace(DOLOS_API_SERVER_URL, DOLOS_PROXY_API_URL)
                with open(local_file_path, 'w') as file:
                    file.write(filedata)

            # Determine the file's MIME type
            content_type, _ = mimetypes.guess_type(local_file_path)

            # Send the file as a response
            return FileResponse(open(local_file_path, 'rb'), content_type=content_type)

        # Send the proxied request to the upstream service
        response = requests.request(
            method=request.method,
            url=true_url,
            data=request.body,
            headers=headers,
            files=files,
            cookies=request.COOKIES,
            allow_redirects=True,
        )


        # Create a Django HttpResponse from the upstream response
        # Replace the API server URL with the proxy URL so the frontend can reach the API
        response_content = response.content.replace(
            DOLOS_API_SERVER_URL.encode(), DOLOS_PROXY_API_URL.encode()
        )

        proxy_response = HttpResponse(
            content=response_content,
            status=response.status_code,
        )

        # Add the Access-Control-Allow-Origin header
        proxy_response['Access-Control-Allow-Origin'] = '*'

        # Set the Content-Type header based on the file type
        if path.endswith('.css'):
            proxy_response['Content-Type'] = 'text/css'
        elif path.endswith('.js'):
            proxy_response['Content-Type'] = 'application/javascript'
        elif path.endswith('.ttf'):
            proxy_response['Content-Type'] = 'font/ttf'
        elif path.endswith('.woff'):
            proxy_response['Content-Type'] = 'font/woff'
        elif path.endswith('.woff2'):
            proxy_response['Content-Type'] = 'font/woff2'
        elif path.endswith('.csv'):
            proxy_response['Content-Type'] = 'text/csv'
        return proxy_response

# ---------------------------------------------------------------------------
# Aggregate Dolos reports: per-course (students across exercises) and
# cross-course (exercises across courses). See review/dolos_reports.py for the
# dataset/metadata format that lets Dolos understand this structure.
# ponytail: info.csv metadata drives Dolos visualisation only; Dolos still
# cross-compares every file, so aggregating exercises adds noise you scope
# visually by label (exercise/course) and by the course/exercise ZIP path.
# ---------------------------------------------------------------------------


def _make_get_text():
    """Return get_text(submission) -> source, caching provider config per provider."""
    cache = {}

    def get_text(submission):
        provider = submission.exercise.course.provider
        resolved = cache.get(provider)
        if resolved is None:
            p_config = provider_config(provider)
            resolved = (configured_function(p_config, "get_submission_text"), p_config)
            cache[provider] = resolved
        get_submission_text, p_config = resolved
        return get_submission_text(submission, p_config) or ""

    return get_text


def _exercise_submissions(exercise, include_all=False, newest=None):
    """Submissions to feed Dolos: best-per-student by default, or every valid one
    (several per student) when include_all. Staff excluded unless opted in."""
    if newest:
        newest_ids = (
            exercise.valid_submissions
            .filter(student=OuterRef("student"))
            .order_by("-provider_submission_time", "-id")
            .values("id")[:newest]
        )
        subs = exercise.valid_submissions.filter(id__in=Subquery(newest_ids))
    else:
        subs = exercise.valid_submissions if include_all else exercise.best_submissions
    if not exercise.use_staff_submissions:
        subs = subs.exclude(student__is_staff=True)
    # write_dataset/submission_path touch submission.student and
    # submission.exercise.course for every row; select_related avoids a query
    # per submission for those lookups.
    return subs.select_related("student", "exercise__course")


def _course_submissions(course, include_all=False):
    for exercise in course.exercises.select_related("course").all():
        yield from _exercise_submissions(exercise, include_all)


def _natural_sort_key(exercise):
    """Sort key so "Exercise 2" comes before "Exercise 13" (plain name sorting
    compares digits as text, e.g. "1" < "13" < "2")."""
    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", exercise.name)
    ]


def _generate_dolos_report(submissions, name, programming_language, label_fn):
    """Build + upload a Dolos dataset. Returns the report id, or None if empty."""
    submissions = list(submissions)
    # Dolos needs at least two files to compare (dolos.ts throws otherwise).
    if len(submissions) < 2:
        return None
    work_dir = tempfile.mkdtemp(prefix="dolos_")
    zip_fd, zip_path = tempfile.mkstemp(suffix=".zip")
    os.close(zip_fd)
    try:
        write_dataset(work_dir, submissions, label_fn, _make_get_text())
        zip_dataset(work_dir, zip_path)
        with open(zip_path, "rb") as zip_handle:
            response = requests.post(
                DOLOS_API_SERVER_URL + "/reports",
                files={"dataset[zipfile]": zip_handle},
                data={
                    "dataset[name]": name,
                    "dataset[programming_language]": programming_language,
                },
            )
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
        os.remove(zip_path)
    return response.json().get("id")


def _dolos_report_name(prefix):
    stamp = datetime.datetime.now(pytz.timezone("Europe/Helsinki"))
    return "%s | %s" % (prefix, stamp.strftime("Day: %Y-%m-%d - Time: %H.%M.%S"))


@access_resource
def generate_course_dolos_view(request, course_key=None, course=None) -> HttpResponse:
    """Dolos report over every exercise in a course (students across exercises)."""
    report_id = _generate_dolos_report(
        _course_submissions(course),
        _dolos_report_name(course.name),
        dolos_language(course.tokenizer),
        label_fn=lambda submission: submission.exercise.name,
    )
    if report_id is None:
        return HttpResponse("Need at least two submissions to analyse in this course")
    return redirect("%s/#/share/%s" % (DOLOS_PROXY_WEB_URL, report_id))


@login_required
def generate_cross_course_dolos_view(request) -> HttpResponse:
    """Dolos report over every accessible course (exercises across courses)."""
    submissions = []
    for course in Course.objects.get_available_courses(request.user):
        submissions.extend(_course_submissions(course))
    report_id = _generate_dolos_report(
        submissions,
        _dolos_report_name("All courses"),
        # ponytail: courses may mix languages -> "char" (character-based) always
        # works; split by language and pass a specific Dolos language if noisy.
        "char",
        label_fn=lambda submission: submission.exercise.course.name,
    )
    if report_id is None:
        return HttpResponse("Need at least two submissions to analyse")
    return redirect("%s/#/share/%s" % (DOLOS_PROXY_WEB_URL, report_id))


def _cached_report_id(cache_key, generate):
    # ponytail: best-effort 1h cache so switching hub scopes reuses reports; a
    # missing/broken memcached just regenerates, and staleness clears on TTL.
    try:
        report_id = cache.get(cache_key)
    except Exception:
        report_id = None
    if report_id:
        return report_id
    report_id = generate()
    if report_id:
        try:
            cache.set(cache_key, report_id, 60 * 60)
        except Exception:
            pass
    return report_id


def _too_few_message(selected_count, include_all, total, students, staff_excluded, newest=None):
    """Explain why Dolos has fewer than two files to compare."""
    if newest:
        mode = "%d newest submissions per student" % newest
    else:
        mode = "all submissions" if include_all else "best submission per student"
    msg = (
        "Dolos needs at least 2 files to compare, but only %d matched the current "
        "filter (%s). This exercise has %d submission(s) from %d student(s)%s."
        % (selected_count, mode, total, students,
           " with staff excluded" if staff_excluded else "")
    )
    if not include_all and not newest and total >= 2:
        msg += " Switch to \u201cAll submissions\u201d above to include every submission."
    return msg


def _newest_submission_count(request):
    value = request.GET.get("newest")
    if not value:
        return None
    try:
        return max(1, min(int(value), 100))
    except ValueError:
        return None


def _course_report_task_cache_key(course):
    return "dolos_report:course_task:%d" % course.id


def _course_report_latest_cache_key(course):
    return "dolos_report:course_latest:%d" % course.id


def _course_report_completed_cache_key(course):
    return "dolos_report:course_completed:%d" % course.id


def _course_report_progress_cache_key(task_id):
    return course_progress_cache_key(task_id)


def _course_report_progress_cache():
    return caches["course_report_progress"]


def _store_course_report_progress(task_id, payload, timeout=60 * 60):
    _course_report_progress_cache().set(_course_report_progress_cache_key(task_id), payload, timeout)


def _clear_course_report_progress(task_id):
    try:
        _course_report_progress_cache().delete(_course_report_progress_cache_key(task_id))
    except Exception:
        pass


def _course_report_task_session_key(course):
    return "dolos_course_task_id_%d" % course.id


def _course_report_latest_session_key(course):
    return "dolos_course_report_id_%d" % course.id


def _course_report_started_session_key(course):
    return "dolos_course_task_started_%d" % course.id


def _course_report_completed_session_key(course):
    return "dolos_course_report_completed_%d" % course.id


def _course_report_latest_ids_cache_key(course):
    return "dolos_report:course_latest_ids:%d" % course.id


def _course_report_latest_ids_session_key(course):
    return "dolos_course_report_ids_%d" % course.id


def _course_report_reused_session_key(course):
    return "dolos_course_reports_reused_%d" % course.id


def _store_latest_course_report(course, report_id, completed_at, report_ids=None):
    """Persist latest course-wide report metadata in both session callers and
    shared cache so other pages/sessions can resolve it reliably."""
    if report_ids is None:
        report_ids = [report_id] if report_id else []
    report_ids = [rid for rid in report_ids if rid]
    try:
        cache.set(_course_report_latest_cache_key(course), report_id, 60 * 60 * 24)
        cache.set(_course_report_completed_cache_key(course), completed_at, 60 * 60 * 24)
        cache.set(_course_report_latest_ids_cache_key(course), report_ids, 60 * 60 * 24)
    except Exception:
        pass


def _clear_latest_course_report(course, request):
    request.session.pop(_course_report_latest_session_key(course), None)
    request.session.pop(_course_report_completed_session_key(course), None)
    request.session.pop(_course_report_latest_ids_session_key(course), None)
    try:
        cache.delete(_course_report_latest_cache_key(course))
        cache.delete(_course_report_completed_cache_key(course))
        cache.delete(_course_report_latest_ids_cache_key(course))
    except Exception:
        pass


def _read_latest_course_report(course, request):
    """Read latest course-wide report metadata from session, then cache.

    Returns (report_id, completed_at) where either value may be None.
    """
    report_id = request.session.get(_course_report_latest_session_key(course))
    completed_at = request.session.get(_course_report_completed_session_key(course))

    if report_id:
        return report_id, completed_at

    try:
        report_id = cache.get(_course_report_latest_cache_key(course))
        completed_at = cache.get(_course_report_completed_cache_key(course))
    except Exception:
        report_id = None
        completed_at = None

    if report_id:
        request.session[_course_report_latest_session_key(course)] = report_id
        if completed_at:
            request.session[_course_report_completed_session_key(course)] = completed_at
        request.session.save()

    return report_id, completed_at


def _read_latest_course_report_ids(course, request):
    """Read latest course-wide report id list from session, then cache."""
    report_ids = request.session.get(_course_report_latest_ids_session_key(course))
    if report_ids:
        return [rid for rid in report_ids if rid]

    try:
        report_ids = cache.get(_course_report_latest_ids_cache_key(course))
    except Exception:
        report_ids = None

    if report_ids:
        report_ids = [rid for rid in report_ids if rid]
        request.session[_course_report_latest_ids_session_key(course)] = report_ids
        request.session.save()
        return report_ids

    # Backward compatibility: synthesize from single-report storage.
    report_id, _completed_at = _read_latest_course_report(course, request)
    if report_id:
        report_ids = [report_id]
        request.session[_course_report_latest_ids_session_key(course)] = report_ids
        try:
            cache.set(_course_report_latest_ids_cache_key(course), report_ids, 60 * 60 * 24)
        except Exception:
            pass
        request.session.save()
        return report_ids

    return []


def _build_pending_task_payload(task_id, task_result, started_at=None):
    """Build the payload for a task that is still pending or in progress."""
    payload = {"status": "pending", "task_id": task_id}
    if task_result.info and isinstance(task_result.info, dict):
        payload.update(task_result.info)
    try:
        cached_progress = _course_report_progress_cache().get(_course_report_progress_cache_key(task_id))
        if isinstance(cached_progress, dict):
            payload.update(cached_progress)
    except Exception:
        pass

    if not started_at:
        return payload

    elapsed = time.time() - started_at
    if elapsed > COURSE_REPORT_STALE_SECONDS:
        return {
            "status": "failed",
            "task_id": task_id,
            "message": (
                "Report generation has been queued for over %d minutes with no progress. "
                "This usually means no Celery worker is currently processing the queue. "
                "Check the worker and try again."
                % (COURSE_REPORT_STALE_SECONDS // 60)
            ),
        }
    if elapsed > COURSE_REPORT_SLOW_START_HINT_SECONDS and not payload.get("current_exercise"):
        payload["hint"] = (
            "Still waiting for a worker to pick this up. If this message persists, "
            "confirm a Celery worker is running and connected to the broker."
        )
    return payload


def _build_success_task_payload(task_id, result):
    """Build the payload for a completed task result."""
    if not isinstance(result, dict):
        report_id = result
        if not report_id:
            return {
                "status": "failed",
                "task_id": task_id,
                "message": "Report generation returned no report ID. Check logs for details.",
            }
        payload = {
            "status": "ready",
            "task_id": task_id,
            "report_id": report_id,
            "report_url": "%s/#/share/%s" % (DOLOS_PROXY_WEB_URL, report_id),
        }
        if isinstance(result, dict):
            payload["submissions_included"] = result.get("submissions_included")
            payload["submissions_skipped"] = result.get("submissions_skipped")
            payload["exercises_failed"] = result.get("exercises_failed")
            notes = []
            if result.get("submissions_skipped"):
                notes.append("%d submission(s) skipped (source unavailable)" % result["submissions_skipped"])
            if result.get("exercises_failed"):
                notes.append("%d exercise(s) failed entirely" % result["exercises_failed"])
            payload["message"] = "Report ready." + (" Note: " + ", ".join(notes) + "." if notes else "")
        return payload

    if "report_ids" not in result:
        return {
            "status": "failed",
            "task_id": task_id,
            "message": "Report generation returned no report ID. Check logs for details.",
        }

    report_ids = result.get("report_ids", [])
    exercises_failed = result.get("exercises_failed", [])
    if not report_ids and exercises_failed:
        error_details = []
        for ex in exercises_failed[:3]:
            error_details.append(
                "%s: %s" % (ex.get("name", ex.get("key")), ex.get("error", "Unknown error"))
            )
        extra = " (%d more)" % (len(exercises_failed) - 3) if len(exercises_failed) > 3 else ""
        message = (
            "All exercises failed to generate reports:"
            + extra
            + " "
            + "; ".join(error_details)
        )
        return {
            "status": "failed",
            "task_id": task_id,
            "message": message,
        }

    if not report_ids:
        return {
            "status": "failed",
            "task_id": task_id,
            "message": "Report generation returned no report ID. Check logs for details.",
        }

    report_urls = ["%s/#/share/%s" % (DOLOS_PROXY_WEB_URL, rid) for rid in report_ids]
    payload = {
        "status": "ready",
        "task_id": task_id,
        "report_ids": report_ids,
        "report_urls": report_urls,
        "exercises_processed": result.get("exercises_processed", len(report_ids)),
        "exercises_total": result.get("exercises_total", len(report_ids)),
        "exercises_failed": exercises_failed,
        "submissions_total": result.get("submissions_total", 0),
        "reports_reused": result.get("reports_reused", 0),
        "reports_generated": result.get("reports_generated", len(report_ids)),
    }
    notes = []
    if result.get("submissions_skipped"):
        notes.append("%d submission(s) skipped" % result["submissions_skipped"])
    if exercises_failed:
        notes.append("%d exercise(s) failed" % len(exercises_failed))
    payload["message"] = "Generated %d exercise report(s)." % len(report_ids)
    if notes:
        payload["message"] += " Note: " + ", ".join(notes) + "."
    return payload


def _resolve_course_task_status(course, task_id, started_at=None):
    """Resolve a Celery task id into a stable API payload used by both polling
    endpoints and initial page-load status restore.

    ``started_at`` (epoch seconds), if given, lets a task that has been
    PENDING/PROGRESS for too long be reported as failed instead of polled
    forever -- this is the only way to tell "queued, worker will get to it"
    apart from "no worker is ever going to pick this up" (both look
    identical to Celery: PENDING).
    """
    task_result = AsyncResult(task_id, app=app)
    state = task_result.state

    if state in ("PENDING", "STARTED", "RETRY", "PROGRESS"):
        pending_payload = _build_pending_task_payload(task_id, task_result, started_at=started_at)
        try:
            cached_progress = _course_report_progress_cache().get(_course_report_progress_cache_key(task_id))
        except Exception:
            cached_progress = None
        if isinstance(cached_progress, dict) and cached_progress.get("report_ids"):
            return _build_success_task_payload(task_id, cached_progress)
        return pending_payload

    if state == "SUCCESS":
        return _build_success_task_payload(task_id, task_result.result)

    if state in ("FAILURE", "ERROR", "REVOKED"):
        return {
            "status": "failed",
            "task_id": task_id,
            "message": str(task_result.result) if task_result.result else "Unknown error occurred",
        }

    return {"status": "pending", "task_id": task_id}


def _current_course_report_status(course, request):
    task_id = request.session.get(_course_report_task_session_key(course))
    if not task_id:
        return None
    started = request.session.get(_course_report_started_session_key(course))
    payload = _resolve_course_task_status(course, task_id, started_at=started)
    if payload.get("status") == "idle":
        return None
    return payload


@access_resource
def generate_course_dolos_async(request, course_key=None, course=None) -> JsonResponse:
    """
    Trigger an asynchronous course-wide Dolos report generation.
    Returns a task ID that can be polled for progress.
    """
    if request.method not in ("GET", "POST"):
        return JsonResponse({"status": "failed", "message": "Method not allowed"}, status=405)

    force = request.GET.get("force") == "1" or request.POST.get("force") == "1"

    # Reuse a currently running task for this course so refreshes and repeated
    # clicks continue tracking one job instead of queueing duplicates.
    existing_task_id = request.session.get(_course_report_task_session_key(course))

    if existing_task_id and not force:
        started = request.session.get(_course_report_started_session_key(course))
        existing_status = _resolve_course_task_status(course, existing_task_id, started_at=started)
        if existing_status["status"] == "pending":
            return JsonResponse({
                "status": "queued",
                "task_id": existing_task_id,
                "message": "Course-wide Dolos report generation is already running.",
            })
        # Stale, ready or failed: stop tracking it and fall through to start a fresh task.
        request.session.pop(_course_report_task_session_key(course), None)
        request.session.pop(_course_report_started_session_key(course), None)
        request.session.save()

    if force:
        request.session.pop(_course_report_task_session_key(course), None)
        request.session.pop(_course_report_started_session_key(course), None)
        request.session.save()

    _clear_latest_course_report(course, request)

    try:
        task = generate_course_dolos_task.delay(course_key, force=force)
    except Exception as first_exc:
        # A broker/channel error (e.g. RabbitMQ closing a channel after a
        # previous task held it too long) can leave a broken connection
        # sitting in Celery's producer pool, so every subsequent .delay()
        # keeps failing with the same low-level error until something
        # discards it. Force the pool to drop ALL connections, close any
        # underlying kombu connections, and retry once with a fresh one.
        logger.warning(
            "Failed to queue course-wide Dolos report for %s (%s); "
            "retrying with a fresh broker connection", course_key, first_exc)
        try:
            # Aggressively close all pooled connections
            generate_course_dolos_task.app.pool.force_close_all()
            # Also close any lingering kombu connections in the current thread
            try:
                # Force a fresh connection by creating and immediately closing one
                with Connection(generate_course_dolos_task.app.conf.broker_url):
                    pass
            except Exception:
                pass  # Ignore errors during cleanup
            task = generate_course_dolos_task.delay(course_key, force=force)
        except Exception as exc:
            logger.exception("Failed to queue course-wide Dolos report for %s", course_key)
            return JsonResponse({
                "status": "failed",
                "message": (
                    "Could not queue report generation: %s. Is the task queue "
                    "(Celery/message broker) running?" % exc
                ),
            }, status=503)

    request.session[_course_report_task_session_key(course)] = task.id
    request.session[_course_report_started_session_key(course)] = time.time()
    request.session.pop(_course_report_reused_session_key(course), None)
    request.session.save()

    progress_payload = None
    exercises = list(course.exercises.only("id", "key", "name").all())
    if exercises:
        progress_payload = {
            "phase": "collecting",
            "current_exercise": None,
            "exercises_done": 0,
            "exercises_total": len(exercises),
            "exercises_remaining": len(exercises),
        }
        _store_course_report_progress(task.id, progress_payload)

    response = {
        "status": "queued",
        "task_id": task.id,
        "message": "Course-wide Dolos report generation started. This may take a few minutes."
    }
    if progress_payload:
        response.update(progress_payload)
    return JsonResponse(response)


@access_resource
def check_course_dolos_task(request, course_key=None, task_id=None, course=None) -> JsonResponse:
    """
    Check the status of a course-wide Dolos report generation task.
    Returns:
      - {"status": "pending"} if still running
      - {"status": "ready", "report_url": "..."} if completed successfully
      - {"status": "failed", "message": "..."} if failed
    """
    started = request.session.get(_course_report_started_session_key(course))
    payload = _resolve_course_task_status(course, task_id, started_at=started)
    if payload["status"] == "ready":
        report_ids = payload.get("report_ids") or []
        primary_report_id = payload.get("report_id") or (report_ids[0] if report_ids else None)
    else:
        report_ids = []
        primary_report_id = None

    if payload["status"] == "ready" and primary_report_id:
        completed_at = now().isoformat()
        request.session[_course_report_latest_session_key(course)] = primary_report_id
        request.session[_course_report_completed_session_key(course)] = completed_at
        request.session[_course_report_latest_ids_session_key(course)] = report_ids or [primary_report_id]
        request.session[_course_report_reused_session_key(course)] = payload.get("reports_reused", 0)
        _store_latest_course_report(
            course,
            primary_report_id,
            completed_at,
            report_ids=report_ids or [primary_report_id],
        )
        request.session.pop(_course_report_task_session_key(course), None)
        request.session.pop(_course_report_started_session_key(course), None)
        request.session.save()
        payload["completed_at"] = completed_at
    elif payload["status"] == "failed":
        request.session.pop(_course_report_task_session_key(course), None)
        request.session.pop(_course_report_started_session_key(course), None)
        request.session.save()
    return JsonResponse(payload)


@access_resource
def check_course_dolos_task_current(request, course_key=None, course=None) -> JsonResponse:
    """Current course-wide Dolos generation status for page refresh restore.

    Returns one of:
    - pending + task_id
    - ready + report_url (latest completed within cache TTL)
    - failed + message (including a stale/no-worker task turning into failed)
    - idle
    """
    task_id = request.session.get(_course_report_task_session_key(course))

    if task_id:
        started = request.session.get(_course_report_started_session_key(course))
        payload = _resolve_course_task_status(course, task_id, started_at=started)
        if payload["status"] == "ready":
            report_ids = payload.get("report_ids") or []
            primary_report_id = payload.get("report_id") or (report_ids[0] if report_ids else None)
        else:
            report_ids = []
            primary_report_id = None

        if payload["status"] == "ready" and primary_report_id:
            completed_at = now().isoformat()
            request.session[_course_report_latest_session_key(course)] = primary_report_id
            request.session[_course_report_completed_session_key(course)] = completed_at
            request.session[_course_report_latest_ids_session_key(course)] = report_ids or [primary_report_id]
            request.session[_course_report_reused_session_key(course)] = payload.get(
                "reports_reused", 0
            )
            _store_latest_course_report(
                course,
                primary_report_id,
                completed_at,
                report_ids=report_ids or [primary_report_id],
            )
            request.session.pop(_course_report_task_session_key(course), None)
            request.session.pop(_course_report_started_session_key(course), None)
            request.session.save()
            payload["completed_at"] = completed_at
        elif payload["status"] == "failed":
            request.session.pop(_course_report_task_session_key(course), None)
            request.session.pop(_course_report_started_session_key(course), None)
            request.session.save()
        return JsonResponse(payload)

    latest_report_id, completed_at = _read_latest_course_report(course, request)
    latest_report_ids = _read_latest_course_report_ids(course, request)

    if latest_report_id:
        payload = {
            "status": "ready",
            "report_id": latest_report_id,
            "report_url": "%s/#/share/%s" % (DOLOS_PROXY_WEB_URL, latest_report_id),
            "completed_at": completed_at,
        }
        if latest_report_ids:
            payload["report_ids"] = latest_report_ids
            payload["report_urls"] = [
                "%s/#/share/%s" % (DOLOS_PROXY_WEB_URL, report_id)
                for report_id in latest_report_ids
            ]
        return JsonResponse(payload)

    return JsonResponse({"status": "idle"})


@access_resource
def dolos_hub(request, course_key=None, exercise_key=None, course=None, exercise=None) -> HttpResponse:
    """
    Dolos navigation hub: a Radar nav bar (every exercise) around the Dolos
    report embedded in an iframe. ``?all=1`` includes every submission
    (several per student) instead of only the best per student.

    ``?course_report=1`` shows the "Whole Course" tab instead of a single
    exercise: one Dolos report spanning every exercise, generated
    asynchronously via Celery (see ``generate_course_dolos_async`` and
    ``provider.tasks.generate_course_dolos_task``) since it can take minutes
    for a large course.

    Renders immediately without waiting for report generation: the report id
    is only cheaply peeked from the cache here. If it isn't already cached,
    the page shows a loading indicator and fetches ``dolos_hub_report`` (which
    does the slow zip/upload work) client-side, so the nav bar is usable right
    away instead of the whole page blocking on Dolos.
    """
    # Legacy Radar has no hub: send these URLs to the classic views so the mode
    # toggle takes effect even from inside a Dolos report.
    if request.session.get("legacy_radar", True):
        if exercise is not None:
            return redirect("exercise", course_key=course.key, exercise_key=exercise.key)
        return redirect("course", course_key=course.key)

    course_report_mode = request.GET.get("course_report") == "1"

    if exercise is None:
        first_exercise = course.exercises.first()
        if first_exercise is None:
            return redirect("course", course_key=course.key)

        if course_report_mode:
            latest_report_id, completed_at = _read_latest_course_report(course, request)
            latest_report_ids = _read_latest_course_report_ids(course, request)
            report_url = None
            report_urls = None
            message = None
            if latest_report_ids:
                report_urls = [
                    "%s/#/share/%s" % (DOLOS_PROXY_WEB_URL, report_id)
                    for report_id in latest_report_ids
                ]
                report_url = report_urls[0]
            elif latest_report_id:
                report_url = "%s/#/share/%s" % (DOLOS_PROXY_WEB_URL, latest_report_id)
            else:
                message = "No course-wide report yet. Generate one with 'Generate Course Report'."

            report_status_url = reverse(
                "dolos_hub_exercise_report",
                kwargs={"course_key": course.key, "exercise_key": first_exercise.key},
            )

            return render(
                request,
                "review/dolos_hub.html",
                {
                    "hierarchy": (
                        (settings.APP_NAME, reverse("index")),
                        (course.name, reverse("course", kwargs={"course_key": course.key})),
                        ("Course-wide report", None),
                    ),
                    "course": course,
                    "exercises": _dolos_hub_exercises(course),
                    "current_exercise": first_exercise,
                    "include_all": False,
                    "message": message,
                    "report_url": report_url,
                    "report_urls": report_urls,
                    "exercises_processed": len(report_urls) if report_urls else None,
                    "loading": False,
                    "report_status_url": report_status_url,
                    "course_report_completed_at": completed_at,
                    "course_report_task_status": _current_course_report_status(course, request),
                    "course_report_mode": True,
                    "reports_reused": request.session.get(_course_report_reused_session_key(course)),
                },
            )

        return redirect("dolos_hub_exercise", course_key=course.key, exercise_key=first_exercise.key)

    newest = _newest_submission_count(request)
    include_all = request.GET.get("all") == "1" and newest is None
    force = request.GET.get("force") == "1"
    selected_count, counts_source, staff_excluded = _dolos_hub_scope(
        exercise, include_all, newest
    )
    stored_report = None
    if newest is None:
        stored_report = ExerciseDolosReport.objects.filter(
            exercise=exercise, include_all=include_all
        ).first()

    report_url = None
    report_id = None
    message = None
    loading = False

    if stored_report and not force:
        report_id = stored_report.report_id
        report_url = "%s/#/share/%s" % (DOLOS_PROXY_WEB_URL, stored_report.report_id)
    elif selected_count < 2:
        total = counts_source.count()
        students = counts_source.values("student").distinct().count()
        message = _too_few_message(
            selected_count, include_all, total, students, staff_excluded, newest
        )
    else:
        loading = True

    report_status_url = reverse(
        "dolos_hub_exercise_report", kwargs={"course_key": course.key, "exercise_key": exercise.key}
    )
    if include_all:
        report_status_url += "?all=1"
    elif newest:
        report_status_url += "?newest=%d" % newest
    if force:
        report_status_url += "%sforce=1" % ("&" if "?" in report_status_url else "?")

    return render(
        request,
        "review/dolos_hub.html",
        {
            "hierarchy": (
                (settings.APP_NAME, reverse("index")),
                (course.name, reverse("course", kwargs={"course_key": course.key})),
                (exercise.name, None),
            ),
            "course": course,
            "exercises": _dolos_hub_exercises(course),
            "current_exercise": exercise,
            "include_all": include_all,
            "newest": newest,
            "message": message,
            "report_id": report_id,
            "report_url": report_url,
            "loading": loading,
            "report_status_url": report_status_url,
            "course_report_completed_at": _read_latest_course_report(course, request)[1],
            "course_report_task_status": _current_course_report_status(course, request),
            "course_report_mode": False,
            "report_reused": stored_report is not None and not force,
            "report_generated_at": stored_report.generated_at if stored_report else None,
            "new_submissions_count": (
                exercise.submissions.filter(created__gt=stored_report.generated_at).count()
                if stored_report else 0
            ),
            "report_mode_label": (
                "%d newest per student" % newest if newest else
                "All submissions" if include_all else "Best per student"
            ),
        },
    )


def _dolos_hub_scope(exercise, include_all, newest=None):
    """Cheap (query-only) info about an exercise's hub scope."""
    selected_count = _exercise_submissions(exercise, include_all, newest).count()
    return selected_count, exercise.submissions, not exercise.use_staff_submissions


def _dolos_hub_exercises(course):
    exercises = sorted(course.exercises.all(), key=_natural_sort_key)
    stored_modes = set(
        ExerciseDolosReport.objects.filter(exercise__course=course).values_list(
            "exercise_id", "include_all"
        )
    )
    for exercise in exercises:
        exercise.dolos_report_cached_best = (exercise.id, False) in stored_modes
        exercise.dolos_report_cached_all = (exercise.id, True) in stored_modes
    return exercises


@access_resource
def dolos_hub_report(request, course_key=None, exercise_key=None, course=None, exercise=None) -> JsonResponse:
    """
    AJAX endpoint backing dolos_hub's loading indicator: does the actual
    (potentially slow) submission gathering + report generation/upload, and
    reports back whether a report is ready, empty, or failed.
    """
    newest = _newest_submission_count(request)
    include_all = request.GET.get("all") == "1" and newest is None
    force = request.GET.get("force") == "1"
    stored_report = None
    if newest is None:
        stored_report = ExerciseDolosReport.objects.filter(
            exercise=exercise, include_all=include_all
        ).first()
    if stored_report and not force:
        return JsonResponse({
            "status": "ready",
            "report_id": stored_report.report_id,
            "report_url": "%s/#/share/%s" % (DOLOS_PROXY_WEB_URL, stored_report.report_id),
            "reused": True,
            "mode": "All submissions" if include_all else "Best per student",
        })

    selected = list(_exercise_submissions(exercise, include_all, newest))

    def label_fn(sub):
        return sub.student.display_name

    name, language = (
        _dolos_report_name(exercise.name),
        dolos_language(exercise.tokenizer),
    )
    staff_excluded = not exercise.use_staff_submissions

    if len(selected) < 2:
        total = exercise.submissions.count()
        students = exercise.submissions.values("student").distinct().count()
        return JsonResponse({
            "status": "empty",
            "message": _too_few_message(
                len(selected), include_all, total, students, staff_excluded, newest
            ),
        })

    report_id = _generate_dolos_report(selected, name, language, label_fn)
    if not report_id:
        return JsonResponse({
            "status": "error",
            "message": (
                "Dolos accepted %d files but returned no report \u2014 is the Dolos API "
                "(%s) running?" % (len(selected), DOLOS_API_SERVER_URL)
            ),
        })
    if newest is None:
        ExerciseDolosReport.objects.update_or_create(
            exercise=exercise,
            include_all=include_all,
            defaults={"report_id": report_id, "submissions_included": len(selected)},
        )
    return JsonResponse({
        "status": "ready",
        "report_id": report_id,
        "report_url": "%s/#/share/%s" % (DOLOS_PROXY_WEB_URL, report_id),
        "reused": False,
    })


def _student_key_from_path(path):
    """Recover the student key from a submission_path() ZIP path
    ("course/exercise/<student_key>_<submission_id>.txt")."""
    filename = path.rsplit("/", 1)[-1]
    return filename.rsplit("_", 1)[0]


def _exercise_key_from_path(path):
    """Recover the exercise key from a submission_path() ZIP path
    ("course/exercise/<student_key>_<submission_id>.txt")."""
    parts = [part for part in path.split("/") if part]
    if len(parts) < 2:
        return None
    # Use the parent directory of the file so optional leading prefixes do not
    # break exercise detection (e.g. "dataset/course/exercise/file.txt").
    return parts[-2]


def _submission_id_from_path(path):
    """Recover the submission id from a submission_path() ZIP path."""
    filename = path.rsplit("/", 1)[-1]
    stem, _, suffix = filename.rpartition(".")
    if suffix.lower() != "txt" or "_" not in stem:
        return None
    submission_id = stem.rsplit("_", 1)[-1]
    return submission_id if submission_id.isdigit() else None


def _mini_dolos_report_cache_key(course_key, exercise_key, left_submission_id, right_submission_id):
    ordered_ids = sorted([str(left_submission_id), str(right_submission_id)])
    return "dolos_report:mini:%s:%s:%s:%s" % (
        course_key,
        exercise_key,
        ordered_ids[0],
        ordered_ids[1],
    )


def _dolos_pairs_for_student(report_id, student_key):
    """This student's matches in an already-generated report, sourced from
    Dolos's own pairs data (never recomputed by Radar), highest similarity
    first. Each match is (other_student_key, similarity)."""
    rows = _fetch_dolos_pairs_rows(report_id)
    matches = []
    for row in rows:
        left = _student_key_from_path(row["leftFilePath"])
        right = _student_key_from_path(row["rightFilePath"])
        if left == student_key and right != student_key:
            matches.append((right, float(row["similarity"])))
        elif right == student_key and left != student_key:
            matches.append((left, float(row["similarity"])))
    matches.sort(key=lambda match: match[1], reverse=True)
    return matches


@functools.lru_cache(maxsize=128)
def _fetch_dolos_pairs_rows(report_id):
    """Fetch Dolos pairs rows for a report, preferring the canonical endpoint.

    Dolos API serves report data as ``/reports/:id/data/:file`` where file is
    usually requested as ``pairs.csv``. Some deployments may also accept
    ``pairs``; keep that as a fallback for compatibility.
    """
    urls = [
        "%s/reports/%s/data/pairs.csv" % (DOLOS_API_SERVER_URL, report_id),
        "%s/reports/%s/data/pairs" % (DOLOS_API_SERVER_URL, report_id),
    ]
    last_error = None
    for url in urls:
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return list(csv.DictReader(io.StringIO(response.text)))
        except Exception as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    raise RuntimeError("Failed to fetch Dolos pairs data")


def _collect_pair_exercise_scores(rows, exercises_by_key):
    """Aggregate best similarity scores per student pair and exercise."""
    pair_exercise_scores = {}
    for row in rows:
        left_path = row.get("leftFilePath", "")
        right_path = row.get("rightFilePath", "")
        left_student = _student_key_from_path(left_path)
        right_student = _student_key_from_path(right_path)
        if not left_student or not right_student or left_student == right_student:
            continue

        exercise_key = _exercise_key_from_path(left_path) or _exercise_key_from_path(right_path)
        if not exercise_key or exercise_key not in exercises_by_key:
            continue

        try:
            similarity = float(row.get("similarity", 0))
        except (TypeError, ValueError):
            continue

        pair_key = tuple(sorted((left_student, right_student)))
        ex_scores = pair_exercise_scores.setdefault(pair_key, {})
        current = ex_scores.get(exercise_key)
        if current is None or similarity > current:
            ex_scores[exercise_key] = similarity

    return pair_exercise_scores


def _build_pair_rows(
    pair_exercise_scores,
    exercises_by_key,
    students_by_key,
    min_similarity,
    min_exercises,
):
    """Build pairs with enough exercises at or above the similarity threshold."""
    pair_rows = []
    for (a_key, b_key), ex_scores in pair_exercise_scores.items():
        qualifying_scores = {
            key: similarity
            for key, similarity in ex_scores.items()
            if similarity >= min_similarity
        }
        if len(qualifying_scores) < min_exercises:
            continue
        exercise_keys = sorted(qualifying_scores.keys())
        sims = list(qualifying_scores.values())
        pair_rows.append(
            {
                "a_key": a_key,
                "a_name": students_by_key.get(a_key, a_key),
                "b_key": b_key,
                "b_name": students_by_key.get(b_key, b_key),
                "exercise_count": len(exercise_keys),
                "exercise_names": [exercises_by_key[key].name for key in exercise_keys if key in exercises_by_key],
                "avg_similarity": (sum(sims) / len(sims)) if sims else 0,
                "max_similarity": max(sims) if sims else 0,
            }
        )

    pair_rows.sort(
        key=lambda item: (item["exercise_count"], item["avg_similarity"], item["max_similarity"]),
        reverse=True,
    )
    return pair_rows


def _build_group_rows(pair_rows, students_by_key, limit=20):
    """Build maximal groups where every member pair meets the thresholds."""
    adjacency = {}
    for pair in pair_rows:
        a_key = pair["a_key"]
        b_key = pair["b_key"]
        adjacency.setdefault(a_key, set()).add(b_key)
        adjacency.setdefault(b_key, set()).add(a_key)

    cliques = []

    def find_cliques(current, candidates, excluded):
        if len(cliques) >= limit:
            return
        if not candidates and not excluded:
            if len(current) >= 3:
                cliques.append(current)
            return
        pivot_candidates = candidates | excluded
        pivot = max(
            pivot_candidates,
            key=lambda node: len(candidates & adjacency.get(node, set())),
            default=None,
        )
        remaining = candidates - adjacency.get(pivot, set()) if pivot else set(candidates)
        for node in list(remaining):
            neighbours = adjacency.get(node, set())
            find_cliques(
                current | {node},
                candidates & neighbours,
                excluded & neighbours,
            )
            candidates.remove(node)
            excluded.add(node)

    find_cliques(set(), set(adjacency), set())
    pair_counts = {
        frozenset((pair["a_key"], pair["b_key"])): pair["exercise_count"]
        for pair in pair_rows
    }
    group_rows = []
    for clique in cliques:
        member_keys = sorted(clique)
        edge_counts = [
            pair_counts[frozenset((left, right))]
            for index, left in enumerate(member_keys)
            for right in member_keys[index + 1:]
        ]
        members = sorted(clique, key=lambda key: students_by_key.get(key, key).lower())
        group_rows.append(
            {
                "size": len(clique),
                "member_keys": member_keys,
                "member_slug": "-".join(member_keys),
                "members": [
                    {"key": key, "name": students_by_key.get(key, key)}
                    for key in members
                ],
                "edge_count": len(edge_counts),
                "minimum_shared_exercises": min(edge_counts),
            }
        )

    group_rows.sort(
        key=lambda item: (item["size"], item["minimum_shared_exercises"], item["edge_count"]),
        reverse=True,
    )
    return group_rows


def _build_group_pair_rows(course, report_ids, member_keys):
    """Build raw comparison rows for a group-scoped mini Dolos report."""
    member_keys = [key for key in member_keys if key]
    member_set = set(member_keys)
    exercises_by_key = {ex.key: ex for ex in sorted(course.exercises.all(), key=_natural_sort_key)}
    students_by_key = {s.key: s.display_name for s in course.students.all()}

    comparison_rows = {}
    load_errors = []

    for report_id in report_ids:
        try:
            rows = _fetch_dolos_pairs_rows(report_id)
        except Exception as exc:
            logger.exception(
                "Failed to load Dolos pair rows for group report course=%s report=%s",
                course.key,
                report_id,
            )
            load_errors.append("%s: %s" % (report_id, exc))
            continue

        for row in rows:
            left_path = row.get("leftFilePath", "")
            right_path = row.get("rightFilePath", "")
            left_student = _student_key_from_path(left_path)
            right_student = _student_key_from_path(right_path)
            if (
                not left_student
                or not right_student
                or left_student == right_student
                or left_student not in member_set
                or right_student not in member_set
            ):
                continue

            exercise_key = _exercise_key_from_path(left_path) or _exercise_key_from_path(right_path)
            exercise = exercises_by_key.get(exercise_key)
            if exercise is None:
                continue

            try:
                similarity = float(row.get("similarity", 0))
            except (TypeError, ValueError):
                continue

            left_submission_id = _submission_id_from_path(left_path)
            right_submission_id = _submission_id_from_path(right_path)
            if not left_submission_id or not right_submission_id:
                continue

            pair_key = tuple(sorted((left_student, right_student)))
            row_key = (exercise_key, tuple(sorted((left_path, right_path))))
            current = comparison_rows.get(row_key)
            if current is None or similarity > current["similarity"]:
                comparison_rows[row_key] = {
                    "exercise": exercise,
                    "similarity": similarity,
                    "report_id": report_id,
                    "left_submission_id": left_submission_id,
                    "right_submission_id": right_submission_id,
                    "left_key": left_student,
                    "right_key": right_student,
                    "left_name": students_by_key.get(left_student, left_student),
                    "right_name": students_by_key.get(right_student, right_student),
                    "left_path": left_path,
                    "right_path": right_path,
                    "pair_key": pair_key,
                    "pair_url": reverse(
                        "student_pair_hub",
                        kwargs={"course_key": course.key, "a_key": pair_key[0], "b_key": pair_key[1]},
                    ),
                }

    comparison_rows = sorted(
        comparison_rows.values(),
        key=lambda item: (
            item["similarity"],
            item["exercise"].name.lower(),
            item["left_name"].lower(),
            item["right_name"].lower(),
        ),
        reverse=True,
    )
    return comparison_rows, load_errors


def _build_course_similarity_summary(course, report_ids, min_similarity, min_exercises):
    """Build pair/group summaries from a course-wide Dolos report set.

    Returns dict with:
    - pair_rows: strongest student pairs ranked by shared exercises
    - group_rows: connected student groups (size >= 3) using repeated-pair edges
    - stats: headline counts for quick scanning
    """
    exercises_by_key = {ex.key: ex for ex in course.exercises.all()}
    students_by_key = {s.key: s.display_name for s in course.students.all()}

    rows = []

    def fetch_report(report_id):
        try:
            return report_id, _fetch_dolos_pairs_rows(report_id), None
        except Exception:
            return report_id, (), True

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        fetched_reports = executor.map(fetch_report, report_ids)
        for report_id, report_rows, failed in fetched_reports:
            if failed:
                logger.error(
                    "Failed to load Dolos pair rows for course summary course=%s report=%s",
                    course.key,
                    report_id,
                )
            else:
                rows.extend(report_rows)

    pair_exercise_scores = _collect_pair_exercise_scores(rows, exercises_by_key)
    pair_rows = _build_pair_rows(
        pair_exercise_scores,
        exercises_by_key,
        students_by_key,
        min_similarity,
        min_exercises,
    )
    group_rows = _build_group_rows(pair_rows, students_by_key)

    stats = {
        "pairs_total": len(pair_rows),
        "groups_total": len(group_rows),
        "min_similarity_percent": round(min_similarity * 100),
        "min_exercises": min_exercises,
    }
    return {"pair_rows": pair_rows, "group_rows": group_rows, "stats": stats}


def _compress_matches_by_student(matches):
    """Deduplicate matches by other student key, keeping highest similarity."""
    best_by_student = {}
    for other_key, similarity in matches:
        current = best_by_student.get(other_key)
        if current is None or similarity > current:
            best_by_student[other_key] = similarity
    return sorted(best_by_student.items(), key=lambda item: item[1], reverse=True)


def _student_exercise_matches(course, student_key, include_all=False):
    """Per exercise in course, this student's best Dolos match -- sourced
    straight from that exercise's own generated report so it always agrees
    with what the report itself shows, instead of a separately-computed
    number. ``report_id`` is None if that exercise has no generated report
    yet (nothing to show); ``match`` is None if the report has no match for
    this student, otherwise (other_student_key, similarity).

    Uses only reports for the requested submission set."""
    exercises = sorted(course.exercises.all(), key=_natural_sort_key)
    reports_by_exercise = dict(
        ExerciseDolosReport.objects.filter(
            exercise__course=course, include_all=include_all
        ).values_list("exercise_id", "report_id")
    )

    def fallback_lookup(exercise):
        report_id = reports_by_exercise.get(exercise.id)

        match = None
        all_matches = []
        if report_id:
            try:
                matches = _dolos_pairs_for_student(report_id, student_key)
                all_matches = _compress_matches_by_student(matches)
                match = all_matches[0] if all_matches else None
            except Exception:
                match = None
                all_matches = []
        return exercise, report_id, match, all_matches

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        return list(executor.map(fallback_lookup, exercises))


def _exercise_report_ids(course, include_all=False):
    return list(
        ExerciseDolosReport.objects.filter(
            exercise__course=course, include_all=include_all
        ).values_list("report_id", flat=True)
    )


@access_resource
def students_hub(request, course_key=None, course=None) -> HttpResponse:
    """New Radar: list of students in the course, linking to their
    cross-exercise Dolos similarity page."""
    if request.session.get("legacy_radar", True):
        return redirect("students_view", course_key=course.key)

    unnamed_students = course.students.filter(
        Q(name="") | Q(name__iexact="No Name") | Q(name__iexact="No_Name") | Q(name__iexact="None")
    )
    if course.provider == "a+" and unnamed_students.exists():
        try:
            aplus.sync_student_names(course)
        except Exception:
            logger.warning(
                "Failed to load student names for course=%s",
                course.key,
                exc_info=True,
            )

    include_all = request.GET.get("all") == "1"
    latest_course_report_ids = _exercise_report_ids(course, include_all=include_all)
    latest_course_report_id = latest_course_report_ids[0] if latest_course_report_ids else None
    _latest_report_id, latest_completed_at = _read_latest_course_report(course, request)
    course_report_task_status = _current_course_report_status(course, request)

    summary = None
    summary_error = None
    exercise_count = course.exercises.count()
    max_exercises = max(1, exercise_count)
    try:
        min_similarity_percent = max(0, min(100, int(request.GET.get("similarity", 83))))
    except (TypeError, ValueError):
        min_similarity_percent = 83
    try:
        min_exercises = max(1, min(max_exercises, int(request.GET.get("exercises", 5))))
    except (TypeError, ValueError):
        min_exercises = min(5, max_exercises)
    if latest_course_report_ids:
        try:
            summary = _build_course_similarity_summary(
                course,
                latest_course_report_ids,
                min_similarity_percent / 100,
                min_exercises,
            )
        except Exception as exc:
            logger.exception(
                "Failed to build course similarity summary for course=%s reports=%s",
                course.key,
                latest_course_report_ids,
            )
            summary_error = str(exc)

    return render(
        request,
        "review/students_hub.html",
        {
            "hierarchy": (
                (settings.APP_NAME, reverse("index")),
                (course.name, reverse("course", kwargs={"course_key": course.key})),
                ("Students", None),
            ),
            "course": course,
            "students": course.students.all(),
            "course_report_id": latest_course_report_id,
            "course_report_completed_at": latest_completed_at,
            "course_report_summary": summary,
            "course_report_summary_error": summary_error,
            "course_report_task_status": course_report_task_status,
            "min_similarity_percent": min_similarity_percent,
            "min_exercises": min_exercises,
            "exercise_count": exercise_count,
            "include_all": include_all,
            "show_submission_switch": True,
        },
    )


@access_resource
def student_pair_hub(request, course_key=None, a_key=None, b_key=None, course=None) -> HttpResponse:
    """New Radar: show pair similarities across exercises from course-wide Dolos reports."""
    student_a = get_object_or_404(Student, course=course, key=a_key)
    student_b = get_object_or_404(Student, course=course, key=b_key)

    include_all = request.GET.get("all") == "1"
    latest_report_ids = _exercise_report_ids(course, include_all=include_all)
    exercises_by_key = {ex.key: ex for ex in sorted(course.exercises.all(), key=_natural_sort_key)}
    pair_exercise_scores = {}
    pair_exercise_rows = {}
    load_errors = []

    if latest_report_ids:
        authors = {a_key, b_key}
        for report_id in latest_report_ids:
            try:
                rows = _fetch_dolos_pairs_rows(report_id)
            except Exception as exc:
                logger.exception(
                    "Failed to load Dolos pair rows for course=%s report=%s",
                    course.key,
                    report_id,
                )
                load_errors.append("%s: %s" % (report_id, exc))
                continue

            for row in rows:
                left_path = row.get("leftFilePath", "")
                right_path = row.get("rightFilePath", "")
                left_student = _student_key_from_path(left_path)
                right_student = _student_key_from_path(right_path)
                if {left_student, right_student} != authors:
                    continue

                exercise_key = _exercise_key_from_path(left_path) or _exercise_key_from_path(right_path)
                exercise = exercises_by_key.get(exercise_key)
                if exercise is None:
                    continue

                try:
                    similarity = float(row.get("similarity", 0))
                except (TypeError, ValueError):
                    continue

                left_submission_id = _submission_id_from_path(left_path)
                right_submission_id = _submission_id_from_path(right_path)
                if not left_submission_id or not right_submission_id:
                    continue

                current = pair_exercise_scores.get(exercise_key)
                if current is None or similarity > current["similarity"]:
                    pair_exercise_scores[exercise_key] = {
                        "exercise": exercise,
                        "similarity": similarity,
                        "report_id": report_id,
                        "left_submission_id": left_submission_id,
                        "right_submission_id": right_submission_id,
                        "left_path": left_path,
                        "right_path": right_path,
                    }

                pair_exercise_rows.setdefault(exercise_key, []).append(
                    {
                        "exercise": exercise,
                        "similarity": similarity,
                        "report_id": report_id,
                        "left_submission_id": left_submission_id,
                        "right_submission_id": right_submission_id,
                        "left_path": left_path,
                        "right_path": right_path,
                    }
                )

    pair_rows = sorted(
        pair_exercise_scores.values(),
        key=lambda item: (item["similarity"], item["exercise"].name.lower()),
        reverse=True,
    )

    for row in pair_rows:
        exercise_key = row["exercise"].key
        row["comparison_rows"] = sorted(
            pair_exercise_rows.get(exercise_key, []),
            key=lambda item: item["similarity"],
            reverse=True,
        )

    return render(
        request,
        "review/student_pair_hub.html",
        {
            "hierarchy": (
                (settings.APP_NAME, reverse("index")),
                (course.name, reverse("course", kwargs={"course_key": course.key})),
                ("Students", reverse("students_hub", kwargs={"course_key": course.key})),
                ("%s and %s" % (student_a.display_name, student_b.display_name), None),
            ),
            "course": course,
            "student_a": student_a,
            "student_b": student_b,
            "latest_report_ids": latest_report_ids,
            "pair_rows": pair_rows,
            "load_errors": load_errors,
            "course_report_task_status": _current_course_report_status(course, request),
            "include_all": include_all,
        },
    )


@require_POST
@access_resource
def create_cheatersheet_comparison(
    request,
    course_key=None,
    left_submission_id=None,
    right_submission_id=None,
    course=None,
) -> JsonResponse:
    """Send an exact New Radar submission pair to CheaterSheet."""
    left_submission = get_object_or_404(
        Submission.objects.select_related("exercise", "student"),
        pk=left_submission_id,
        exercise__course=course,
    )
    right_submission = get_object_or_404(
        Submission.objects.select_related("exercise", "student"),
        pk=right_submission_id,
        exercise=left_submission.exercise,
    )
    if left_submission.student_id == right_submission.student_id:
        return JsonResponse({"error": "A comparison requires two different students"}, status=400)

    return _send_cheatersheet_comparison(
        request,
        course,
        left_submission,
        right_submission,
    )


def _send_cheatersheet_comparison(request, course, left_submission, right_submission):
    payload = {
        "comparison": "true",
        "submission_id": left_submission.external_key,
        "student_key": left_submission.student.key,
        "other_submission_id": right_submission.external_key,
        "other_student_key": right_submission.student.key,
        "course_key": str(course.api_id),
        "similarity": request.POST.get("similarity", ""),
        "comment": request.POST.get("comment", "Radar Dolos comparison"),
    }
    return send_cheatersheet_comparison(payload, left_submission.external_key)


@require_POST
@access_resource
def create_cheatersheet_comparison_from_dolos(
    request,
    course_key=None,
    report_id=None,
    pair_id=None,
    course=None,
) -> JsonResponse:
    """Resolve the current Dolos pair and send it to CheaterSheet."""
    try:
        pair = next(
            row for row in _fetch_dolos_pairs_rows(report_id)
            if str(row.get("id")) == str(pair_id)
        )
    except StopIteration:
        return JsonResponse({"error": "The selected Dolos pair was not found"}, status=404)
    except requests.RequestException as exc:
        logger.exception("Failed to load selected Dolos pair")
        return JsonResponse({"error": str(exc)}, status=502)

    left_submission_id = _submission_id_from_path(pair.get("leftFilePath", ""))
    right_submission_id = _submission_id_from_path(pair.get("rightFilePath", ""))
    submissions = {
        submission.pk: submission
        for submission in Submission.objects.select_related("exercise", "student").filter(
            pk__in=[left_submission_id, right_submission_id],
            exercise__course=course,
        )
    }
    try:
        left_submission = submissions[int(left_submission_id)]
        right_submission = submissions[int(right_submission_id)]
    except (KeyError, TypeError, ValueError):
        return JsonResponse({"error": "Dolos pair submissions were not found in this course"}, status=404)
    if left_submission.exercise_id != right_submission.exercise_id:
        return JsonResponse({"error": "Dolos pair submissions belong to different exercises"}, status=400)

    request.POST = request.POST.copy()
    request.POST.setdefault("similarity", pair.get("similarity", ""))
    request.POST.setdefault(
        "comment",
        "Radar Dolos comparison: %s similarity" % pair.get("similarity", ""),
    )
    return _send_cheatersheet_comparison(
        request,
        course,
        left_submission,
        right_submission,
    )


@access_resource
def dolos_mini_comparison(
    request,
    course_key=None,
    a_key=None,
    b_key=None,
    exercise_key=None,
    left_submission_id=None,
    right_submission_id=None,
    course=None,
    exercise=None,
):
    """Open an exact Dolos mini comparison by showing the two submissions."""
    left_submission = get_object_or_404(
        Submission,
        pk=left_submission_id,
        exercise=exercise,
        student__course=course,
    )
    right_submission = get_object_or_404(
        Submission,
        pk=right_submission_id,
        exercise=exercise,
        student__course=course,
    )

    if {left_submission.student.key, right_submission.student.key} != {a_key, b_key}:
        return HttpResponseBadRequest("Submission authors do not match the requested pair")

    cache_key = _mini_dolos_report_cache_key(
        course.key,
        exercise.key,
        left_submission.pk,
        right_submission.pk,
    )

    def generate_report():
        return _generate_dolos_report(
            [left_submission, right_submission],
            _dolos_report_name(
                "%s | %s vs %s"
                % (
                    exercise.name,
                    left_submission.student.display_name,
                    right_submission.student.display_name,
                )
            ),
            dolos_language(exercise.tokenizer),
            label_fn=lambda submission: submission.student.display_name,
        )

    try:
        report_id = _cached_report_id(cache_key, generate_report)
    except Exception as exc:
        logger.exception(
            "Failed to build mini Dolos report for course=%s exercise=%s submissions=%s/%s",
            course.key,
            exercise.key,
            left_submission.pk,
            right_submission.pk,
        )
        return HttpResponseBadRequest("Could not build mini Dolos report: %s" % exc)

    if not report_id:
        return HttpResponse("Need at least two submissions to build a mini Dolos report")

    report_url = "%s/#/share/%s" % (DOLOS_PROXY_WEB_URL, report_id)

    comparison = Comparison.objects.filter(
        submission_a=left_submission,
        submission_b=right_submission,
    ).select_related(
        "submission_a",
        "submission_b",
        "submission_a__exercise",
        "submission_b__exercise",
        "submission_a__student",
        "submission_b__student",
    ).first()
    if comparison is None:
        comparison = Comparison.objects.filter(
            submission_a=right_submission,
            submission_b=left_submission,
        ).select_related(
            "submission_a",
            "submission_b",
            "submission_a__exercise",
            "submission_b__exercise",
            "submission_a__student",
            "submission_b__student",
        ).first()

    comparison_url = None
    if comparison is not None:
        comparison_url = reverse(
            "comparison",
            kwargs={
                "course_key": course.key,
                "exercise_key": exercise.key,
                "ak": comparison.submission_a.student.key,
                "bk": comparison.submission_b.student.key,
                "ck": comparison.pk,
            },
        )

    return render(
        request,
        "review/dolos_mini_comparison.html",
        {
            "hierarchy": (
                (settings.APP_NAME, reverse("index")),
                (course.name, reverse("course", kwargs={"course_key": course.key})),
                ("Students", reverse("students_hub", kwargs={"course_key": course.key})),
                ("Mini comparison", None),
            ),
            "course": course,
            "exercise": exercise,
            "student_a": left_submission.student,
            "student_b": right_submission.student,
            "submission_a": left_submission,
            "submission_b": right_submission,
            "similarity": comparison.similarity if comparison else None,
            "comparison": comparison,
            "report_id": report_id,
            "report_url": report_url,
            "open_report_url": report_url,
            "comparison_url": comparison_url,
        },
    )


@access_resource
def student_group_hub(request, course_key=None, member_keys=None, course=None) -> HttpResponse:
    """New Radar: show a mini Dolos report for one detected student group."""
    if request.session.get("legacy_radar", True):
        return redirect("students_view", course_key=course.key)

    raw_member_keys = [key for key in (member_keys or "").split("-") if key]
    if len(raw_member_keys) < 3:
        return HttpResponseBadRequest("A group report needs at least 3 students")

    group_students = []
    for key in raw_member_keys:
        group_students.append(get_object_or_404(Student, course=course, key=key))

    resolved_member_keys = [student.key for student in group_students]
    include_all = request.GET.get("all") == "1"
    latest_report_ids = _exercise_report_ids(course, include_all=include_all)
    comparison_rows = []
    load_errors = []

    if latest_report_ids:
        comparison_rows, load_errors = _build_group_pair_rows(course, latest_report_ids, resolved_member_keys)

    return render(
        request,
        "review/student_group_hub.html",
        {
            "hierarchy": (
                (settings.APP_NAME, reverse("index")),
                (course.name, reverse("course", kwargs={"course_key": course.key})),
                ("Students", reverse("students_hub", kwargs={"course_key": course.key})),
                ("Group report", None),
            ),
            "course": course,
            "group_students": group_students,
            "latest_report_ids": latest_report_ids,
            "comparison_rows": comparison_rows,
            "load_errors": load_errors,
            "course_report_task_status": _current_course_report_status(course, request),
            "include_all": include_all,
        },
    )


@access_resource
def student_hub(request, course_key=None, student_key=None, course=None, student=None) -> HttpResponse:
    """
    New Radar: one student's similarity across every exercise in the course.

    Sourced entirely from each exercise's own already-generated Dolos report
    (via the Dolos API's pairs data) -- never from Radar's separate legacy
    matcher -- so the numbers shown here always agree with what a reviewer
    sees inside that exercise's report. Exercises without a generated report
    yet show a "not analysed" link instead of guessing a score.
    """
    if request.session.get("legacy_radar", True):
        return redirect("student_view", course_key=course.key, student_key=student_key)

    include_all = request.GET.get("all") == "1"
    students_by_key = {s.key: s.display_name for s in course.students.all()}
    rows = [
        {
            "exercise": exercise,
            "generated": report_id is not None,
            "match": match,
            "all_matches": [
                {
                    "student_key": other_key,
                    "student_name": students_by_key.get(other_key, other_key),
                    "similarity": similarity,
                }
                for other_key, similarity in all_matches
            ],
            "report_url": reverse(
                "dolos_hub_exercise",
                kwargs={"course_key": course.key, "exercise_key": exercise.key},
            ) + ("?all=1" if include_all else ""),
        }
        for exercise, report_id, match, all_matches in _student_exercise_matches(
            course, student_key, include_all=include_all
        )
    ]

    return render(
        request,
        "review/student_hub.html",
        {
            "hierarchy": (
                (settings.APP_NAME, reverse("index")),
                (course.name, reverse("course", kwargs={"course_key": course.key})),
                ("Students", reverse("students_hub", kwargs={"course_key": course.key})),
                (student.display_name, None),
            ),
            "course": course,
            "student": student,
            "rows": rows,
            "include_all": include_all,
        },
    )



# ---------------------------------------------------------------------------
# Legacy Radar: the original comparison / graph / cluster views. Reachable only
# in Legacy Radar mode (New Radar routes to the Dolos hub instead).
# ---------------------------------------------------------------------------


# Render a single comparison between two submissions
@access_resource
def comparison(
    request: WSGIRequest,
    course_key: str | None = None,
    exercise_key: str | None = None,
    ak: str | None = None,
    bk: str | None = None,
    ck: str | None = None,
    course: Course | None = None,
    exercise: Exercise | None = None,
) -> HttpResponse:

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

    # Get the top comparisons for the exercise
    top_comparisons = json.loads(exercise.best_comparisons or '[]')

    # Create a regex to find the current comparison in the top comparisons
    r = re.compile(r'../(.+)-(.+)/' + re.escape(str(comparison.id)))

    try:
        # Find the index of the current comparison in the top comparisons
        index = [i for i, c in enumerate(top_comparisons) if re.search(r, c)][0]

        # Get the next and previous comparisons based on the index
        if index + 1 < len(top_comparisons):
            next_comparison = top_comparisons[index + 1]
        else:
            next_comparison = -1

        if index - 1 >= 0:
            previous_comparison = top_comparisons[index - 1]
        else:
            previous_comparison = -1
    except IndexError:
        index = -1
        next_comparison = -1
        previous_comparison = -1

    context = {
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
            ("%s → %s" % (a.student.key, b.student.key), None),
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
        "next_comparison": next_comparison,
        "previous_comparison": previous_comparison,
        "index": index,
        "top_comparisons": len(top_comparisons),
    }

    return render(
        request,
        "review/comparison.html",
        context,
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
        "number_of_exercises": course.exercises.count(),
    }
    return render(request, "review/graph.html", context)


# This view is used to build the graph data and clusters for the course.
@access_resource
def build_graph(request: WSGIRequest, course: Course | None = None, course_key: str | None = None) -> JsonResponse:
    # If the request is not a POST request or not an AJAX request, return a 400 error
    if request.method != "POST" or not is_ajax(request):
        return HttpResponseBadRequest()

    # Load the task state from the request body
    task_state = json.loads(request.body.decode("utf-8"))

    # Check if the task state is pending
    if task_state["task_id"]:
        task_state = handle_async_task(task_state, course.key)

    # If the task is ready
    elif not task_state["ready"]:
        # Check if the graph data is already cached in the database
        graph_data = json.loads(course.similarity_graph_json or '{}')

        # Get the provider configuration
        p_config = provider_config(course.provider)

        # Get the parameters for the graph
        min_similarity, min_matches, use_unique_ex, origin = (
            task_state["min_similarity"],
            task_state["min_matches"],
            task_state["unique_exercises"],
            task_state["origin"],
        )

        # Check if the graph data is already cached and matches the parameters
        if (
            graph_data
            and graph_data["min_similarity"] == min_similarity
            and graph_data["min_matches"] == min_matches
            and graph_data["unique_exercises"] == use_unique_ex
        ):
            # Check if the clusters are already cached in the database
            clusters = json.loads(course.clusters_json or '{}')

            # Check if the clusters match the parameters
            if (
            clusters
            and clusters["min_similarity"] == min_similarity
            and clusters["min_matches"] == min_matches
            and clusters["unique_exercises"] == use_unique_ex
            and clusters["origin"] == origin
            ):
                # Clusters and graph was already cached
                task_state["graph_data"] = graph_data
                task_state["clusters"] = clusters["clusters"]
                task_state["ready"] = True

            else:
                # Graph was already cached, but clusters not
                task_state["graph_data"] = graph_data

                # Build clusters
                if p_config.get("async_graph", True) or CELERY_DEBUG:
                    async_task = build_clusters_for(task_state, course.key, delay=True)
                    task_state["task_id"] = [None, async_task.id]
                else:
                    task_state["clusters"] = build_clusters_for(task_state, course.key)
                    task_state["ready"] = True

        else:
            # No graph cached, build graph and clusters
            if p_config.get("async_graph", True) or CELERY_DEBUG:
                async_task = graph.generate_match_graph.delay(
                    course.key, float(min_similarity), int(min_matches), use_unique_ex
                )
                task_state["task_id"] = [async_task.id, None]
            else:
                task_state["graph_data"] = graph.generate_match_graph(
                    course.key, float(min_similarity), int(min_matches), use_unique_ex
                )
                task_state["clusters"] = build_clusters_for(task_state, course.key)
                task_state["ready"] = True

    return JsonResponse(task_state)


@access_resource
def invalidate_graph_cache(request, course, course_key):
    course.similarity_graph_json = ''
    course.clusters_json = ''
    course.save()
    return HttpResponse("Graph cache invalidated")


@access_resource
def students_view(request: WSGIRequest, course: Course | None = None, course_key: str | None = None) -> HttpResponse:
    """
    Students view listing students and average/max similarity scores of their submissions
    """
    if not request.session.get("legacy_radar", True):
        return redirect("students_hub", course_key=course.key)

    # Get all submissions for the course
    submissions = (
        Submission.objects.filter(exercise__course=course)
        .values('student__key', 'student__is_staff', 'exercise__name')
        .annotate(
            avg_similarity=Avg('max_similarity'),
        )
    )

    # Exercise names as a list
    exercise_names = course.exercises.all().values_list('name', flat=True)

    # Exercise ids as a list
    exercise_ids = course.exercises.all().values_list('key', flat=True)

    # Student keys
    student_info = submissions.values_list('student__key', 'student__is_staff', 'student__name').distinct()

    students = []

    # Loop through students and their submissions
    for student in student_info:
        # Get all submissions and their similarity for the student
        exercise_similarities = list(
            submissions.filter(student__key=student[0])
            .values_list('exercise__name', 'avg_similarity')
        )

        similarities = list(map(lambda x: x[1], exercise_similarities))

        # Append the student to the list of students
        students.append(
            {
                'key': student[0],
                'is_staff': student[1],
                'name': student[2],
                'exercises': exercise_similarities,
                'avg_similarity': sum(similarities) / len(similarities) if len(similarities) > 0 else "",
            }
        )

        # Check if their submissions are missing for some exercises
        if len(exercise_similarities) == len(exercise_names):
            students[-1]['exercises'] = sorted(students[-1]['exercises'], key=lambda x: x[0])
            continue

        # Add missing exercises
        for exercise in exercise_names:
            if not any(d[0] == exercise for d in students[-1]['exercises']):
                students[-1]['exercises'].append((exercise, ""))

                if len(students[-1]['exercises']) == len(exercise_names):
                    students[-1]['exercises'] = sorted(students[-1]['exercises'], key=lambda x: x[0])
                    break

    context = {
        "hierarchy": (
            (settings.APP_NAME, reverse("index")),
            (course.name, reverse("course", kwargs={"course_key": course.key})),
            ("Students", None),
        ),
        "course": course,
        "exercises": dict(zip(exercise_ids, exercise_names)),
        "students": students,
    }

    return render(request, "review/students_view.html", context)


@access_resource
def student_view(request, course=None, course_key=None, student=None, student_key=None):
    if not request.session.get("legacy_radar", True):
        return redirect("student_hub", course_key=course.key, student_key=student_key)

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
            ("%s → %s" % (a_key, b_key), None),
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
                "%s → %s" % (a_key, b_key),
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


# Render the clusters view
@access_resource
def clusters_view(request: WSGIRequest, course: Course | None = None, course_key: str | None = None) -> HttpResponse:

    context = {
        "hierarchy": (
            (settings.APP_NAME, reverse("index")),
            (course.name, reverse("course", kwargs={"course_key": course.key})),
            ("Clusters", None),
        ),
        "minimum_similarity_threshold": settings.MATCH_STORE_MIN_SIMILARITY,
        "number_of_exercises": course.exercises.count(),
    }

    return render(request, "review/clusters_view.html", context)


# Render the cluster view
@access_resource
def cluster_view(
    request: WSGIRequest,
    cluster_key: str,
    course: Course | None = None,
    course_key: str | None = None
    ) -> HttpResponse:

    # Get the cluster data from the course object
    cluster_data = json.loads(course.clusters_json or '{}')
    if not cluster_data:
        return HttpResponseBadRequest("No cluster data found")

    # Get the cluster data
    min_similarity = cluster_data["min_similarity"]
    min_matches = cluster_data["min_matches"]
    use_unique_ex = cluster_data["unique_exercises"]
    date_time = cluster_data["date_time"]
    cluster = cluster_data["clusters"][int(cluster_key) - 1]
    students = cluster["students"]

    # Get all student similarities for the course
    comparisons = (
        Comparison.objects.filter(submission_a__exercise__course=course)
        .filter(submission_a__student__key__in=students, submission_b__student__key__in=students)
        .annotate(
            student_a=F("submission_a__student__key"),
            student_b=F("submission_b__student__key"),
        )
        .values("student_a", "student_b")
        .annotate(
            avg_similarity=Avg("similarity"),
        )
    )

    # Get the max similarity for each student
    students_sorted = list(
        comparisons.values("student_b")
        .annotate(max_similarity=Avg("similarity"))
        .order_by("-max_similarity")
        .values_list("student_b", flat=True)
    )

    # Create a grid of student pairs and their average similarity
    grid = {}
    for comparison in comparisons:
        grid[comparison["student_a"] + '_' + comparison["student_b"]] = comparison["avg_similarity"]

    context = {
        "hierarchy": (
            (settings.APP_NAME, reverse("index")),
            (course.name, reverse("course", kwargs={"course_key": course.key})),
            ("Clusters", reverse("clusters_view", kwargs={"course_key": course.key})),
            (cluster_key, None),
        ),
        "course": course,
        "cluster_key": cluster_key,
        'min_similarity': min_similarity,
        'min_matches': min_matches,
        'use_unique_ex': use_unique_ex,
        'date_time': date_time,
        "students": students_sorted,
        "grid": grid,
    }

    return render(request, "review/cluster_view.html", context)
