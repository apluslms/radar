import logging

from django.http.response import HttpResponse, Http404
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt

from data.models import Course
from radar.config import provider_config, configured_function


logger = logging.getLogger("radar.hook")

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

    config = provider_config(course.provider)
    try:
        f = configured_function(config, "hook")
        f(request, course, config)
    except Exception:
        logger.exception("Submission hook failed")

    return HttpResponse("Working on it sire!")
