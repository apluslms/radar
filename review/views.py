import datetime
import logging
import json
import mimetypes
import time
from urllib.parse import urljoin
import concurrent.futures

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.http.response import JsonResponse, HttpResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect, get_object_or_404
from django.template import loader as template_loader
from celery.result import AsyncResult
from django.utils.timezone import now
from django.views import View
import requests
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from django.db.models import Avg, Max, Q

from data.models import Course, Comparison, Student, Submission
from data import graph
from radar.config import provider_config, configured_function
from radar.settings import DOLOS_API_SERVER_URL, DOLOS_PROXY_API_URL, DOLOS_PROXY_WEB_URL, DOLOS_WEB_SERVER_URL
from review.decorators import access_resource
from review.forms import ExerciseForm, ExerciseTemplateForm, DeleteExerciseFrom
from util.misc import is_ajax
import zipfile
import os
import csv
import pytz
from django.http import FileResponse

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
    one_pair_per_match = request.GET.get('one_pair_per_match', 'false').lower() == 'true'
    best_submissions = request.GET.get('best_submissions', 'false').lower() == 'true'

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
            "comparisons": exercise.top_comparisons(rows, one_pair_per_match, best_submissions),
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
        min_similarity, min_matches, use_unique_ex = (
            task_state["min_similarity"],
            task_state["min_matches"],
            task_state["unique_exercises"],
        )
        if (
            graph_data
            and graph_data["min_similarity"] == min_similarity
            and graph_data["min_matches"] == min_matches
            and graph_data["unique_exercises"] == use_unique_ex
        ):
            # Graph was already cached
            task_state["graph_data"] = graph_data
            task_state["ready"] = True
        else:
            # No graph cached, build
            p_config = provider_config(course.provider)
            if not p_config.get("async_graph", True):
                task_state["graph_data"] = graph.generate_match_graph(
                    course.key, float(min_similarity), int(min_matches), use_unique_ex
                )
                task_state["ready"] = True
            else:
                async_task = graph.generate_match_graph.delay(
                    course.key, float(min_similarity), int(min_matches), use_unique_ex
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
    print("Submissions", submissions)

    download_files(new_submissions_dir, exercise, course, submissions.distinct())
    write_metadata_for_dolos(new_submissions_dir, exercise, submissions.distinct())
    zip_files(new_submissions_dir, temp_submissions_dir)

    timestamp = time.time()
    date_and_time = datetime.datetime.fromtimestamp(timestamp, pytz.timezone('Europe/Helsinki'))
    time_string = date_and_time.strftime('Day: %Y-%m-%d - Time: %H.%M.%S')

    programming_language = exercise.tokenizer
    if exercise.tokenizer == "skip":
        programming_language = "text"

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
        proxy_response = HttpResponse(
            content=response.content,
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
