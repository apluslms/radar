"""
Celery tasks for asynchronous submission processing.
Contains some hard-coded A+ specific stuff that should be generalized.
"""

import datetime
import json
import os
import shutil
import tempfile
import time

import celery
import pytz
import requests
from celery.exceptions import SoftTimeLimitExceeded
from celery.utils.log import get_task_logger
from django.conf import settings
from django.core.cache import caches

from data.models import Course, Exercise, ExerciseDolosReport, TaskError
from matcher import tasks as matcher_tasks
from provider import aplus
from provider.insert import (
    submission_exists,
    insert_submission,
    prepare_submission,
    InsertError,
)
import radar.config as config_loaders
from radar.settings import DEBUG, CELERY_DEBUG, DOLOS_API_SERVER_URL
from review.dolos_reports import (
    course_progress_cache_key,
    refresh_progress_cache_key,
    dolos_language,
    write_info_csv,
    write_submission_files,
    zip_dataset,
)


logger = get_task_logger(__name__)


@celery.shared_task(soft_time_limit=570, time_limit=600, ignore_result=True)
def load_radar_page_data(course_id, operation, arguments, key):
    from review import views

    store = caches["course_report_progress"]
    try:
        course = Course.objects.get(pk=course_id)
        if operation == "course_home":
            include_all, students_page, version = arguments
            result = views._build_course_home_data(course, include_all, students_page)
        elif operation == "summary":
            if course.provider == "a+":
                try:
                    aplus.sync_student_names(course)
                except Exception:
                    logger.warning("Background roster refresh failed", exc_info=True)
            for report_id in arguments[0]:
                views._fetch_dolos_pairs_rows(report_id)
            result = views._build_course_similarity_summary(course, *arguments)
        elif operation == "student_matches":
            student_key, include_all, report_ids = arguments
            for report_id in report_ids:
                views._fetch_dolos_pairs_rows(report_id)
            result = views._student_exercise_matches(course, student_key, include_all)
        elif operation == "group_pairs":
            for report_id in arguments[0]:
                views._fetch_dolos_pairs_rows(report_id)
            result = views._build_group_pair_rows(course, *arguments)
        elif operation == "mini_report":
            exercise_id, left_id, right_id = arguments
            exercise = course.exercises.get(pk=exercise_id)
            submissions = list(exercise.submissions.filter(pk__in=[left_id, right_id]).select_related("student"))
            if len(submissions) != 2:
                raise ValueError("Mini report submissions no longer exist")
            result = views._generate_dolos_report(
                submissions, views._dolos_report_name(exercise.name),
                dolos_language(exercise.tokenizer),
                label_fn=lambda submission: submission.student.display_name,
            )
            if not result:
                raise ValueError("Dolos returned no mini report")
        elif operation == "exercise_report":
            exercise_id, include_all, newest = arguments
            exercise = course.exercises.get(pk=exercise_id)
            result = views._build_hub_report_data(exercise, include_all, newest)
        else:
            raise ValueError("Unknown background operation")
        store.set(key, {"status": "ready", "result": result}, 30 if operation == "course_home" else 600)
    except Exception:
        logger.exception("Background Radar page data failed for course=%s operation=%s", course_id, operation)
        store.set(key, {"status": "failed", "message": "Background loading failed. Check the worker log and retry."}, 600)
    finally:
        caches["default"].delete(key + ":lock")


class ProviderAPIError(Exception):
    pass


class APIAuthException(ProviderAPIError):
    pass


class CourseReportError(Exception):
    """Raised when a course-wide Dolos report cannot be produced."""


# Highly I/O bound task, recommended to be consumed by several workers
@celery.shared_task(bind=True, ignore_result=True)
def create_submission(
    task, submission_key, course_key, submission_api_url, matching_start_time=''
):
    """
    Fetch submission data for a new submission with provider key submission_key from a given API url,
    create new submission, and tokenize submission content. If matching_start_time timestamp is given,
    it will be written into the submission object before writing.
    """
    course = Course.objects.get(key=course_key)
    if submission_exists(submission_key):
        write_error(
            "Submission with key %s already exists, will not create a duplicate."
            % submission_key,
            "create_submission",
        )
        return

    # We need someone with a token to the A+ API.
    api_client = aplus.get_api_client(course)
    # Request data from provider API
    try:
        data = api_client.load_data(submission_api_url)
    except (
        requests.exceptions.ConnectionError,
        requests.exceptions.ReadTimeout,
    ):
        logger.exception("Unable to read data from the API.")
        data = None

    del api_client

    if not data:
        logger.error(
            "API returned nothing for submission %s, skipping submission",
            submission_key,
        )
        return

    exercise_data = data["exercise"]

    # Check if exercise is configured for Radar
    # If not, and there is no manually configured exercise in the database, skip
    radar_config = aplus.get_radar_config(exercise_data, course)
    if radar_config is None and not course.has_exercise(str(exercise_data["id"])):
        return

    # Get or create exercise configuration
    exercise = course.get_exercise(str(exercise_data["id"]))
    if exercise.name == "unknown":
        # Get template source
        try:
            radar_config["template_source"] = radar_config["get_template_source"]()
        except Exception as e:
            write_error(
                "Error while attempting to get template source for submission %s\n%s"
                % (submission_key, str(e)),
                "create_submission",
            )
            radar_config["template_source"] = ''
        exercise.set_from_config(radar_config)
        exercise.save()

    del radar_config

    # A+ allows more than one submitter for a single submission
    # TODO: if there are more than one unique submitters,
    # set as approved plagiate and show this in the UI
    ## for submitter_id in _decode_students(data["submitters"]):
    submitter_id = "_".join(aplus._decode_students(data["submitters"]))
    submitter_name = "_".join(aplus.get_student_names(data["submitters"]))

    # Check if any of the submitters is a staff member
    is_staff = check_if_staff(data, course)

    if is_staff:
        submitter_id += "_STAFF"

    try:
        submission = insert_submission(
            exercise, submission_key, submitter_id, submitter_name, data
        )

        # If any of the submitters is a staff member, set the student as staff
        if is_staff:
            staff = submission.student
            staff.is_staff = True
            staff.save()

        prepare_submission(submission, matching_start_time)
    except InsertError as err:
        write_error(str(err), 'create_submission')
        return


@celery.shared_task(ignore_result=True)
def reload_exercise_submissions(exercise_id, submissions_api_url, progress_cache_key=None):
    """
    Fetch the current submission list from the API url, clear existing submissions, create new submissions,
    and match all submissions.

    ``progress_cache_key``, if given, receives per-submission progress so a
    course-wide refresh can show what the currently reloading exercise is doing.
    """
    exercise = Exercise.objects.get(pk=exercise_id)

    def report(done, total):
        if not progress_cache_key:
            return
        try:
            caches["course_report_progress"].set(
                progress_cache_key,
                {"phase": "reloading", "submissions_done": done, "submissions_total": total},
                60 * 60,
            )
        except Exception:
            logger.warning("Failed to persist refresh progress", exc_info=True)

    api_client = aplus.get_api_client(exercise.course)
    submissions_data = api_client.load_data(submissions_api_url)
    if submissions_data is None:
        # raise ProviderTaskError("Invalid submissions data returned from %s for exercise %s:
        # expected an iterable but got None" % (submissions_api_url, exercise))
        write_error(
            "Invalid submissions data returned from %s for exercise %s: expected an iterable but got None"
            % (submissions_api_url, exercise),
            "reload_exercise_submissions",
        )
        return
    # We got new submissions data from the provider, delete all current submissions to this exercise
    exercise.submissions.all().delete()
    # Overwrite timestamp for new matching task
    exercise.touch_all_timestamps()
    # Create every submission and set timestamp
    submissions_data = list(submissions_data)
    total = len(submissions_data)
    for done, submission in enumerate(submissions_data, start=1):
        create_submission(
            submission["id"],
            exercise.course.key,
            submission["url"],
            exercise.matching_start_time,
        )
        report(done, total)
    # All submissions created, now match them
    if not DEBUG or CELERY_DEBUG:
        matcher_tasks.match_all_new_submissions_to_exercise.delay(exercise_id)


@celery.shared_task
def get_full_course_config(api_user_id, course_id, has_radar_config=True):
    """
    Perform full traversal of the exercises list of a course in the A+ API.
    The API access token of a RadarUser with the given id will be used for access.
    If has_radar_config is given and False, all submittable exercises will be retireved.
    Else, only exercises defined with Radar configuration data will be retrieved.
    """
    result = {}
    course = Course.objects.get(pk=course_id)
    client = aplus.get_api_client(course.namespace)

    try:
        if client is None:
            raise APIAuthException
        response = client.load_data(course.url)
        if response is None:
            raise APIAuthException
        exercises = response.get("exercises", [])
    except APIAuthException:
        exercises = []
        result.setdefault("errors", []).append(
            "This user does not have correct credentials to use the API of %s"
            % repr(course)
        )

    if not exercises:
        result.setdefault("errors", []).append(
            "No exercises found for %s" % repr(course)
        )

    if has_radar_config:
        # Exercise API data is expected to contain Radar configurations
        # Partition all radar configs into unseen and existing exercises
        new_exercises, old_exercises = [], []
        for radar_config in aplus.leafs_with_radar_config(exercises, course):
            radar_config["template_source"] = radar_config["get_template_source"]()
            # We got the template and lambdas are not serializable so we delete the getter
            del radar_config["get_template_source"]
            if course.has_exercise(radar_config["exercise_key"]):
                old_exercises.append(radar_config)
            else:
                new_exercises.append(radar_config)
        result["exercises"] = {
            "old": old_exercises,
            "new": new_exercises,
            "new_json": json.dumps(new_exercises),
        }
    else:
        # Exercise API data is not expected to contain Radar data,
        # choose all submittable exercises and patch them with a default Radar config
        new_exercises = []
        # Note that the type of 'exercise' is AplusApiDict
        for exercise in aplus.submittable_exercises(exercises):
            # Avoid overwriting exercise_info if it is defined
            patched_exercise_info = dict(
                exercise["exercise_info"] or {},
                radar={"tokenizer": "skip", "minimum_match_tokens": 15},
            )
            exercise.add_data({"exercise_info": patched_exercise_info})
            radar_config = aplus.get_radar_config(exercise, course)
            if radar_config:
                radar_config["template_source"] = radar_config["get_template_source"]()
                del radar_config["get_template_source"]
                new_exercises.append(radar_config)
        result["exercises"] = {
            "new": new_exercises,
            "tokenizer_choices": settings.TOKENIZER_CHOICES,
        }

    return result


@celery.shared_task(
    bind=True,
    name="provider.tasks.refresh_course_submissions_task",
    soft_time_limit=55 * 60,
    time_limit=60 * 60,
)
def refresh_course_submissions_task(self, course_key):
    """Re-fetch every exercise's submissions from the provider, reporting
    per-exercise progress to the cache so the UI can poll it."""
    course = Course.objects.get(key=course_key)
    p_config = config_loaders.provider_config(course.provider)
    full_reload = config_loaders.configured_function(p_config, "full_reload")
    exercises = list(course.exercises.all())
    total = len(exercises)
    cache_key = refresh_progress_cache_key(self.request.id)

    def report(**payload):
        try:
            caches["course_report_progress"].set(cache_key, payload, 60 * 60)
        except Exception:
            logger.warning("Failed to persist refresh progress", exc_info=True)

    report(phase="started", exercises_done=0, exercises_total=total)
    failed = []
    for index, exercise in enumerate(exercises, start=1):
        report(
            phase="reloading",
            current_exercise=exercise.name,
            current_exercise_key=exercise.key,
            exercises_done=index - 1,
            exercises_total=total,
        )
        try:
            full_reload(exercise, p_config, progress_cache_key=cache_key)
        except Exception as exc:
            logger.warning("Failed to reload exercise %s: %s", exercise.key, exc)
            failed.append({"key": exercise.key, "name": exercise.name, "error": str(exc)})
    report(
        phase="complete",
        exercises_done=total,
        exercises_total=total,
        exercises_failed=failed,
    )


@celery.shared_task(ignore_result=True)
def recompare_all_unmatched(course_id):
    course = Course.objects.get(pk=course_id)
    p_config = config_loaders.provider_config(course.provider)
    recompare = config_loaders.configured_function(p_config, "recompare")
    for exercise in course.exercises_with_unmatched_submissions:
        recompare(exercise, p_config)


@celery.shared_task(ignore_result=True)
def recompare_all(course_id):
    course = Course.objects.get(pk=course_id)
    p_config = config_loaders.provider_config(course.provider)
    recompare = config_loaders.configured_function(p_config, "recompare")
    for exercise in course.exercises.all():
        if exercise.valid_submissions.count() == 0:
            continue
        recompare(exercise, p_config)


@celery.shared_task(ignore_result=True)
def task_error_handler(task_id, *args, **kwargs):
    write_error("Failed celery task {}".format(task_id), "task_error_handler")


def write_error(message, namespace):
    logger.error(message)
    TaskError(package="provider", namespace=namespace, error_string=message).save()


# Check if any of the submitters is a staff member
def check_if_staff(data, course):
    is_staff = False

    # Check if any group submission submitters are staff
    for submitter in data["submitters"]:
        # Get the user data from the API
        try:
            api_client = aplus.get_api_client(course)
            submitter_data = api_client.load_data(submitter["url"])
            del api_client
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.ReadTimeout,
        ):
            logger.exception("Unable to read data from the API.")
            continue

        # Check if the user is a staff member for this course
        for course_data in submitter_data["staff_courses"]:
            if course_data["id"] == course.api_id:
                is_staff = True
                break

        if is_staff:
            break

    return is_staff


# Dolos poll interval while waiting for it to finish analysing an uploaded
# dataset (see _wait_for_dolos_report). Frequent enough for timely progress
# updates without hammering the Dolos API.
DOLOS_REPORT_POLL_SECONDS = 3


def _wait_for_dolos_report(report_id, report_progress):
    """Block until Dolos finishes analysing ``report_id`` (or fails).

    Dolos's report status moves queued -> running -> finished (or ->
    failed/error). There's no push notification for this, so poll GET
    /reports/:id. A stuck analysis is bounded by this task's own soft/hard
    time limits: SoftTimeLimitExceeded fires through time.sleep() below just
    like anywhere else in the task, so this can't hang forever.

    Returns ``(status, detail)``: ``status`` is the terminal status string
    ("finished", "failed", "error" or "purged"); ``detail`` is a short
    human-readable reason pulled from Dolos's own report data (its ``error``
    and ``exit_status`` fields, e.g. "out-of-memory (exit status 137)") when
    the report failed, or ``None`` otherwise. Transient polling errors are
    logged and retried rather than failing the whole report.
    """
    status_url = "%s/reports/%s" % (DOLOS_API_SERVER_URL, report_id)
    last_status = "queued"
    last_detail = None
    elapsed = 0
    while True:
        try:
            response = requests.get(status_url, timeout=30)
            response.raise_for_status()
            data = response.json()
            last_status = data.get("status") or last_status
            if last_status in ("failed", "error"):
                dolos_error = data.get("error")
                exit_status = data.get("exit_status")
                if dolos_error and exit_status not in (None, 0):
                    last_detail = "%s (exit status %s)" % (dolos_error, exit_status)
                else:
                    last_detail = dolos_error or (
                        "exit status %s" % exit_status if exit_status not in (None, 0) else None
                    )
        except requests.RequestException as exc:
            logger.warning("Transient error polling Dolos report %s status", report_id, exc_info=True)
            if last_status in ("failed", "error"):
                last_detail = last_detail or str(exc)
        else:
            if last_status in ("finished", "failed", "error", "purged"):
                return last_status, last_detail
        time.sleep(DOLOS_REPORT_POLL_SECONDS)
        elapsed += DOLOS_REPORT_POLL_SECONDS
        report_progress(
            phase="analyzing",
            dolos_status=last_status, analyzing_seconds=elapsed,
        )


def _exercise_submissions(exercise, include_all=False):
    """Return submissions for an exercise with the configured staff filter."""
    submissions = exercise.valid_submissions if include_all else exercise.best_submissions
    if not exercise.use_staff_submissions:
        submissions = submissions.exclude(student__is_staff=True)
    return submissions.select_related("student", "exercise__course")


def _build_exercise_dolos_report(exercise, include_all=False, report_progress=None):
    """Build, upload and wait for a Dolos report for one exercise.

    Returns a dict with the report metadata used by both exercise-level and
    course-level tasks.
    """
    if report_progress is None:
        def report_progress(**_payload):
            return None

    get_submission_text = _make_get_text_for_course(exercise.course)

    report_progress(phase="collecting", exercise_key=exercise.key)

    submissions = list(_exercise_submissions(exercise, include_all=include_all))
    if not submissions:
        raise CourseReportError(
            "No submissions found for exercise %s in course %s."
            % (exercise.name, exercise.course.name)
        )

    report_progress(phase="fetching", exercise_key=exercise.key, total=len(submissions))

    work_dir = tempfile.mkdtemp(prefix="dolos_exercise_")
    zip_fd, zip_path = tempfile.mkstemp(suffix=".zip")
    os.close(zip_fd)

    try:
        def _safe_text(submission):
            text = get_submission_text(submission)
            return text if text else None

        rows, skipped = write_submission_files(
            work_dir,
            submissions,
            label_fn=lambda _submission: exercise.name,
            get_text=_safe_text,
        )

        if len(rows) < 2:
            if skipped and not rows:
                raise CourseReportError(
                    "Only 0 submission(s) for exercise %s -- need at least 2 to compare. "
                    "All %d candidate submission(s) were skipped because source text could not be fetched."
                    % (exercise.name, skipped)
                )
            if skipped:
                raise CourseReportError(
                    "Only %d submission(s) for exercise %s -- need at least 2 to compare. "
                    "%d candidate submission(s) were skipped because source text could not be fetched."
                    % (len(rows), exercise.name, skipped)
                )
            raise CourseReportError(
                "Only %d submission(s) for exercise %s -- need at least 2 to compare."
                % (len(rows), exercise.name)
            )

        report_progress(phase="packaging", exercise_key=exercise.key, total=len(rows))
        write_info_csv(work_dir, rows)
        zip_dataset(work_dir, zip_path)

        report_progress(phase="uploading", exercise_key=exercise.key)

        stamp = datetime.datetime.now(pytz.timezone("Europe/Helsinki"))
        name = "%s | %s - %s" % (
            exercise.course.name,
            exercise.name,
            stamp.strftime("Day: %Y-%m-%d - Time: %H.%M.%S"),
        )
        language = dolos_language(exercise.course.tokenizer)

        try:
            with open(zip_path, "rb") as zip_file:
                response = requests.post(
                    DOLOS_API_SERVER_URL + "/reports",
                    files={"dataset[zipfile]": zip_file},
                    data={
                        "dataset[name]": name,
                        "dataset[programming_language]": language,
                    },
                    timeout=1800,
                )
                response.raise_for_status()
        except requests.RequestException as exc:
            raise CourseReportError(
                "Could not upload exercise %s to Dolos: %s" % (exercise.name, exc)
            ) from exc

        report_id = response.json().get("id")
        if not report_id:
            raise CourseReportError(
                "Dolos accepted the dataset but returned no report id for %s."
                % exercise.name
            )

        report_progress(phase="analyzing", exercise_key=exercise.key, dolos_status="queued")

        dolos_status, dolos_detail = _wait_for_dolos_report(report_id, report_progress)
        if dolos_status in ("failed", "error", "purged"):
            detail = " (%s)" % dolos_detail if dolos_detail else ""
            raise CourseReportError(
                "Dolos failed to analyse exercise %s (report %s, status: %s)%s."
                % (exercise.name, report_id, dolos_status, detail)
            )

        logger.info(
            "Exercise report %s ready for %s (%d submissions, %d skipped)",
            report_id, exercise.name, len(rows), skipped,
        )

        return {
            "exercise_key": exercise.key,
            "exercise_name": exercise.name,
            "report_id": report_id,
            "submissions_included": len(rows),
            "submissions_skipped": skipped,
            "include_all_used": include_all,
        }
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
        if os.path.exists(zip_path):
            os.remove(zip_path)


@celery.shared_task(
    bind=True,
    name="provider.tasks.generate_exercise_dolos_task",
    soft_time_limit=15 * 60,
    time_limit=20 * 60,
)
def generate_exercise_dolos_task(self, exercise_id, include_all=False):
    """
    Generate a Dolos report for a single exercise.

    This is the building block for course-wide reports: instead of one giant
    dataset that can OOM, we generate one report per exercise and combine
    them afterward.

    Args:
        exercise_id: The database ID of the exercise (not the key, to avoid
                     duplicate key issues).

    Returns:
        {
            "exercise_key": str,
            "exercise_name": str,
            "report_id": str,
            "submissions_included": int,
            "submissions_skipped": int,
        }

    Raises:
        CourseReportError: if the exercise has no submissions or Dolos fails.
    """
    exercise = Exercise.objects.select_related("course").get(id=exercise_id)
    logger.info("Generating Dolos report for exercise %s (%s)", exercise.key, exercise.name)

    progress_cache_key = "exercise_progress:%s:%s" % (self.request.id, exercise.key)

    def report_progress(**payload):
        try:
            caches["course_report_progress"].set(progress_cache_key, payload, 60 * 60)
        except Exception:
            logger.warning("Failed to persist exercise progress for %s", exercise.key, exc_info=True)
        try:
            self.update_state(state="PROGRESS", meta=payload)
        except Exception:
            logger.warning("Failed to update task state for exercise %s", exercise.key, exc_info=True)

    try:
        return _build_exercise_dolos_report(
            exercise,
            include_all=include_all,
            report_progress=report_progress,
        )

    except CourseReportError:
        raise
    except SoftTimeLimitExceeded as exc:
        raise CourseReportError(
            "Report generation for %s timed out after %d minutes."
            % (exercise.name, self.request.timelimit[0] // 60 if self.request.timelimit else 15)
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error generating report for exercise %s", exercise.key)
        raise CourseReportError("Unexpected error for %s: %s" % (exercise.name, exc)) from exc
def _make_course_report_progress_callback(
    report_progress,
    exercise_name,
    exercise_key,
    exercises_done,
    exercises_total,
    exercises_remaining,
):
    """Return a callback that reports progress for one exercise."""

    def progress_callback(**payload):
        report_progress(
            current_exercise=exercise_name,
            current_exercise_key=exercise_key,
            exercises_done=exercises_done,
            exercises_total=exercises_total,
            exercises_remaining=exercises_remaining,
            **payload,
        )

    return progress_callback


def _report_course_progress(task, progress_cache_key, **payload):
    try:
        caches["course_report_progress"].set(progress_cache_key, payload, 60 * 60)
    except Exception:
        logger.warning("Failed to persist course report progress", exc_info=True)
    try:
        task.update_state(state="PROGRESS", meta=payload)
    except Exception:
        logger.warning("Failed to update task state for course report progress", exc_info=True)


@celery.shared_task(
    bind=True,
    name="provider.tasks.generate_course_dolos_task",
    soft_time_limit=25 * 60,
    time_limit=30 * 60,
)
def generate_course_dolos_task(self, course_key, force=False):
    """
    Generate course-wide Dolos report by analyzing each exercise separately
    and combining the results.

    This approach avoids OOM issues by keeping each dataset small.
    Returns a list of per-exercise report results.
    """
    course = Course.objects.get(key=course_key)
    logger.info("Starting per-exercise course-wide Dolos report for %s", course.name)

    progress_cache_key = course_progress_cache_key(self.request.id)

    def report_progress(**payload):
        _report_course_progress(self, progress_cache_key, **payload)

    exercises = _deduplicate_exercises(course.exercises.select_related("course").all())
    total_exercises = len(exercises)
    if total_exercises == 0:
        raise CourseReportError("%s has no exercises configured." % course.name)

    report_results = []
    failed_exercises = []

    try:
        report_progress(
            phase="collecting",
            current_exercise=None,
            exercises_done=0,
            exercises_total=total_exercises,
        )

        for index, exercise in enumerate(exercises, start=1):
            remaining = total_exercises - index + 1
            report_progress(
                phase="processing",
                current_exercise=exercise.name,
                current_exercise_key=exercise.key,
                exercises_done=index - 1,
                exercises_total=total_exercises,
                exercises_remaining=remaining,
            )

            try:
                include_all = _should_include_all_submissions(exercise)
                stored_report = None
                if not force:
                    stored_report = ExerciseDolosReport.objects.filter(
                        exercise=exercise, include_all=include_all
                    ).first()
                if stored_report:
                    exercise_result = {
                        "exercise_key": exercise.key,
                        "exercise_name": exercise.name,
                        "report_id": stored_report.report_id,
                        "submissions_included": stored_report.submissions_included,
                        "submissions_skipped": 0,
                        "include_all_used": include_all,
                        "reused": True,
                    }
                else:
                    progress_callback = _make_course_report_progress_callback(
                        report_progress,
                        exercise.name,
                        exercise.key,
                        index - 1,
                        total_exercises,
                        remaining,
                    )
                    exercise_result = _build_exercise_dolos_report(
                        exercise,
                        include_all=include_all,
                        report_progress=progress_callback,
                    )
                    ExerciseDolosReport.objects.update_or_create(
                        exercise=exercise,
                        include_all=include_all,
                        defaults={
                            "report_id": exercise_result["report_id"],
                            "submissions_included": exercise_result["submissions_included"],
                        },
                    )
                    exercise_result["reused"] = False
                report_results.append(exercise_result)
                logger.info("Completed exercise %s/%s: %s", index, total_exercises, exercise.key)
            except Exception as exc:
                logger.warning("Failed to process exercise %s: %s", exercise.key, exc)
                failed_exercises.append({
                    "key": exercise.key,
                    "name": exercise.name,
                    "error": str(exc),
                })

        report_progress(
            phase="complete",
            exercises_done=total_exercises,
            exercises_total=total_exercises,
            report_ids=[r["report_id"] for r in report_results],
        )

        final_result = {
            "report_ids": [r["report_id"] for r in report_results],
            "exercises_processed": len(report_results),
            "exercises_total": total_exercises,
            "exercises_failed": failed_exercises,
            "submissions_total": sum(r["submissions_included"] for r in report_results),
            "reports_reused": sum(1 for r in report_results if r["reused"]),
            "reports_generated": sum(1 for r in report_results if not r["reused"]),
        }
        try:
            caches["course_report_progress"].set(
                course_progress_cache_key(self.request.id),
                final_result,
                60 * 60,
            )
        except Exception:
            logger.warning("Failed to persist final course report payload", exc_info=True)
        return final_result

    except CourseReportError:
        raise
    except SoftTimeLimitExceeded as exc:
        raise CourseReportError(
            "Course-wide report generation timed out after %d minutes."
            % (self.request.timelimit[0] // 60 if self.request.timelimit else 25)
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error generating course-wide report for %s", course_key)
        raise CourseReportError("Unexpected error: %s" % exc) from exc


def _deduplicate_exercises(exercises):
    """Return exercises without duplicate IDs while preserving order."""
    seen_ids = set()
    unique_exercises = []
    for exercise in exercises:
        if exercise.id in seen_ids:
            continue
        seen_ids.add(exercise.id)
        unique_exercises.append(exercise)
    return unique_exercises


def _should_include_all_submissions(exercise):
    """Decide whether to include all submissions for an exercise."""
    best_count = _exercise_submissions(exercise, include_all=False).count()
    all_count = _exercise_submissions(exercise, include_all=True).count()
    if best_count < 2:
        return all_count >= 2
    return False


def _make_get_text_for_course(course):
    """Return a closure that fetches submission text via provider config."""
    p_config = config_loaders.provider_config(course.provider)
    get_submission_text = config_loaders.configured_function(
        p_config, "get_submission_text"
    )

    def get_text(submission):
        return get_submission_text(submission, p_config) or ""

    return get_text
