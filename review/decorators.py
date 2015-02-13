from django.utils.six import wraps
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from data.models import Course, Exercise, Student

COURSE_KEY = "course_name"
EXERCISE_KEY = "exercise_name"
STUDENT_KEY = "student_name"

def access_resource(view_func):
    """
    Accesses the resource selected by named URL patterns.
    
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        
        if COURSE_KEY not in kwargs:
            raise RuntimeError("Expected pattern \"course_name\" in the URL.")
        course = get_object_or_404(Course, name=kwargs[COURSE_KEY])
        kwargs["course"] = course

        if EXERCISE_KEY in kwargs:
            kwargs["exercise"] = get_object_or_404(Exercise, course=course, name=kwargs[EXERCISE_KEY])
        
        if STUDENT_KEY in kwargs:
            kwargs["student"] = get_object_or_404(Student, course=course, name=kwargs[STUDENT_KEY])

        if not course.has_access(request.user):
            raise PermissionError()

        return view_func(request, *args, **kwargs)

    return login_required(_wrapped_view)
