from types import SimpleNamespace
from unittest.mock import Mock, patch
from datetime import timedelta

import requests
from aplus_client.django.models import ApiNamespace
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.timezone import now

from data.models import Course, Exercise, ExerciseDolosReport, Student, Submission
from review import views


@override_settings(
    CHEATERSHEET_WEB_SERVER_URL="http://cheatersheet.test",
    CHEATERSHEET_API_TOKEN="secret",
)
class CreateCheatersheetComparisonTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user("reviewer", password="password")
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

    def test_course_report_waiting_panel_includes_active_game(self):
        html = render_to_string(
            "review/_course_report_panel.html",
            {
                "course": self.course,
                "course_report_task_status": {"status": "pending"},
            },
        )

        self.assertIn(
            'class="hub-course-game active" id="canvas" width="500" height="500"',
            html,
        )

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

    @patch("review.views._dolos_pairs_for_student", return_value=[])
    def test_student_hub_uses_requested_submission_set(self, pairs_for_student):
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
        pairs_for_student.assert_called_once_with("BEST_REPORT", "studentA")
        self.assertContains(best_response, 'href="%s" aria-current="true"' % url)

        pairs_for_student.reset_mock()
        all_response = self.client.get(url + "?all=1")
        pairs_for_student.assert_called_once_with("ALL_REPORT", "studentA")
        self.assertContains(all_response, 'href="%s?all=1" aria-current="true"' % url)

    @patch("review.views._build_course_similarity_summary", return_value={})
    def test_students_hub_uses_requested_submission_set(self, build_summary):
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
        self.assertEqual(build_summary.call_args.args[1], ["BEST_REPORT"])
        self.assertEqual(build_summary.call_args.args[2:], (0.83, 1))
        self.assertContains(best_response, 'href="%s" aria-current="true"' % url)
        self.assertContains(best_response, "Alice Example (studentA)")
        self.assertContains(best_response, "Bob Example (studentB)")

        all_response = self.client.get(url + "?all=1")
        self.assertEqual(build_summary.call_args.args[1], ["ALL_REPORT"])
        self.assertContains(all_response, 'href="%s?all=1" aria-current="true"' % url)

        self.client.get(url + "?similarity=90&exercises=1")
        self.assertEqual(build_summary.call_args.args[2:], (0.9, 1))

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
        self.assertContains(page_response, "Redo analysis")
        self.assertEqual(
            forced_page_response.context["report_status_url"], report_url + "?force=1"
        )
        self.assertEqual(ajax_response.json()["report_id"], "NEW_REPORT")
        self.assertFalse(ajax_response.json()["reused"])
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
            "http://cheatersheet.test/api/submissions/providerA/",
            json={
                "comparison": "true",
                "submission_id": "providerA",
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

    @patch("cheatersheet.views.requests.post")
    def test_new_radar_sends_comparison_like_legacy_radar(self, post):
        response = Mock(status_code=201)
        response.json.return_value = {"id": 7}
        post.return_value = response
        payload = {
            "comparison": "true",
            "submission_id": "providerA",
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
