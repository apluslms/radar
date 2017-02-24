import logging


logger = logging.getLogger('radar.ltilogin')


def accept_course(oauth_request, user):
    """
    Creates or gets the course instance and adds user to it.

    """
    from data.models import Course, URLKeyField

    course_key = URLKeyField.safe_version(oauth_request.context_id) \
        if oauth_request.context_id else None
    course_name = oauth_request.context_title \
        if oauth_request.context_title else ''

    if course_key:
        course, created = Course.objects.get_or_create(key=course_key,
            defaults={'name': course_name, 'provider': 'a+', 'tokenizer': 'scala' })
        if created:
            logger.info('Creating a new LTI authenticated course: %s', course_name)
        course.reviewers.add(user)
