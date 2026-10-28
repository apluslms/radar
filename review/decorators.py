from contextlib import contextmanager
import logging

from six import wraps
from django.contrib.auth.decorators import login_required
from django.db import connection, OperationalError, transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from data.models import Course, Exercise, Student

COURSE_KEY = "course_key"
EXERCISE_KEY = "exercise_key"
STUDENT_KEY = "student_key"
logger = logging.getLogger("radar.review")


@contextmanager
def database_timeout(milliseconds):
    """Keep PostgreSQL statement/lock waits bounded without changing other requests."""
    if connection.vendor != "postgresql":
        yield
        return
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SHOW statement_timeout")
            previous = cursor.fetchone()[0]
            cursor.execute("SELECT set_config('statement_timeout', %s, true)", [str(milliseconds)])
            yield
            cursor.execute("SELECT set_config('statement_timeout', %s, true)", [previous])


def overview_request(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        try:
            with database_timeout(2000):
                return view_func(request, *args, **kwargs)
        except OperationalError as exc:
            cause = exc.__cause__
            if getattr(cause, "pgcode", None) != "57014" and getattr(cause, "sqlstate", None) != "57014":
                raise
            logger.exception("Radar overview database deadline exceeded path=%s", request.path)
            return HttpResponse(
                "Radar could not load this page because the database is busy. Please retry shortly.",
                status=503, content_type="text/plain", headers={"Retry-After": "30"},
            )
    return wrapped


def access_resource(view_func):
    """
    Accesses the resource selected by named URL patterns.

    """

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):

        if COURSE_KEY not in kwargs:
            raise RuntimeError("Expected pattern \"course_name\" in the URL.")
        course = get_object_or_404(
            Course.objects.defer("similarity_graph_json", "clusters_json"), key=kwargs[COURSE_KEY],
        )
        kwargs["course"] = course

        if EXERCISE_KEY in kwargs:
            kwargs["exercise"] = get_object_or_404(
                Exercise, course=course, key=kwargs[EXERCISE_KEY]
            )

        if STUDENT_KEY in kwargs:
            kwargs["student"] = get_object_or_404(
                Student, course=course, key=kwargs[STUDENT_KEY]
            )

        if not course.has_access(request.user):
            raise PermissionError()

        return view_func(request, *args, **kwargs)

    return login_required(_wrapped_view)
