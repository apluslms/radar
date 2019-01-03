import logging
import requests

from django.core.cache import caches as django_caches

from data.models import URLKeyField
from provider import tasks
import matcher.tasks as matcher_tasks


POST_KEY = "submission_id"
API_SUBMISSION_URL = "/api/v2/submissions/%(sid)s/"
API_EXERCISE_URL = "/api/v2/exercises/%(eid)s/"
API_SUBMISSION_LIST_URL = API_EXERCISE_URL + "submissions/"


logger = logging.getLogger("radar.provider")


class AplusProviderError(Exception):
    pass


def hook(request, course, config):
    """
    Stores the submission id from A+ for further provider work.

    """
    sid = _detect_submission_id(request)
    if sid is None:
        raise AplusProviderError("Received invalid request to A+ submission hook: invalid submission id.")
    # Create submission asynchronously but do not match
    submission_url = config["host"] + API_SUBMISSION_URL % { "sid": sid }
    tasks.create_submission.delay(sid, course.key, submission_url)


def reload(exercise, config):
    """
    Reload all submissions to given exercise from the A+ API, tokenize sources and match all.
    Deletes all existing submissions to exercise.
    """
    logger.info("Reloading all submissions for exercise %s", exercise)
    submissions_url = config["host"] + API_SUBMISSION_LIST_URL % { "eid": exercise.key }
    # Queue exercise for asynchronous handling,
    # all submissions to this exercise are created in parallel while matching is sequential
    tasks.reload_exercise_submissions.delay(exercise.id, submissions_url)


def recompare(exercise, config):
    """
    Clear all comparisons of submissions to given exercise and match all from scratch.
    """
    logger.info("Recomparing all submissions for exercise %s", exercise)
    # Drop all existing comparisons and queue for recomparison
    exercise.clear_all_matches()
    exercise.touch_all_timestamps()
    matcher_tasks.match_exercise.delay(exercise.id)


# TODO a better solution would probably be to configure A+ to allow API access to the Radar service itself and not use someones LTI login tokens to fetch stuff from the API
def get_api_client(course):
    """
    Return the AplusTokenClient of the first user with staff status from list of course reviewers.
    """
    api_user = course.reviewers.filter(is_staff=True).first()
    return api_user.get_api_client(course.namespace)


def request_template_content(url):
    """
    Attempt to GET exercise template contents from url.
    """
    try:
        logger.debug("Requesting exercise template content from '%s'.", url)
        response = requests.get(url, timeout=(4, 10))
        response.raise_for_status()
        response_content_type = response.headers.get("Content-Type")
        if response_content_type.find("text/plain") < 0:
            raise requests.exceptions.InvalidHeader(
                    "Expected response content with MIME type text/plain but got content type {}".format(response_content_type),
                    response=response)
        response.encoding = "utf-8"
        return response.text
    except (requests.exceptions.ConnectionError,
            requests.exceptions.ReadTimeout,
            requests.exceptions.HTTPError,
            requests.exceptions.InvalidHeader) as err:
        logger.error(
            "%s when requesting template contents from %s: %s",
            err.__class__.__name__,
            url,
            err)
        return ''


# FIXME the A+ API does not support fetching submission data containing information about which language was enabled when a submission was posted
# i18n for exercise templates are encoded into the urls, e.g. as:
# "|en:<external url to template in english>|fi:<external url to template in finnish>|"
# Therefore, if i18n exercise template urls are found,
# we use a heuristic to first select the english template and if not available, the finnish template, and if not available, fail miserably
def load_exercise_template_from_api_data(exercise_data):
    """
    Do a GET request for each exercise template url in exercise, and return the template source of response, concatenated with newlines.
    """
    # It is possible to define multiple templates from multiple urls for
    # a single exercise.
    # However, in most cases 'templates' will hold just one url.
    source = ""
    template_urls_str = exercise_data.get("templates", None)
    if template_urls_str:
        template_urls = template_urls_str.split(" ")
        parsed_urls = []
        for template_url in template_urls:
            if template_url.startswith("|"):
                # i18n urls
                lang_prefixes = ("|en:", "|fi:")
                for lang_prefix in lang_prefixes:
                    if lang_prefix in template_url:
                        template_url = template_url.split(lang_prefix, 1)[1]
                        template_url = template_url.split("|", 1)[0]
                        break
                else:
                    raise AplusProviderError("Unknown exercise template url format: {}, expected i18n urls but did not find any language prefixes from '{}'. Complete url was: {}".format(template_url, lang_prefixes, template_urls_str))
            if template_url:
                parsed_urls.append(template_url)
        template_data = (request_template_content(url) for url in parsed_urls)
        # Join all non-empty templates into a single string, separated by newlines.
        # If there is only one non-empty template in template_data,
        # this will simply evaluate to that template, with no extra newline.
        source = '\n'.join(t for t in template_data if t)
    return source


def load_exercise_template(exercise, config, invalidate_cache=False):
    """
    Get the exercise template source from the A+ API for an Exercise object and return it as a string.
    """
    template_cache = django_caches["exercise_templates"]
    template_source = template_cache.get(exercise.key)
    if template_source is not None:
        if invalidate_cache:
            template_cache.delete(exercise.key)
        else:
            return template_source
    exercise_url = config["host"] + API_EXERCISE_URL % {"eid": exercise.key}
    data = get_api_client(exercise.course).load_data(exercise_url)
    if data is None:
        logger.error("A+ API returned None when loading from %s", exercise_url)
        return ""
    template_source = load_exercise_template_from_api_data(data)
    template_cache.set(exercise.key, template_source)
    return template_source


def get_radar_config(exercise_data):
    """
    Extract relevant Radar data from an AplusApiDict or None if there is no Radar data.
    """
    exercise_info = exercise_data.get("exercise_info")
    if not exercise_info:
        return None
    radar_config = exercise_info.get("radar")
    if not radar_config:
        return None
    data = {
       "name": exercise_data.get("display_name"),
       "exercise_key": URLKeyField.safe_version(str(exercise_data["id"])),
       "url": exercise_data.get("html_url"),
       "tokenizer": radar_config.get("tokenizer", "skip"),
       "minimum_match_tokens": radar_config.get("minimum_match_tokens") or 15,
       "get_template_source": lambda: load_exercise_template_from_api_data(exercise_data)
    }
    return data


def _decode_students(students):
    return [
        u["student_id"] if u["student_id"] else u["username"]
        for u in students
    ]


def _detect_submission_id(request):
    if request.method != "POST" or POST_KEY not in request.POST:
        logger.error("Received invalid request to A+ submission hook")
        return None
    try:
        return int(request.POST[POST_KEY])
    except ValueError:
        logger.exception("Received invalid A+ submission id \"%s\" from hook", request.POST[POST_KEY])
        return None
