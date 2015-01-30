from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http.response import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.module_loading import import_by_path
import logging

from data.models import Course


logger = logging.getLogger("radar.hook")

def hook_submission(request, course_name=None):
    """
    Receives the hook call for new submission
    and passes it to the course provider.
    
    """
    course = get_object_or_404(Course, name=course_name)
    config = settings.PROVIDERS[course.provider]
    try:
        getdef = import_by_path(config["def"])
        getdef(request, config)
    except ImproperlyConfigured:
        logger.error("Could not find configured submission hook: %s" % (config["def"]))        
    
    return HttpResponse("Working on it sire!")
