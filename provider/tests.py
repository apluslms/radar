from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from provider import aplus
from provider import tasks


class AplusApiUrlTests(SimpleTestCase):
    @mock.patch("provider.aplus.config_loaders.provider_config")
    def test_build_api_url_uses_provider_host_for_relative_paths(self, provider_config):
        provider_config.return_value = {"host": "https://plus.example.com"}
        course = SimpleNamespace(provider="demo")

        self.assertEqual(
            aplus.build_api_url(course, "/api/v2/submissions/123/"),
            "https://plus.example.com/api/v2/submissions/123/",
        )

    @mock.patch("provider.aplus.get_api_client")
    @mock.patch("provider.aplus.build_api_url", return_value="https://plus.example.com/api/v2/courses/42/students/")
    def test_sync_student_names_uses_paginated_course_roster(self, build_api_url, get_api_client):
        unnamed = mock.Mock(key="123456", name="No Name")
        named = mock.Mock(key="654321", name="Existing Name")
        students = mock.Mock()
        students.all.return_value = [unnamed, named]
        course = SimpleNamespace(api_id=42, students=students)
        get_api_client.return_value.load_data.side_effect = [
            {
                "results": [{"student_id": "123456", "full_name": "Matti Meikäläinen"}],
                "next": "https://plus.example.com/api/v2/courses/42/students/?page=2",
            },
            {
                "results": [{"student_id": "654321", "full_name": "Updated Name"}],
                "next": None,
            },
        ]

        with mock.patch("provider.aplus.Student.objects") as student_objects:
            updated = aplus.sync_student_names(course)

        self.assertEqual(updated, 2)
        self.assertEqual(unnamed.name, "Matti Meikäläinen")
        self.assertEqual(named.name, "Updated Name")
        student_objects.bulk_update.assert_called_once_with([unnamed, named], ["name"])
        build_api_url.assert_called_once()

    @mock.patch("provider.aplus.get_api_client")
    @mock.patch("provider.aplus.build_api_url", return_value="https://plus.example.com/api/v2/courses/42/students/")
    def test_sync_student_names_clears_placeholder_full_name_from_api(self, build_api_url, get_api_client):
        unnamed = mock.Mock(key="123456", name="No Name")
        students = mock.Mock()
        students.all.return_value = [unnamed]
        course = SimpleNamespace(api_id=42, students=students)
        get_api_client.return_value.load_data.return_value = {
            "results": [{"student_id": "123456", "full_name": "   no name   "}],
            "next": None,
        }

        with mock.patch("provider.aplus.Student.objects") as student_objects:
            updated = aplus.sync_student_names(course)

        self.assertEqual(updated, 1)
        self.assertEqual(unnamed.name, "")
        student_objects.bulk_update.assert_called_once_with([unnamed], ["name"])
        build_api_url.assert_called_once()


class CourseDolosReportTests(SimpleTestCase):
    @mock.patch("provider.tasks._report_course_progress")
    @mock.patch("provider.tasks._should_include_all_submissions", side_effect=[False, True])
    @mock.patch("provider.tasks._build_exercise_dolos_report")
    @mock.patch("provider.tasks.Course.objects.get")
    def test_course_report_generates_and_stores_every_exercise(
        self, get_course, build_report, _include_all, _report_progress
    ):
        exercises = [
            SimpleNamespace(id=11, key="ex1", name="Exercise 1"),
            SimpleNamespace(id=12, key="ex2", name="Exercise 2"),
        ]
        exercise_query = mock.MagicMock()
        exercise_query.select_related.return_value.all.return_value = exercises
        get_course.return_value = SimpleNamespace(name="Course", exercises=exercise_query)
        build_report.side_effect = [
            {"report_id": "REPORT_1", "submissions_included": 2},
            {"report_id": "REPORT_2", "submissions_included": 3},
        ]

        with mock.patch("provider.tasks.ExerciseDolosReport.objects") as report_objects:
            report_objects.filter.return_value.first.return_value = None
            result = tasks.generate_course_dolos_task.run("course")

        self.assertEqual(result["report_ids"], ["REPORT_1", "REPORT_2"])
        self.assertEqual(result["exercises_processed"], result["exercises_total"])
        self.assertEqual(result["exercises_failed"], [])
        self.assertEqual(build_report.call_count, len(exercises))
        self.assertEqual(
            [call.kwargs["include_all"] for call in build_report.call_args_list],
            [False, True],
        )
        self.assertEqual(result["reports_generated"], 2)
        self.assertEqual(result["reports_reused"], 0)
        report_objects.update_or_create.assert_has_calls([
            mock.call(
                exercise=exercises[0],
                include_all=False,
                defaults={"report_id": "REPORT_1", "submissions_included": 2},
            ),
            mock.call(
                exercise=exercises[1],
                include_all=True,
                defaults={"report_id": "REPORT_2", "submissions_included": 3},
            ),
        ])

    @mock.patch("provider.tasks._report_course_progress")
    @mock.patch("provider.tasks._should_include_all_submissions", side_effect=[False, True])
    @mock.patch("provider.tasks._build_exercise_dolos_report")
    @mock.patch("provider.tasks.Course.objects.get")
    def test_course_report_reuses_every_stored_exercise_report(
        self, get_course, build_report, _include_all, _report_progress
    ):
        exercises = [
            SimpleNamespace(id=11, key="ex1", name="Exercise 1"),
            SimpleNamespace(id=12, key="ex2", name="Exercise 2"),
        ]
        exercise_query = mock.MagicMock()
        exercise_query.select_related.return_value.all.return_value = exercises
        get_course.return_value = SimpleNamespace(name="Course", exercises=exercise_query)
        stored_reports = [
            SimpleNamespace(report_id="REPORT_1", submissions_included=2),
            SimpleNamespace(report_id="REPORT_2", submissions_included=3),
        ]

        with mock.patch("provider.tasks.ExerciseDolosReport.objects") as report_objects:
            report_objects.filter.return_value.first.side_effect = stored_reports
            result = tasks.generate_course_dolos_task.run("course")

        self.assertEqual(result["report_ids"], ["REPORT_1", "REPORT_2"])
        self.assertEqual(result["reports_reused"], 2)
        self.assertEqual(result["reports_generated"], 0)
        build_report.assert_not_called()
        report_objects.update_or_create.assert_not_called()

    @mock.patch("provider.tasks._report_course_progress")
    @mock.patch("provider.tasks._should_include_all_submissions", return_value=False)
    @mock.patch("provider.tasks._build_exercise_dolos_report")
    @mock.patch("provider.tasks.Course.objects.get")
    def test_forced_course_report_replaces_stored_exercise_report(
        self, get_course, build_report, _include_all, _report_progress
    ):
        exercise = SimpleNamespace(id=11, key="ex1", name="Exercise 1")
        exercise_query = mock.MagicMock()
        exercise_query.select_related.return_value.all.return_value = [exercise]
        get_course.return_value = SimpleNamespace(name="Course", exercises=exercise_query)
        build_report.return_value = {
            "report_id": "NEW_REPORT",
            "submissions_included": 2,
        }

        with mock.patch("provider.tasks.ExerciseDolosReport.objects") as report_objects:
            result = tasks.generate_course_dolos_task.run("course", force=True)

        report_objects.filter.assert_not_called()
        build_report.assert_called_once()
        report_objects.update_or_create.assert_called_once_with(
            exercise=exercise,
            include_all=False,
            defaults={"report_id": "NEW_REPORT", "submissions_included": 2},
        )
        self.assertEqual(result["reports_generated"], 1)
