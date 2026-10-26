from types import SimpleNamespace
from unittest.mock import Mock, patch
from datetime import timedelta

import requests
from aplus_client.django.models import ApiNamespace
from django.contrib.auth import get_user_model
from django.core.cache import caches
from django.db import connection
from django.template.loader import render_to_string
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils.timezone import now

from data.models import Comparison, Course, Exercise, ExerciseDolosReport, Student, Submission
from review import views


@override_settings(
    CHEATERSHEET_WEB_SERVER_URL="http://cheatersheet.test",
    CHEATERSHEET_API_TOKEN="secret",
)
class CreateCheatersheetComparisonTests(TestCase):
    @override_settings(CACHES={
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "refresh-locks"},
        "course_report_progress": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "refresh-results"},
    })
    @patch("provider.tasks.load_radar_page_data.apply_async")
    @patch("provider.aplus.AplusTokenClient")
    @patch("provider.aplus.get_api_client")
    def test_course_home_refresh_updates_metadata_in_worker_and_preserves_submissions(self, get_client, client_class, enqueue):
        from provider.tasks import load_radar_page_data

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
        "course_report_progress": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "metadata-results"},
    })
    @patch("provider.aplus.get_api_client")
    def test_course_home_worker_imports_missing_metadata_without_legacy_setup(self, get_client):
        from provider import aplus
        from provider.tasks import load_radar_page_data

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
        from provider import aplus

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
        "course_report_progress": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "async-test"},
    })
    @patch("provider.tasks.load_radar_page_data.apply_async")
    @patch("review.views._student_exercise_matches")
    def test_background_page_load_queue_poll_and_worker_result(self, matches, enqueue):
        from provider.tasks import load_radar_page_data

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
        "course_report_progress": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "summary-roster-results"},
    })
    @patch("provider.aplus.sync_student_names")
    @patch("review.views._build_course_similarity_summary", return_value={"pairs": []})
    def test_summary_worker_uses_stored_roster_without_refreshing_provider(self, build_summary, sync_roster):
        from provider.tasks import load_radar_page_data

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
        "course_report_progress": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "async-failure-test"},
    })
    @patch("provider.tasks.load_radar_page_data.apply_async", side_effect=RuntimeError("broker down"))
    def test_background_queue_failure_and_stale_job_can_be_retried(self, enqueue):
        import time
        from review.background import result_key

        store = caches["course_report_progress"]
        store.clear()
        session = self.client.session
        session["legacy_radar"] = False
        session.save()
        url = reverse("student_hub", kwargs={"course_key": self.course.key, "student_key": "studentA"}) + "?background=1"
        self.assertEqual(self.client.post(url).json()["status"], "failed")
        self.client.get(url)
        enqueue.assert_called_once()
        key = result_key(self.course.pk, "student_matches", [["studentA", False, []], ""])
        store.set(key, {"status": "pending", "started": time.time() - 700})
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
            reverse("student_pair_hub", kwargs={"course_key": self.course.key, "a_key": "studentA", "b_key": "studentB"}),
            reverse("student_group_hub", kwargs={"course_key": self.course.key, "member_keys": "studentA-studentB-studentC"}),
            reverse("dolos_mini_comparison", kwargs={"course_key": self.course.key, "a_key": "studentA", "b_key": "studentB", "exercise_key": self.exercise.key, "left_submission_id": self.submission_a.pk, "right_submission_id": self.submission_b.pk}),
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
        url = reverse("student_hub", kwargs={"course_key": self.course.key, "student_key": "studentA"}) + "?background=1"
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
        "course_report_progress": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "async-worker-error-test"},
    })
    @patch("review.views._fetch_dolos_pairs_rows", side_effect=requests.ConnectionError("Dolos unavailable"))
    def test_background_worker_failure_is_not_an_empty_success(self, fetch):
        from provider.tasks import load_radar_page_data

        store = caches["course_report_progress"]
        with self.assertLogs("provider.tasks", level="ERROR"):
            load_radar_page_data.run(self.course.pk, "student_matches", ["studentA", False, ["REPORT"]], "worker-error")
        self.assertEqual(store.get("worker-error")["status"], "failed")
        store.delete("worker-error")

    @override_settings(CACHES={
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "missing-report-locks"},
        "course_report_progress": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "missing-report-results"},
    })
    @patch("review.views._fetch_dolos_pairs_rows")
    def test_missing_dolos_report_suggests_regenerating_course_report(self, fetch):
        from provider.tasks import load_radar_page_data

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
        enqueue.assert_called_once_with(self.course.key, force=True)

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

    def test_new_radar_pair_flag_is_shown_in_student_overview(self):
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
        overview = self.client.get(reverse("students_hub", kwargs={"course_key": self.course.key}))
        self.assertContains(overview, "Flagged Pairs and Submissions")
        self.assertContains(overview, "radarA and radarB")

        response = self.client.post(flag_url, {"flagged": "false"}, follow=True)

        self.assertEqual(response.status_code, 200)
        comparison.refresh_from_db()
        self.assertEqual(comparison.review, 0)
        self.assertContains(response, "Pair flag removed.")

    @override_settings(CACHES={
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "home-bounds-locks"},
        "course_report_progress": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "home-bounds-results"},
    })
    @patch("review.views._flagged_comparisons")
    def test_course_home_bounds_lists_without_aggregate_counts(self, flagged_query):
        caches["default"].clear()
        caches["course_report_progress"].clear()

        class FlaggedRows:
            def __init__(self):
                self.requested_slice = None

            def only(self, *fields):
                return self

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
        "course_report_progress": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "home-results"},
    })
    @patch("provider.tasks.load_radar_page_data.apply_async")
    def test_course_home_renders_without_heavy_queries_even_after_worker_completion(self, enqueue):
        from provider.tasks import load_radar_page_data

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
