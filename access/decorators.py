from django.utils.six import wraps
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from data.models import Course, Exercise, Student, Submission, MatchGroup

COURSE_KEY = "course_name"
EXERCISE_KEY = "exercise_name"
STUDENT_KEY = "student_name"
SUBMISSION_KEY = "submission_id"
GROUP_KEY = "group_id"

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

        exercise = None
        if EXERCISE_KEY in kwargs:
            exercise = get_object_or_404(Exercise, course=course, name=kwargs[EXERCISE_KEY])
            kwargs["exercise"] = exercise
        
        student = None
        if STUDENT_KEY in kwargs:
            student = get_object_or_404(Student, course=course, name=kwargs[STUDENT_KEY])
            kwargs["student"] = student
        
        if SUBMISSION_KEY in kwargs:
            if exercise is not None:
                kwargs["submission"] = get_object_or_404(Submission, exercise=exercise, pk=kwargs[SUBMISSION_KEY])
            elif student is not None:
                kwargs["submission"] = get_object_or_404(Submission, student=student, pk=kwargs[SUBMISSION_KEY])
            else:
                raise RuntimeError("Encountered pattern \"submission_id\" in the URL without \"exercise_name\" or \"student_name\".")

        if GROUP_KEY in kwargs:
            if exercise is None:
                raise RuntimeError("Encountered pattern \"group_id\" in the URL without \"exercise_name\".")
            kwargs["group"] = get_object_or_404(MatchGroup, exercise=exercise, pk=kwargs[GROUP_KEY])

        if not course.has_access(request.user):
            raise PermissionError()

        return view_func(request, *args, **kwargs)

    return login_required(_wrapped_view)
