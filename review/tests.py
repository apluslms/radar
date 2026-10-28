from types import SimpleNamespace
from unittest.mock import Mock, call, patch
from datetime import timedelta
import time

import requests
from aplus_client.django.models import ApiNamespace
from django.contrib.auth import get_user_model
from django.core.cache import caches
from django.db import connection, OperationalError
from django.template.loader import render_to_string
from django.test import Client, RequestFactory, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils.timezone import now

from data.models import Comparison, Course, Exercise, ExerciseDolosReport, Student, Submission
from provider import aplus
from provider.tasks import load_radar_page_data
from review import views
from review.decorators import database_timeout
from review.background import background_result, result_key, store_background_state


@override_settings(
    CHEATERSHEET_WEB_SERVER_URL="http://cheatersheet.test",
    CHEATERSHEET_API_TOKEN="secret",
)
class CreateCheatersheetComparisonTests(TestCase):
    @override_settings(CACHES={
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "refresh-locks"},
        "course_report_progress": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "refresh-results",
        },
    })
    @patch("provider.tasks.load_radar_page_data.apply_async")
    @patch("provider.aplus.AplusTokenClient")
    @patch("provider.aplus.get_api_client")
    def test_course_home_refresh_updates_metadata_in_worker_and_preserves_submissions(
        self, get_client, client_class, enqueue,
    ):
        caches["default"].clear()
        caches["course_report_progress"].clear()
        session = self.client.session
        session["legacy_radar"] = False
        session.save()
        self.exercise.override_minimum_match_tokens = 37
        self.exercise.save()
        student_b = self.course.students.get(key="studentB")
        student_b.name = "Keep Bob"
        student_b.save(update_fields=["name"])
        url = reverse("course_home", kwargs={"course_key": self.course.key})
        response = self.client.post(url + "?all=1&students_page=1", {"refresh_metadata": "1"})
        self.assertRedirects(response, url + "?all=1&students_page=1")
        get_client.assert_not_called()
        enqueue.assert_not_called()
        poll_url = url + "?all=1&students_page=1&background=1"
        self.assertEqual(self.client.post(poll_url).json()["status"], "pending")

        def load_data(url, skip_cache=False):
            if url == self.course.url:
                return {"exercises": [
                    {"id": "ex1", "display_name": "Changed provider name", "is_submittable": True},
                    {"id": "ex2", "display_name": "New exercise", "is_submittable": True},
                ]}
            return [
                {"student_id": "studentA", "full_name": "Updated Alice"},
                {"student_id": "studentB", "full_name": "No Name"},
                {"student_id": "studentC", "full_name": "New Student"},
            ]

        client_class.return_value.load_data.side_effect = load_data
        load_radar_page_data.run(*enqueue.call_args.kwargs["args"])
        self.assertEqual(self.client.get(poll_url).json()["status"], "ready")
        self.assertEqual(client_class.call_count, 2)
        self.assertEqual(client_class.return_value.load_data.call_count, 2)
        for call in client_class.return_value.load_data.call_args_list:
            self.assertTrue(call.kwargs["skip_cache"])
        self.exercise.refresh_from_db()
        self.assertEqual(self.exercise.name, "Exercise 1")
        self.assertEqual(self.exercise.override_minimum_match_tokens, 37)
        self.assertTrue(self.course.exercises.filter(key="ex2").exists())
        self.assertEqual(self.course.students.get(key="studentA").name, "Updated Alice")
        self.assertEqual(self.course.students.get(key="studentB").name, "Keep Bob")
        self.assertTrue(self.course.students.filter(key="studentC").exists())
        self.assertEqual(self.course.submissions.count(), 2)
        self.assertIsNone(caches["default"].get("course_home_refresh:%s" % self.course.pk))
        self.assertContains(self.client.get(url + "?all=1&students_page=1"), "Refresh roster and exercises")
        caches["default"].clear()
        caches["course_report_progress"].clear()

    @override_settings(CACHES={
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "metadata-locks"},
        "course_report_progress": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "metadata-results",
        },
    })
    @patch("provider.aplus.get_api_client")
    def test_course_home_worker_imports_missing_metadata_without_legacy_setup(self, get_client):
        self.course.exercises.all().delete()
        self.course.students.all().delete()
        get_client.return_value.load_data.side_effect = [
            {"exercises": [{"exercises": [
                {"id": 71, "display_name": "New Exercise", "is_submittable": True},
                {"id": 72, "display_name": "Reading", "is_submittable": False},
            ]}]},
            [
                {"student_id": "12345", "full_name": "Alice Example"},
                {"student_id": None, "username": "bob", "full_name": "No Name"},
                {"student_id": None, "username": None, "full_name": "No Identifier"},
            ],
        ]
        session = self.client.session
        session["legacy_radar"] = False
        session.save()
        response = self.client.get(reverse("course_home", kwargs={"course_key": self.course.key}))
        self.assertEqual(response.status_code, 200)
        get_client.assert_not_called()

        with self.assertLogs("provider.tasks", level="INFO") as task_logs:
            load_radar_page_data.run(self.course.pk, "course_home", [False, 1, "initial"], "metadata-test")
        self.assertTrue(any("Radar course-home metadata ready" in message for message in task_logs.output))
        self.assertTrue(any("Radar course-home data ready" in message for message in task_logs.output))
        state = caches["course_report_progress"].get("metadata-test")
        self.assertEqual(state["status"], "ready")
        self.assertEqual([exercise.key for exercise in state["result"]["exercises"]], ["71"])
        self.assertEqual(self.course.students.count(), 2)
        self.assertEqual(Submission.objects.filter(exercise__course=self.course).count(), 0)
        exercise = self.course.exercises.get(key="71")
        self.assertEqual(exercise.name, "New Exercise")
        self.assertEqual(self.course.students.get(key="12345").name, "Alice Example")
        self.assertEqual(self.course.students.get(key="bob").name, "")
        exercise.name = "Locally configured name"
        exercise.override_minimum_match_tokens = 37
        exercise.save()
        get_client.return_value.load_data.reset_mock()
        aplus.import_missing_course_metadata(self.course)
        get_client.return_value.load_data.assert_not_called()
        exercise.refresh_from_db()
        self.assertEqual(exercise.name, "Locally configured name")
        self.assertEqual(exercise.override_minimum_match_tokens, 37)
        self.assertEqual(self.course.students.count(), 2)
        caches["course_report_progress"].delete("metadata-test")

    @patch("provider.aplus.get_api_client")
    def test_course_metadata_import_skips_filesystem_and_reports_provider_failure(self, get_client):
        self.course.provider = "filesystem"
        aplus.import_missing_course_metadata(self.course)
        get_client.assert_not_called()
        self.course.provider = "a+"
        self.course.exercises.all().delete()
        get_client.return_value.load_data.return_value = None
        with self.assertRaises(aplus.AplusProviderError):
            aplus.import_missing_course_metadata(self.course)
        self.assertFalse(self.course.exercises.exists())

    def setUp(self):
        user = get_user_model().objects.create_user("reviewer", password="password")
        self.user = user
        namespace = ApiNamespace.objects.create(domain="https://plus.test")
        self.course = Course(
            api_id=42,
            url="https://plus.test/courses/42/",
            namespace=namespace,
            key="course42",
            name="Course 42",
        )
        self.course.save()
        self.course.reviewers.add(user)
        self.exercise = Exercise.objects.create(course=self.course, key="ex1", name="Exercise 1")
        student_a = Student.objects.create(course=self.course, key="studentA")
        student_b = Student.objects.create(course=self.course, key="studentB")
        self.submission_a = Submission.objects.create(
            key="radarA",
            aplus_key="providerA",
            exercise=self.exercise,
            student=student_a,
        )
        self.submission_b = Submission.objects.create(
            key="radarB",
            aplus_key="providerB",
            exercise=self.exercise,
            student=student_b,
        )
        self.client.force_login(user)

    def test_dolos_toolbar_uses_reversible_url_sentinels(self):
        html = render_to_string(
            "review/_dolos_cheatersheet_toolbar.html",
            {"course": self.course},
        )

        self.assertIn(
            "/course42/dolos_hub/cheatersheet/report/REPORT_ID/0/",
            html,
        )

    @override_settings(CACHES={
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
        "course_report_progress": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "async-test",
        },
    })
    @patch("provider.tasks.load_radar_page_data.apply_async")
    @patch("review.views._student_exercise_matches")
    def test_background_page_load_queue_poll_and_worker_result(self, matches, enqueue):
        store = caches["course_report_progress"]
        store.clear()
        session = self.client.session
        session["legacy_radar"] = False
        session.save()
        url = reverse("student_hub", kwargs={"course_key": self.course.key, "student_key": "studentA"})

        response = self.client.get(url)
        self.assertContains(response, "Loading report data")
        matches.assert_not_called()
        enqueue.assert_not_called()
        self.assertEqual(self.client.get(url + "?background=1").json()["status"], "idle")
        self.assertEqual(self.client.post(url + "?background=1").json()["status"], "pending")
        self.client.post(url + "?background=1")
        self.client.get(url + "?background=1")
        enqueue.assert_called_once()
        self.assertEqual(enqueue.call_args.kwargs["queue"], "radar_background")
        matches.assert_not_called()

        matches.return_value = [(self.exercise, "REPORT", ("studentB", 0.8), [("studentB", 0.8)])]
        load_radar_page_data.run(*enqueue.call_args.kwargs["args"])
        self.assertEqual(self.client.get(url + "?background=1").json(), {"status": "ready"})
        response = self.client.get(url)
        self.assertContains(response, "80")
        self.assertNotContains(response, "data-background-loading")
        matches.assert_called_once()
        store.clear()

    @override_settings(CACHES={
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "summary-roster-locks"},
        "course_report_progress": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "summary-roster-results",
        },
    })
    @patch("provider.aplus.sync_student_names")
    @patch("review.views._build_course_similarity_summary", return_value={"pairs": []})
    def test_summary_worker_uses_stored_roster_without_refreshing_provider(self, build_summary, sync_roster):
        caches["default"].clear()
        caches["course_report_progress"].clear()
        load_radar_page_data.run(self.course.pk, "summary", [[], 0.83, 1], "summary-roster-test")

        sync_roster.assert_not_called()
        build_summary.assert_called_once_with(self.course, [], 0.83, 1)
        self.assertEqual(
            caches["course_report_progress"].get("summary-roster-test"),
            {"status": "ready", "result": {"pairs": []}},
        )
        caches["default"].clear()
        caches["course_report_progress"].clear()

    @override_settings(CACHES={
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
        "course_report_progress": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "async-failure-test",
        },
    })
    @patch("provider.tasks.load_radar_page_data.apply_async", side_effect=RuntimeError("broker down"))
    def test_background_queue_failure_and_stale_job_can_be_retried(self, enqueue):
        store = caches["course_report_progress"]
        store.clear()
        session = self.client.session
        session["legacy_radar"] = False
        session.save()
        url = reverse(
            "student_hub", kwargs={"course_key": self.course.key, "student_key": "studentA"},
        ) + "?background=1"
        with self.assertLogs("radar.review", level="ERROR"):
            self.assertEqual(self.client.post(url).json()["status"], "failed")
        self.client.get(url)
        enqueue.assert_called_once()
        key = result_key(self.course.pk, "student_matches", [["studentA", False, []], ""])
        store_background_state(store, key, {"status": "pending", "started": time.time() - 700}, 900)
        self.assertEqual(self.client.get(url).json()["status"], "failed")
        enqueue.side_effect = None
        self.assertEqual(self.client.post(url, {"retry": "1"}).json()["status"], "pending")
        store.clear()

    @patch("review.views._fetch_dolos_pairs_rows", side_effect=AssertionError("Network in page request"))
    @patch("review.views._generate_dolos_report", side_effect=AssertionError("Generation in page request"))
    @patch("provider.aplus.sync_student_names", side_effect=AssertionError("Roster in page request"))
    def test_new_radar_initial_pages_do_not_fetch_or_generate_reports(self, roster, generate, fetch):
        session = self.client.session
        session["legacy_radar"] = False
        session.save()
        ExerciseDolosReport.objects.create(exercise=self.exercise, include_all=False, report_id="ASYNC_REPORT")
        Student.objects.create(course=self.course, key="studentC")
        urls = [
            reverse("index"),
            reverse("course_home", kwargs={"course_key": self.course.key}),
            reverse("students_hub", kwargs={"course_key": self.course.key}),
            reverse("student_hub", kwargs={"course_key": self.course.key, "student_key": "studentA"}),
            reverse(
                "student_pair_hub",
                kwargs={"course_key": self.course.key, "a_key": "studentA", "b_key": "studentB"},
            ),
            reverse(
                "student_group_hub",
                kwargs={"course_key": self.course.key, "member_keys": "studentA-studentB-studentC"},
            ),
            reverse("dolos_mini_comparison", kwargs={
                "course_key": self.course.key, "a_key": "studentA", "b_key": "studentB",
                "exercise_key": self.exercise.key,
                "left_submission_id": self.submission_a.pk, "right_submission_id": self.submission_b.pk,
            }),
            reverse("dolos_hub_exercise", kwargs={"course_key": self.course.key, "exercise_key": self.exercise.key}),
        ]
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            if url != reverse("index") and url != reverse("course_home", kwargs={"course_key": self.course.key}):
                self.assertContains(response, "Regenerate course reports")
        fetch.assert_not_called()
        generate.assert_not_called()
        roster.assert_not_called()

    @patch("provider.tasks.load_radar_page_data.apply_async")
    def test_background_enqueue_requires_csrf_and_course_access(self, enqueue):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        session = client.session
        session["legacy_radar"] = False
        session.save()
        url = reverse(
            "student_hub", kwargs={"course_key": self.course.key, "student_key": "studentA"},
        ) + "?background=1"
        self.assertEqual(client.post(url).status_code, 403)
        client.logout()
        self.assertEqual(client.post(url).status_code, 403)
        outsider = get_user_model().objects.create_user("outsider")
        self.client.force_login(outsider)
        with self.assertRaises(PermissionError):
            self.client.post(url)
        enqueue.assert_not_called()

    @override_settings(CACHES={
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
        "course_report_progress": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "async-worker-error-test",
        },
    })
    @patch("review.views._fetch_dolos_pairs_rows", side_effect=requests.ConnectionError("Dolos unavailable"))
    def test_background_worker_failure_is_not_an_empty_success(self, fetch):
        store = caches["course_report_progress"]
        with self.assertLogs("provider.tasks", level="ERROR"):
            load_radar_page_data.run(
                self.course.pk, "student_matches", ["studentA", False, ["REPORT"]], "worker-error",
            )
        self.assertEqual(store.get("worker-error")["status"], "failed")
        store.delete("worker-error")

    @override_settings(CACHES={
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "mini-report-locks"},
        "course_report_progress": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "mini-report-results",
        },
    })
    @patch("review.views._generate_dolos_report")
    def test_mini_report_worker_handles_success_missing_submissions_and_empty_report(self, generate):
        store = caches["course_report_progress"]
        arguments = [self.exercise.pk, self.submission_a.pk, self.submission_b.pk]
        key = "mini-report-test"
        self.addCleanup(store.delete, key)
        self.addCleanup(caches["default"].delete, key + ":lock")
        generate.return_value = "MINI_REPORT"
        caches["default"].set(key + ":lock", True)

        load_radar_page_data.run(self.course.pk, "mini_report", arguments, key)

        self.assertEqual(store.get(key), {"status": "ready", "result": "MINI_REPORT"})
        self.assertIsNone(caches["default"].get(key + ":lock"))
        submissions = generate.call_args.args[0]
        self.assertEqual({submission.pk for submission in submissions}, {arguments[1], arguments[2]})
        label = generate.call_args.kwargs["label_fn"]
        self.assertEqual(label(self.submission_a), self.submission_a.student.display_name)

        generate.return_value = None
        with self.assertLogs("provider.tasks", level="ERROR"):
            load_radar_page_data.run(self.course.pk, "mini_report", arguments, key)
        self.assertEqual(store.get(key)["status"], "failed")

        generate.reset_mock()
        with self.assertLogs("provider.tasks", level="ERROR"):
            load_radar_page_data.run(
                self.course.pk, "mini_report", [self.exercise.pk, self.submission_a.pk, -1], key,
            )
        self.assertEqual(store.get(key)["status"], "failed")
        generate.assert_not_called()

    @override_settings(CACHES={
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "missing-report-locks"},
        "course_report_progress": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "missing-report-results",
        },
    })
    @patch("review.views._fetch_dolos_pairs_rows")
    def test_missing_dolos_report_suggests_regenerating_course_report(self, fetch):
        fetch.side_effect = requests.HTTPError(response=Mock(status_code=404))
        store = caches["course_report_progress"]
        with self.assertLogs("provider.tasks", level="ERROR"):
            load_radar_page_data.run(
                self.course.pk,
                "student_matches",
                ["studentA", False, ["MISSING_REPORT"]],
                "missing-report-test",
            )

        result = store.get("missing-report-test")
        self.assertEqual(result["status"], "failed")
        self.assertIn("Regenerate the full course report", result["message"])
        store.delete("missing-report-test")

    @patch("review.views.generate_course_dolos_task.delay", return_value=Mock(id="course-task"))
    def test_course_report_requests_always_force_per_exercise_reports(self, enqueue):
        response = self.client.get(
            reverse("generate_course_dolos_async", kwargs={"course_key": self.course.key})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "queued")
        enqueue.assert_called_once_with(self.course.key, force=True, include_all=False)

    @patch("review.views.generate_course_dolos_task.delay", return_value=Mock(id="all-course-task"))
    def test_course_report_regeneration_preserves_all_submissions_scope(self, enqueue):
        response = self.client.get(
            reverse("generate_course_dolos_async", kwargs={"course_key": self.course.key}) + "?all=1"
        )
        self.assertEqual(response.json()["status"], "queued")
        enqueue.assert_called_once_with(self.course.key, force=True, include_all=True)

    def test_course_report_button_preserves_selected_submission_scope(self):
        generate_url = reverse("generate_course_dolos_async", kwargs={"course_key": self.course.key})
        for include_all in (False, True):
            with self.subTest(include_all=include_all):
                html = render_to_string(
                    "review/_course_report_panel.html", {"course": self.course, "include_all": include_all},
                )
                self.assertIn('data-generate-url="%s?all=%s"' % (generate_url, int(include_all)), html)

    def test_radar_mode_selection_is_idempotent(self):
        url = reverse("toggle_radar_mode")

        first_response = self.client.post(url, {"mode": "new"})
        second_response = self.client.post(url, {"mode": "new"})

        self.assertEqual(first_response.status_code, 302)
        self.assertEqual(second_response.status_code, 302)
        self.assertFalse(self.client.session["legacy_radar"])

    def test_radar_mode_selection_rejects_unknown_mode(self):
        response = self.client.post(reverse("toggle_radar_mode"), {"mode": "unexpected"})

        self.assertEqual(response.status_code, 400)

    def test_index_counts_courses_with_bounded_queries(self):
        for index in range(3):
            course = Course(
                api_id=100 + index,
                url="https://plus.test/courses/%s/" % (100 + index),
                namespace=self.course.namespace,
                key="extra%s" % index,
                name="Extra Course %s" % index,
            )
            course.save()
            course.reviewers.add(self.user)

        session = self.client.session
        session["legacy_radar"] = False
        session.save()

        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse("index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/static/pico.min.css")
        self.assertNotContains(response, "cdn.jsdelivr.net")
        self.assertLessEqual(len(queries), 10)
        first_course = next(course for course in response.context["courses"] if course.key == self.course.key)
        self.assertEqual(first_course.home_exercise_count, 1)
        self.assertEqual(first_course.home_student_count, 2)
        self.assertEqual(first_course.home_submission_count, 2)
        self.assertEqual(first_course.home_matched_count, 0)

    def test_whole_course_report_url_redirects_to_course_home(self):
        session = self.client.session
        session["legacy_radar"] = False
        session.save()

        response = self.client.get(
            reverse("dolos_hub", kwargs={"course_key": self.course.key}) + "?course_report=1"
        )

        self.assertRedirects(
            response,
            reverse("course_home", kwargs={"course_key": self.course.key}),
        )

    @override_settings(CACHES={
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "overview-flags-locks"},
        "course_report_progress": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "overview-flags-results",
        },
    })
    @patch("provider.tasks.load_radar_page_data.apply_async")
    def test_new_radar_pair_flag_is_shown_in_student_overview(self, enqueue):
        caches["default"].clear()
        caches["course_report_progress"].clear()
        enqueue.side_effect = lambda args, **kwargs: load_radar_page_data.run(*args)
        session = self.client.session
        session["legacy_radar"] = False
        session.save()
        flag_url = reverse(
            "flag_new_radar_pair",
            kwargs={
                "course_key": self.course.key,
                "left_submission_id": self.submission_a.pk,
                "right_submission_id": self.submission_b.pk,
            },
        )

        response = self.client.post(flag_url, {"flagged": "true"})

        self.assertEqual(response.status_code, 302)
        comparison = Comparison.objects.get(
            submission_a=self.submission_a,
            submission_b=self.submission_b,
        )
        self.assertEqual(comparison.review, 10)
        overview_url = reverse("students_hub", kwargs={"course_key": self.course.key})
        poll_url = overview_url + "?background=1&section=flags"
        self.assertEqual(self.client.post(poll_url).json()["status"], "pending")
        first_key = enqueue.call_args.kwargs["args"][3]
        overview = self.client.get(overview_url)
        self.assertContains(overview, "Flagged Pairs and Submissions")
        self.assertContains(overview, "radarA and radarB")

        response = self.client.post(flag_url, {"flagged": "false"}, follow=True)

        self.assertEqual(response.status_code, 200)
        comparison.refresh_from_db()
        self.assertEqual(comparison.review, 0)
        self.assertContains(response, "Pair flag removed.")
        self.assertNotContains(response, "radarA and radarB")
        self.assertEqual(self.client.post(poll_url).json()["status"], "pending")
        self.assertNotEqual(enqueue.call_args.kwargs["args"][3], first_key)
        self.assertContains(self.client.get(overview_url), "No flagged pairs")

    @override_settings(CACHES={
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "home-bounds-locks"},
        "course_report_progress": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "home-bounds-results",
        },
    })
    @patch("review.views._flagged_comparisons")
    def test_course_home_bounds_lists_without_aggregate_counts(self, flagged_query):
        caches["default"].clear()
        caches["course_report_progress"].clear()

        class FlaggedRows:
            def __init__(self):
                self.requested_slice = None

            def __getitem__(self, requested_slice):
                self.requested_slice = requested_slice
                return []

        rows = FlaggedRows()
        flagged_query.return_value = rows
        for index in range(49):
            Student.objects.create(
                course=self.course,
                key="extra%02d" % index,
            )
        session = self.client.session
        session["legacy_radar"] = False
        session.save()

        response = self.client.get(reverse("course_home", kwargs={"course_key": self.course.key}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Loading report data")
        result = views._build_course_home_data(self.course, False, 1)
        self.assertNotIn("exercise_count", result)
        self.assertNotIn("student_count", result)
        self.assertNotIn("submission_count", result)
        self.assertNotIn("reports_generated", result)
        self.assertNotIn("flagged_count", result)
        self.assertEqual(rows.requested_slice.stop, 10)
        self.assertEqual(len(result["other_students"]), 50)
        self.assertTrue(result["other_students"].has_next())
        self.assertEqual(result["other_students"].paginator.count, 51)
        caches["default"].clear()
        caches["course_report_progress"].clear()

    @override_settings(CACHES={
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "home-locks"},
        "course_report_progress": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "home-results",
        },
    })
    @patch("provider.tasks.load_radar_page_data.apply_async")
    def test_course_home_renders_without_heavy_queries_even_after_worker_completion(self, enqueue):
        caches["default"].clear()
        caches["course_report_progress"].clear()
        session = self.client.session
        session["legacy_radar"] = False
        session.save()
        Comparison.objects.create(
            submission_a=self.submission_a, submission_b=self.submission_b,
            review=10, similarity=0.9,
        )
        url = reverse("course_home", kwargs={"course_key": self.course.key})
        with patch("review.views._build_course_home_data", side_effect=AssertionError("Heavy work in web request")):
            with CaptureQueriesContext(connection) as queries:
                response = self.client.get(url)
                self.assertEqual(self.client.get(url + "?background=1").json()["status"], "idle")
            self.assertContains(response, "Course 42")
            self.assertContains(response, "Loading report data")
            enqueue.assert_not_called()
            for query in queries:
                self.assertNotIn('"data_submission"', query["sql"])
                self.assertNotIn('"data_comparison"', query["sql"])
            self.assertEqual(self.client.post(url + "?background=1").json()["status"], "pending")

        load_radar_page_data.run(*enqueue.call_args.kwargs["args"])
        self.assertEqual(self.client.get(url + "?background=1").json()["status"], "ready")
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(url)
        self.assertNotIn("submission_count", response.context)
        self.assertNotIn("flagged_count", response.context)
        self.assertContains(response, "studentA and studentB")
        self.assertContains(response, "Regenerate course reports")
        for query in queries:
            self.assertNotIn('"data_submission"', query["sql"])
            self.assertNotIn('"data_comparison"', query["sql"])
        pin_url = reverse("toggle_student_pin", kwargs={"course_key": self.course.key, "student_key": "studentA"})
        self.client.post(pin_url)
        self.assertEqual(self.client.get(url + "?background=1").json()["status"], "idle")
        caches["default"].clear()
        caches["course_report_progress"].clear()

    def test_legacy_students_view_uses_student_number_when_name_is_missing(self):
        html = render_to_string(
            "review/students_view.html",
            {
                "course": self.course,
                "hierarchy": (("Radar", "/"), (self.course.name, "/course42/")),
                "exercises": {},
                "students": [
                    {
                        "key": "studentA",
                        "name": "No Name",
                        "is_staff": False,
                        "avg_similarity": "",
                        "exercises": [],
                    }
                ],
            },
        )

        self.assertIn(">studentA</a>", html)
        self.assertNotIn(">No Name</a>", html)

    def test_student_display_name_uses_student_key_for_placeholder_names(self):
        student = Student.objects.create(course=self.course, key="studentC", name=" no name ")
        self.assertEqual(student.display_name, "studentC")

        self.assertEqual(
            self.course.get_student("studentD", name="No Name").display_name,
            "studentD",
        )

    def test_dolos_hub_marks_the_enabled_submission_set(self):
        session = self.client.session
        session["legacy_radar"] = False
        session.save()
        url = reverse(
            "dolos_hub_exercise",
            kwargs={"course_key": self.course.key, "exercise_key": "ex1"},
        )

        best_response = self.client.get(url)
        self.assertContains(best_response, '<div class="hub-layout">')
        self.assertContains(best_response, '<nav class="hub-tabs">')
        self.assertContains(best_response, 'href="%s" aria-current="true"' % url)
        self.assertContains(best_response, "Best per student")
        self.assertNotContains(best_response, 'name="newest"')

        all_response = self.client.get(url + "?all=1")
        self.assertContains(all_response, 'href="%s?all=1" aria-current="true"' % url)
        self.assertContains(
            all_response,
            'href="%s?all=1"' % reverse(
                "students_hub", kwargs={"course_key": self.course.key}
            ),
        )
        self.assertContains(all_response, "All submissions")

        newest_response = self.client.get(url + "?newest=3")
        self.assertContains(
            newest_response,
            'href="%s?newest=3" aria-current="true"' % url,
        )
        self.assertContains(newest_response, '<label for="newest-count">Include</label>')
        self.assertContains(
            newest_response,
            'id="newest-count" type="number" name="newest" min="1" max="100" value="3"',
        )
        self.assertContains(newest_response, "newest submissions per student")
        self.assertContains(newest_response, "Newest per student")
        self.assertContains(newest_response, ">Apply</button>")
        self.assertContains(newest_response, "?newest=3")

    def test_course_report_waiting_panel_is_compact_and_consistent(self):
        html = render_to_string(
            "review/_course_report_panel.html",
            {
                "course": self.course,
                "course_report_task_status": {"status": "pending"},
            },
        )

        self.assertIn("Regenerate course reports", html)
        self.assertIn('class="hub-course-progress active"', html)
        self.assertNotIn("<canvas", html)

    def test_exercise_submissions_selects_n_newest_per_student(self):
        student_b = self.submission_b.student
        base_time = now()
        expected_ids = set()
        for student in (self.submission_a.student, student_b):
            for offset in range(3):
                submission = Submission.objects.create(
                    key="%s-%d" % (student.key, offset),
                    exercise=self.exercise,
                    student=student,
                    provider_submission_time=base_time + timedelta(minutes=offset),
                )
                if offset > 0:
                    expected_ids.add(submission.id)

        selected_ids = set(
            views._exercise_submissions(self.exercise, newest=2).values_list("id", flat=True)
        )

        self.assertEqual(selected_ids, expected_ids)

    @patch("review.views.background_result", return_value={"status": "pending"})
    def test_student_hub_uses_requested_submission_set(self, background):
        ExerciseDolosReport.objects.create(
            exercise=self.exercise,
            include_all=False,
            report_id="BEST_REPORT",
            submissions_included=2,
        )
        ExerciseDolosReport.objects.create(
            exercise=self.exercise,
            include_all=True,
            report_id="ALL_REPORT",
            submissions_included=2,
        )
        session = self.client.session
        session["legacy_radar"] = False
        session.save()
        url = reverse(
            "student_hub",
            kwargs={"course_key": self.course.key, "student_key": "studentA"},
        )

        best_response = self.client.get(url)
        self.assertEqual(background.call_args.args[3], ["studentA", False, ["BEST_REPORT"]])
        self.assertContains(best_response, 'href="%s" aria-current="true"' % url)

        all_response = self.client.get(url + "?all=1")
        self.assertEqual(background.call_args.args[3], ["studentA", True, ["ALL_REPORT"]])
        self.assertContains(all_response, 'href="%s?all=1" aria-current="true"' % url)

    @patch("review.views.background_result", return_value={"status": "pending"})
    def test_students_overview_does_not_load_submission_payloads_or_deferred_fields(self, background):
        Comparison.objects.create(
            submission_a=self.submission_a, submission_b=self.submission_b,
            review=10, similarity=0.91, matches_json="large match payload",
        )
        Comparison.objects.create(
            submission_a=self.submission_b, submission_b=self.submission_a,
            review=10, similarity=0.89,
        )
        Submission.objects.filter(pk__in=[self.submission_a.pk, self.submission_b.pk]).update(
            tokens="large token payload", indexes_json="large index payload",
        )
        self.exercise.template_tokens = "large exercise template"
        self.exercise.save(update_fields=["template_tokens"])
        session = self.client.session
        session["legacy_radar"] = False
        session.save()

        with patch("review.background.store_background_state") as store_state:
            with CaptureQueriesContext(connection) as worker_queries:
                load_radar_page_data.run(self.course.pk, "overview_flags", [1], "overview-flags-test")
        flags_state = store_state.call_args.args[2]
        self.assertEqual(flags_state["status"], "ready")
        background.return_value = flags_state
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse("students_hub", kwargs={"course_key": self.course.key}))

        self.assertContains(response, "radarA and radarB")
        comparison_queries = [
            query["sql"] for query in worker_queries
            if 'FROM "data_comparison"' in query["sql"]
        ]
        self.assertEqual(len(comparison_queries), 1)
        self.assertFalse(any('FROM "data_comparison"' in query["sql"] for query in queries))
        flagged = list(response.context["flagged_comparisons"])
        self.assertEqual([comparison.similarity for comparison in flagged], [0.91, 0.89])
        with self.assertNumQueries(0):
            for comparison in flagged:
                self.assertIn("matches_json", comparison.get_deferred_fields())
                for submission in (comparison.submission_a, comparison.submission_b):
                    self.assertIn("tokens", submission.get_deferred_fields())
                    self.assertIn("indexes_json", submission.get_deferred_fields())
                    self.assertTrue(submission.key)
                    self.assertTrue(submission.student.display_name)
                self.assertEqual(comparison.submission_a.exercise.name, "Exercise 1")
        for query in queries:
            for field in ('"tokens"', '"indexes_json"', '"matches_json"', '"template_tokens"'):
                self.assertNotIn(field, query["sql"])
        self.assertContains(response, "91")
        self.assertContains(response, "Exercise 1")
        self.assertContains(response, "Unflag")

    @patch("review.views.background_result", return_value={"status": "pending"})
    @patch("review.views._current_course_report_status", side_effect=AssertionError("Result backend in page load"))
    def test_students_overview_skips_task_backend_and_returns_polls_before_page_work(self, task_status, background):
        session = self.client.session
        session["legacy_radar"] = False
        session.save()
        url = reverse("students_hub", kwargs={"course_key": self.course.key})
        self.assertEqual(self.client.get(url).status_code, 200)
        ExerciseDolosReport.objects.create(exercise=self.exercise, report_id="REPORT", include_all=False)
        with patch("review.views._read_latest_course_report", side_effect=AssertionError("Metadata in poll")):
            with patch("review.views._overview_page", side_effect=AssertionError("Lists in poll")):
                for method in (self.client.get, self.client.post):
                    self.assertEqual(method(url + "?background=1").json(), {"status": "pending"})
                self.assertEqual(self.client.get(url + "?all=1&background=1").json(), {"status": "ready"})
        task_status.assert_not_called()

    @patch("review.views.background_result", return_value={"status": "pending"})
    @patch("review.views._flagged_comparisons", side_effect=AssertionError("Comparison scan in web process"))
    def test_students_overview_never_queries_comparisons_even_with_cold_flags(self, flagged, background):
        session = self.client.session
        session["legacy_radar"] = False
        session.save()
        url = reverse("students_hub", kwargs={"course_key": self.course.key})
        response = self.client.get(url)
        self.assertContains(response, "Flagged Pairs and Submissions")
        self.assertNotContains(response, "No flagged pairs")
        self.assertEqual(response.context["flags_background_state"], {"status": "pending"})
        with patch("review.views._exercise_report_ids", side_effect=AssertionError("Summary SQL in flag poll")):
            for method in (self.client.get, self.client.post):
                self.assertEqual(method(url + "?background=1&section=flags").json(), {"status": "pending"})
        self.assertEqual(background.call_args.args[2], "overview_flags")
        self.assertEqual(background.call_args.args[3][0], 1)
        flagged.assert_not_called()

    @patch("review.views.background_result", return_value={"status": "pending"})
    def test_overview_defers_large_legacy_course_graphs(self, background):
        payload = "large legacy graph " * 100000
        Course.objects.filter(pk=self.course.pk).update(similarity_graph_json=payload, clusters_json=payload)
        session = self.client.session
        session["legacy_radar"] = False
        session.save()
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse("students_hub", kwargs={"course_key": self.course.key}))
        self.assertEqual(response.status_code, 200)
        for query in queries:
            self.assertNotIn('"similarity_graph_json"', query["sql"])
            self.assertNotIn('"clusters_json"', query["sql"])
        self.assertEqual(
            response.context["course"].get_deferred_fields(), {"similarity_graph_json", "clusters_json"},
        )
        with self.assertNumQueries(1):
            self.assertEqual(response.context["course"].clusters_json, payload)

    @override_settings(CACHES={
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "overview-status-locks"},
        "course_report_progress": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "overview-status-results",
        },
    })
    @patch("review.views.AsyncResult", side_effect=AssertionError("Celery backend reached from overview polling"))
    def test_overview_widgets_poll_cached_progress_without_celery_backend(self, async_result):
        store = caches["course_report_progress"]
        store.clear()
        session = self.client.session
        session["legacy_radar"] = False
        session[views._course_report_task_session_key(self.course)] = "course-task"
        session[views._course_report_started_session_key(self.course)] = time.time()
        session[views._refresh_task_session_key(self.course)] = "refresh-task"
        session[views._refresh_started_session_key(self.course)] = time.time()
        session.save()
        overview = self.client.get(reverse("students_hub", kwargs={"course_key": self.course.key}))
        urls = [
            reverse("check_course_dolos_task", kwargs={"course_key": self.course.key, "task_id": "course-task"}),
            reverse("check_course_dolos_task_current", kwargs={"course_key": self.course.key}),
            reverse("check_refresh_submissions_task", kwargs={"course_key": self.course.key}),
        ]
        for url in urls:
            # The task-specific URL uses a sentinel until JavaScript knows the task ID.
            if url != urls[0]:
                self.assertContains(overview, url + "?cache_only=1")
            self.assertEqual(self.client.get(url + "?cache_only=1").json()["status"], "pending")
        store.set(views._course_report_progress_cache_key("course-task"), {"report_ids": ["REPORT"]})
        store.set(views.refresh_progress_cache_key("refresh-task"), {"phase": "complete"})
        self.assertEqual(self.client.get(urls[0] + "?cache_only=1").json()["status"], "ready")
        self.assertEqual(self.client.get(urls[2] + "?cache_only=1").json()["status"], "ready")
        self.assertEqual(views._cached_task_status("lost", "missing", time.time() - 3600)["status"], "failed")
        async_result.assert_not_called()
        store.clear()

    def test_overview_returns_logged_503_for_cancelled_query_but_not_other_database_errors(self):
        class QueryCancelled(Exception):
            pgcode = "57014"

        cancelled = OperationalError("cancelled after statement timeout")
        cancelled.__cause__ = QueryCancelled()
        session = self.client.session
        session["legacy_radar"] = False
        session.save()
        url = reverse("students_hub", kwargs={"course_key": self.course.key})
        with patch("review.views._exercise_report_ids", side_effect=cancelled):
            with self.assertLogs("radar.review", level="ERROR"):
                response = self.client.get(url)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response["Retry-After"], "30")
        self.assertContains(response, "database is busy", status_code=503)
        with patch("review.views._exercise_report_ids", side_effect=OperationalError("unrelated database failure")):
            with self.assertRaisesMessage(OperationalError, "unrelated database failure"):
                self.client.get(url)

    @patch("review.views.background_result")
    def test_students_overview_paginates_lists_without_counting_and_preserves_filters(self, background):
        session = self.client.session
        session["legacy_radar"] = False
        session.save()
        Student.objects.filter(pk=self.submission_b.student_id).update(is_pinned=True)
        students = Student.objects.bulk_create([
            Student(course=self.course, key="extra%03d" % index, name="Extra %03d" % index)
            for index in range(120)
        ])
        submissions = Submission.objects.bulk_create([
            Submission(key="extra-submission-%s" % student.pk, exercise=self.exercise, student=student)
            for student in students
        ])
        Comparison.objects.bulk_create([
            Comparison(submission_a=self.submission_a, submission_b=submission, review=10, similarity=0.9)
            for submission in submissions
        ])
        url = reverse("students_hub", kwargs={"course_key": self.course.key})
        next_url = url + "?all=1&similarity=90&exercises=1&run=release"
        student_ids, comparison_ids = [], []
        for number in range(1, 4):
            with patch("review.background.store_background_state") as store_state:
                with CaptureQueriesContext(connection) as worker_queries:
                    load_radar_page_data.run(self.course.pk, "overview_flags", [number], "overview-flags-test")
            background.return_value = store_state.call_args.args[2]
            self.assertEqual(background.return_value["status"], "ready")
            with CaptureQueriesContext(connection) as queries:
                response = self.client.get(next_url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context["students_page"]["number"], number)
            self.assertEqual(response.context["flagged_page"]["number"], number)
            student_ids.extend(student.pk for student in response.context["students"])
            comparison_ids.extend(comparison.pk for comparison in response.context["flagged_comparisons"])
            self.assertLessEqual(len(response.context["students"]), 50)
            self.assertLessEqual(len(response.context["flagged_comparisons"]), 50)
            for table in ("data_student", "data_comparison"):
                source = queries if table == "data_student" else worker_queries
                selects = [query["sql"] for query in source if 'FROM "%s"' % table in query["sql"]]
                self.assertEqual(len(selects), 1)
                self.assertIn("LIMIT 51", selects[0])
                self.assertNotIn("COUNT(", selects[0])
            self.assertFalse(any('FROM "data_comparison"' in query["sql"] for query in queries))
            if number < 3:
                for page in ("students_page", "flagged_page"):
                    self.assertIn("all=1", response.context[page]["next_url"])
                    self.assertIn("similarity=90", response.context[page]["next_url"])
                    self.assertIn("exercises=1", response.context[page]["next_url"])
                    self.assertIn("run=release", response.context[page]["next_url"])
                next_url = url + response.context["students_page"]["next_url"] + "&flags_page=%s" % (number + 1)
            else:
                self.assertIsNone(response.context["students_page"]["next_url"])
                self.assertIsNone(response.context["flagged_page"]["next_url"])
                self.assertContains(response, "Previous")
        self.assertEqual(student_ids[0], self.submission_b.student_id)
        self.assertEqual(len(set(student_ids)), 122)
        self.assertEqual(len(student_ids), 122)
        self.assertEqual(len(set(comparison_ids)), 120)
        self.assertEqual(len(comparison_ids), 120)
        invalid = self.client.get(url + "?students_page=invalid&flags_page=-1")
        self.assertEqual(invalid.context["students_page"]["number"], 1)
        self.assertEqual(invalid.context["flagged_page"]["number"], 1)

    @patch("review.views.background_result", return_value={"status": "pending"})
    def test_students_hub_uses_requested_submission_set(self, background):
        Student.objects.filter(key="studentA").update(name="Alice Example")
        Student.objects.filter(key="studentB").update(name="Bob Example")
        ExerciseDolosReport.objects.create(
            exercise=self.exercise,
            include_all=False,
            report_id="BEST_REPORT",
            submissions_included=2,
        )
        ExerciseDolosReport.objects.create(
            exercise=self.exercise,
            include_all=True,
            report_id="ALL_REPORT",
            submissions_included=2,
        )
        session = self.client.session
        session["legacy_radar"] = False
        session.save()
        url = reverse("students_hub", kwargs={"course_key": self.course.key})

        best_response = self.client.get(url)
        self.assertEqual(background.call_args.args[3], [["BEST_REPORT"], 0.83, 1])
        self.assertContains(best_response, 'href="%s" aria-current="true"' % url)
        self.assertContains(best_response, "Alice Example (studentA)")
        self.assertContains(best_response, "Bob Example (studentB)")

        all_response = self.client.get(url + "?all=1")
        self.assertEqual(background.call_args.args[3][0], ["ALL_REPORT"])
        self.assertContains(all_response, 'href="%s?all=1" aria-current="true"' % url)

        self.client.get(url + "?similarity=90&exercises=1")
        self.assertEqual(background.call_args.args[3][1:], [0.9, 1])

    @patch("review.views._generate_dolos_report")
    def test_dolos_hub_reuses_stored_report_without_generating(self, generate_report):
        ExerciseDolosReport.objects.create(
            exercise=self.exercise,
            include_all=False,
            report_id="STORED_REPORT",
            submissions_included=2,
        )
        session = self.client.session
        session["legacy_radar"] = False
        session.save()
        page_url = reverse(
            "dolos_hub_exercise",
            kwargs={"course_key": self.course.key, "exercise_key": self.exercise.key},
        )
        report_url = reverse(
            "dolos_hub_exercise_report",
            kwargs={"course_key": self.course.key, "exercise_key": self.exercise.key},
        )

        page_response = self.client.get(page_url)
        ajax_response = self.client.get(report_url)

        self.assertContains(page_response, "Using cached report")
        self.assertContains(page_response, "STORED_REPORT")
        self.assertEqual(ajax_response.json()["report_id"], "STORED_REPORT")
        self.assertTrue(ajax_response.json()["reused"])
        generate_report.assert_not_called()

    @patch("review.views._build_group_rows", return_value=[])
    @patch("review.views._build_pair_rows")
    def test_summary_caches_only_displayed_pairs_but_groups_and_stats_use_every_pair(self, build_pairs, build_groups):
        pairs = [{"a_key": "a%s" % index, "b_key": "b%s" % index} for index in range(100)]
        build_pairs.return_value = pairs

        result = views._build_course_similarity_summary(self.course, [], 0.83, 1)

        self.assertEqual(result["pair_rows"], pairs[:40])
        self.assertEqual(result["stats"]["pairs_total"], 100)
        self.assertEqual(build_groups.call_args.args[0], pairs)

    @patch("review.views._generate_dolos_report", return_value="NEW_REPORT")
    def test_dolos_hub_can_force_regeneration_of_stored_report(self, generate_report):
        stored_report = ExerciseDolosReport.objects.create(
            exercise=self.exercise,
            include_all=False,
            report_id="STORED_REPORT",
            submissions_included=2,
        )
        Submission.objects.filter(pk=self.submission_b.pk).update(
            created=stored_report.generated_at + timedelta(seconds=1)
        )
        session = self.client.session
        session["legacy_radar"] = False
        session.save()
        page_url = reverse(
            "dolos_hub_exercise",
            kwargs={"course_key": self.course.key, "exercise_key": self.exercise.key},
        )
        report_url = reverse(
            "dolos_hub_exercise_report",
            kwargs={"course_key": self.course.key, "exercise_key": self.exercise.key},
        )

        page_response = self.client.get(page_url)
        forced_page_response = self.client.get(page_url + "?force=1")
        ajax_response = self.client.get(report_url + "?force=1")

        self.assertContains(page_response, "1 new submission since last analysis")
        self.assertContains(page_response, "Re-run analysis for")
        self.assertEqual(
            forced_page_response.context["report_status_url"], report_url + "?force=1"
        )
        self.assertEqual(ajax_response.json()["status"], "idle")
        generate_report.assert_not_called()
        result = views._build_hub_report_data(self.exercise, False, None)
        self.assertEqual(result["report_id"], "NEW_REPORT")
        self.assertFalse(result["reused"])
        generate_report.assert_called_once()
        stored_report.refresh_from_db()
        self.assertEqual(stored_report.report_id, "NEW_REPORT")

    @patch("cheatersheet.views.requests.post")
    def test_sends_provider_submission_keys_to_cheatersheet(self, post):
        response = Mock(status_code=201)
        response.json.return_value = {"id": 7}
        post.return_value = response

        result = self.client.post(
            reverse(
                "create_cheatersheet_comparison",
                kwargs={
                    "course_key": self.course.key,
                    "left_submission_id": self.submission_a.pk,
                    "right_submission_id": self.submission_b.pk,
                },
            ),
            {"similarity": "0.87", "comment": "Review this pair"},
        )

        self.assertEqual(result.status_code, 201)
        post.assert_called_once_with(
            "http://cheatersheet.test/create-comparison/providerA/ex1/",
            json={
                "comparison": "true",
                "submission_id": "providerA",
                "exercise_key": "ex1",
                "student_key": "studentA",
                "other_submission_id": "providerB",
                "other_student_key": "studentB",
                "course_key": "42",
                "similarity": "0.87",
                "comment": "Review this pair",
            },
            headers={
                "Authorization": "Token secret",
                "Content-Type": "application/json",
            },
            timeout=15,
        )

    @override_settings(CHEATERSHEET_API_TOKEN="CONFIGURE IN LOCAL_SETTINGS.PY")
    @patch("cheatersheet.views.requests.post")
    def test_cheatersheet_comparison_does_not_require_api_token(self, post):
        response = Mock(status_code=201)
        response.json.return_value = {"id": 7}
        post.return_value = response

        result = self.client.post(
            reverse(
                "create_cheatersheet_comparison",
                kwargs={
                    "course_key": self.course.key,
                    "left_submission_id": self.submission_a.pk,
                    "right_submission_id": self.submission_b.pk,
                },
            ),
        )

        self.assertEqual(result.status_code, 201)
        self.assertNotIn("Authorization", post.call_args.kwargs["headers"])

    @patch("cheatersheet.views.requests.post")
    def test_new_radar_sends_comparison_like_legacy_radar(self, post):
        response = Mock(status_code=201)
        response.json.return_value = {"id": 7}
        post.return_value = response
        payload = {
            "comparison": "true",
            "submission_id": "providerA",
            "exercise_key": "ex1",
            "student_key": "studentA",
            "other_submission_id": "providerB",
            "other_student_key": "studentB",
            "course_key": "42",
            "similarity": "0.87",
            "comment": "Review this pair",
            "csrfmiddlewaretoken": "radar-only",
        }

        legacy_result = self.client.post(
            reverse(
                "cheatersheet_api_add_comparison",
                kwargs={"submission_id": "providerA"},
            ),
            payload,
        )
        legacy_call = post.call_args
        post.reset_mock()

        new_result = self.client.post(
            reverse(
                "create_cheatersheet_comparison",
                kwargs={
                    "course_key": self.course.key,
                    "left_submission_id": self.submission_a.pk,
                    "right_submission_id": self.submission_b.pk,
                },
            ),
            {"similarity": "0.87", "comment": "Review this pair"},
        )

        self.assertEqual(legacy_result.status_code, 201)
        self.assertEqual(new_result.status_code, 201)
        self.assertEqual(post.call_args, legacy_call)

    @patch("cheatersheet.views.requests.post")
    def test_preserves_non_json_cheatersheet_error(self, post):
        response = Mock(status_code=404, reason="Not Found", ok=False)
        response.json.side_effect = requests.exceptions.JSONDecodeError(
            "Expecting value", "\n<!doctype html>", 1
        )
        post.return_value = response

        result = self.client.post(
            reverse(
                "create_cheatersheet_comparison",
                kwargs={
                    "course_key": self.course.key,
                    "left_submission_id": self.submission_a.pk,
                    "right_submission_id": self.submission_b.pk,
                },
            )
        )

        self.assertEqual(result.status_code, 404)
        self.assertEqual(
            result.json(),
            {"error": "CheaterSheet returned HTTP 404: Not Found"},
        )

    @patch("review.views._fetch_dolos_pairs_rows")
    @patch("cheatersheet.views.requests.post")
    def test_sends_selected_dolos_pair_to_cheatersheet(self, post, fetch_pairs):
        fetch_pairs.return_value = [{
            "id": "17",
            "leftFilePath": "course42/ex1/studentA_%s.txt" % self.submission_a.pk,
            "rightFilePath": "course42/ex1/studentB_%s.txt" % self.submission_b.pk,
            "similarity": "0.91",
        }]
        response = Mock(status_code=201)
        response.json.return_value = {"id": 8}
        post.return_value = response

        result = self.client.post(
            reverse(
                "create_cheatersheet_comparison_from_dolos",
                kwargs={
                    "course_key": self.course.key,
                    "report_id": "report-123",
                    "pair_id": 17,
                },
            )
        )

        self.assertEqual(result.status_code, 201)
        fetch_pairs.assert_called_once_with("report-123")
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["submission_id"], "providerA")
        self.assertEqual(payload["other_submission_id"], "providerB")
        self.assertEqual(payload["similarity"], "0.91")


class CourseSimilaritySummaryTests(TestCase):
    def test_postgresql_statement_deadline_is_transaction_local_and_restored(self):
        with patch("review.decorators.connection") as database:
            with patch("review.decorators.transaction.atomic"):
                database.vendor = "postgresql"
                cursor = database.cursor.return_value.__enter__.return_value
                cursor.fetchone.return_value = ("17s",)
                with database_timeout(2000):
                    cursor.execute("SELECT 1")
                self.assertEqual(cursor.execute.call_args_list, [
                    call("SHOW statement_timeout"),
                    call("SELECT set_config('statement_timeout', %s, true)", ["2000"]),
                    call("SELECT 1"),
                    call("SELECT set_config('statement_timeout', %s, true)", ["17s"]),
                ])

    def test_only_qualifying_exercises_count_and_groups_require_every_pair(self):
        exercises = {
            key: SimpleNamespace(name=key.upper())
            for key in ("ex1", "ex2", "ex3")
        }
        students = {"a": "Alice", "b": "Bob", "c": "Carol"}
        scores = {
            ("a", "b"): {"ex1": .8, "ex2": .6, "ex3": .49},
            ("a", "c"): {"ex1": .9, "ex2": .7},
            ("b", "c"): {"ex1": .95},
        }

        pairs = views._build_pair_rows(scores, exercises, students, .5, 2)

        self.assertEqual({(row["a_key"], row["b_key"]) for row in pairs}, {("a", "b"), ("a", "c")})
        self.assertEqual(next(row for row in pairs if row["b_key"] == "b")["exercise_count"], 2)
        self.assertEqual(views._build_group_rows(pairs, students), [])

        scores[("b", "c")]["ex2"] = .51
        pairs = views._build_pair_rows(scores, exercises, students, .5, 2)
        groups = views._build_group_rows(pairs, students)

        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["member_keys"], ["a", "b", "c"])
        self.assertEqual(groups[0]["minimum_shared_exercises"], 2)

    def test_group_search_stops_at_display_limit(self):
        partitions = [["a%d" % index for index in range(4)],
                      ["b%d" % index for index in range(4)],
                      ["c%d" % index for index in range(4)]]
        pairs = []
        for left_partition_index, left_partition in enumerate(partitions):
            for right_partition in partitions[left_partition_index + 1:]:
                for left in left_partition:
                    for right in right_partition:
                        pairs.append({"a_key": left, "b_key": right, "exercise_count": 2})
        students = {key: key for partition in partitions for key in partition}

        groups = views._build_group_rows(pairs, students, limit=20)

        self.assertEqual(len(groups), 20)

    @patch("review.views.requests.get")
    def test_dolos_pair_rows_are_fetched_once_per_report(self, get):
        response = Mock(text="leftFilePath,rightFilePath,similarity\na,b,0.8\n")
        response.raise_for_status.return_value = None
        get.return_value = response
        views._fetch_dolos_pairs_rows.cache_clear()

        views._fetch_dolos_pairs_rows("REPORT")
        views._fetch_dolos_pairs_rows("REPORT")

        get.assert_called_once()


@override_settings(CACHES={
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "status-locks"},
    "course_report_progress": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "status-results",
    },
})
class BackgroundStatusTests(TestCase):
    def setUp(self):
        self.store = caches["course_report_progress"]
        self.store.clear()
        caches["default"].clear()
        self.addCleanup(self.store.clear)
        self.addCleanup(caches["default"].clear)
        self.course = SimpleNamespace(pk=42)
        self.factory = RequestFactory()
        self.key = result_key(42, "summary", [[["REPORT"], 0.83, 1], ""])
        self.arguments = [["REPORT"], 0.83, 1]

    @patch("provider.tasks.load_radar_page_data.apply_async")
    def test_ready_polls_read_only_small_status_and_page_reads_full_result(self, enqueue):
        result = {"pair_rows": [{"large_payload": "x" * 100000}], "group_rows": []}
        state = {"status": "ready", "result": result}
        store_background_state(self.store, self.key, state, 600)

        with patch.object(self.store, "get", wraps=self.store.get) as get:
            for request in (
                self.factory.get("/?background=1"),
                self.factory.post("/?background=1"),
            ):
                self.assertEqual(
                    background_result(request, self.course, "summary", self.arguments), {"status": "ready"},
                )
            self.assertEqual(get.call_args_list, [call(self.key + ":status"), call(self.key + ":status")])
        enqueue.assert_not_called()
        self.assertEqual(
            background_result(self.factory.get("/"), self.course, "summary", self.arguments), state,
        )

    @patch("provider.tasks.load_radar_page_data.apply_async")
    def test_missing_payload_invalidates_ready_status_and_can_be_queued_again(self, enqueue):
        store_background_state(self.store, self.key, {"status": "ready", "result": []}, 600)
        self.store.delete(self.key)

        self.assertEqual(
            background_result(self.factory.get("/"), self.course, "summary", self.arguments), {"status": "idle"},
        )
        self.assertIsNone(self.store.get(self.key + ":status"))
        state = background_result(self.factory.post("/?background=1"), self.course, "summary", self.arguments)
        self.assertEqual(state["status"], "pending")
        self.assertEqual(self.store.get(self.key + ":status"), state)
        enqueue.assert_called_once()
        self.assertEqual(enqueue.call_args.kwargs["queue"], "radar_background")

    def test_status_marker_expires_before_payload_and_omits_result(self):
        store = Mock()
        state = {"status": "ready", "result": {"large": "payload"}}

        store_background_state(store, "key", state, 600)

        self.assertEqual(store.set.call_args_list, [
            call("key", state, 600),
            call("key:status", {"status": "ready"}, 599),
        ])
