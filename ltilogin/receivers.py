"""
Parse course data from LTI login requests.
If the OAuth data in the request contains new course data, add new Course instances to the database.
"""
import logging
from django.conf import settings
from django.contrib.auth.signals import user_logged_in
from django.core.exceptions import PermissionDenied

from data.models import Course, URLKeyField
from aplus_client.django.models import ApiNamespace as Site


logger = logging.getLogger('radar.receivers')


def add_course_permissions(sender, **kwargs):
    """
    Add permissions to course user authenticated with (from oauth).
    Also add courses to session so they are used for permission checks
    """
    request = kwargs.get('request', None)
    user = kwargs.get('user', None)
    oauth = getattr(request, 'oauth', None)

    if request and user and oauth:
        api_token = getattr(oauth, 'custom_user_api_token', None)
        course_api_id = getattr(oauth, 'custom_context_api_id', None)
        course_api = getattr(oauth, 'custom_context_api', None)
        course_title = getattr(oauth, 'context_title', None)
        context_id = getattr(oauth, 'context_id', None)
        if api_token is None or course_api_id is None or course_api is None or context_id is None:
            logger.error("LTI login request doesn't contain all required "
                         "fields (custom_user_api_token, custom_context_api_id, "
                         "custom_context_api, context_id) for course membership update."
                         "User in question is {}".format(user))
            raise PermissionDenied("LTI request is missing some fields to allow login")

        # store API token
        site = Site.get_by_url(course_api)
        user.add_api_token(api_token, site) # will not add duplicates

        course_key = URLKeyField.safe_version(context_id)

        # get or create course
        try:
            course = Course.objects.using_namespace(site).get(api_id=course_api_id)
        except Course.DoesNotExist:
            apiclient = user.get_api_client(site)
            url, params = apiclient.normalize_url(course_api)
            apiclient.update_params(params)
            course_obj = apiclient.load_data(url)
            course = Course.objects.get_new_or_updated(course_obj, namespace=site, key=course_key)
            course.save()

        # add course membership for permissions
        user.courses.add(course)

        logger.info("New authentication by {user} for {key} {name}.".format(
            user=user,
            key=course_key,
            name=course_title,
        ))

#         oauth.redirect_url = reverse('index')

        # List LTI params in debug
        if settings.DEBUG:
            logger.debug("LTI login accepted for user %s", user)
            for k, v in sorted(oauth.params):
                logger.debug("  \w param -- %s: %s", k, v)


    # if request and user:
    #     # add courses to users session
    #     courses = list(user.courses.all())
    #     request.session[SITES_SESSION_KEY] = [course.namespace_id for course in courses]
    #     request.session[COURSES_SESSION_KEY] = [course.id for course in courses]


user_logged_in.connect(add_course_permissions)
