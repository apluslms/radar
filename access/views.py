from django.http.response import HttpResponse, Http404
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
import logging

from data.models import Course
from radar.config import provider, named_function


logger = logging.getLogger("radar.hook")

@csrf_exempt
def hook_submission(request, course_name=None):
    """
    Receives the hook call for new submission
    and passes it to the course provider.
    
    """
    course = get_object_or_404(Course, name=course_name)
    
    if course.archived:
        logger.error("Submission hook failed, Archived course")
        raise Http404()
    
    config = provider(course)
    try:
        f = named_function(config, "hook")
        f(request, course, config)
    except Exception:
        logger.exception("Submission hook failed")
    
    return HttpResponse("Working on it sire!")
