from django.http.response import HttpResponse, Http404
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
import logging

from data.models import Course
from radar.config import provider, configured_function
from django.contrib.auth.decorators import login_required
from access.decorators import access_resource
from django.core.urlresolvers import reverse
from data.files import get_submission_text

logger = logging.getLogger("radar.hook")

@login_required
def index(request):
    return render(request, "access/index.html", {
        "hierarchy": (("Courses", None),),
        "courses": Course.objects.get_available_courses(request.user)
    })

@access_resource
def course(request, course_name=None, course=None):
    exercises = course.exercises.all()
    for e in exercises:
        e.group_count = e.active_groups().count()
    return render(request, "access/course.html", {
        "hierarchy": (("Courses", reverse("index")), (course.name, None)),
        "course": course,
        "exercises": exercises
    })

@access_resource
def exercise(request, course_name=None, exercise_name=None, course=None, exercise=None):
    groups = exercise.active_groups()
    n = exercise.size
    for g in groups:
        g.ratio = g.size / n
        g.length = len(g.tokens)
    return render(request, "access/exercise.html", {
        "hierarchy": (("Courses", reverse("index")),
                      (course.name, reverse("access.views.course", kwargs={ "course_name": course.name })),
                      (exercise.name, None)),
        "course": course,
        "exercise": exercise,
        "groups": groups
    })

@access_resource
def group(request, course_name=None, exercise_name=None, group_id=None, course=None, exercise=None, group=None):
    return render(request, "access/group.html", {
        "hierarchy": (("Courses", reverse("index")),
                      (course.name, reverse("access.views.course", kwargs={ "course_name": course.name })),
                      (exercise.name, reverse("access.views.exercise", kwargs={ "course_name": course.name, "exercise_name": exercise.name })),
                      ("Match Group %d" % (group.pk), None)),
        "course": course,
        "exercise": exercise,
        "group": group,
        "matches": group.matches.all().order_by('-length')
    })

@access_resource
def student(request, course_name=None, student_name=None, course=None, student=None):
    return render(request, "access/student.html", {
        "hierarchy": (("Courses", reverse("index")),
                      (course.name, reverse("access.views.course", kwargs={ "course_name": course.name })),
                      (student.name, None)),
        "course": course,
        "student": student
    })


@access_resource
def submission(request, course_name=None, student_name=None, submission_id=None, course=None, student=None, submission=None):
    return render(request, "access/submission.html", {
        "hierarchy": (("Courses", reverse("index")),
                      (course.name, reverse("access.views.course", kwargs={ "course_name": course.name })),
                      (student.name, reverse("access.views.student", kwargs={ "course_name": course.name, "student_name": student.name })),
                      ("Submission %d" % (submission.pk), None)),
        "course": course,
        "student": student,
        "exercise": submission.exercise,
        "submission": submission,
        "matches": submission.matches.all().order_by('first_token'),
        "source": get_submission_text(submission)
    })

@csrf_exempt
def hook_submission(request, course_name=None):
    """
    Receives the hook call for new submission
    and passes it to the course provider.
    
    """
    course = get_object_or_404(Course, name=course_name)

    if course.archived:
        logger.error("Submission hook failed, archived course %s", course)
        raise Http404()

    config = provider(course)
    try:
        f = configured_function(config, "hook")
        f(request, course, config)
    except Exception:
        logger.exception("Submission hook failed")

    return HttpResponse("Working on it sire!")
