import logging
import requests

from data.models import URLKeyField
import provider.tasks as tasks


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
    # Queue submission for handling
    submission_url = config["host"] + API_SUBMISSION_URL % { "sid": sid }
    tasks.create_and_match(sid, course.key, submission_url)


def reload(exercise, config):
    """
    Reload all submissions to given exercise from the A+ API, tokenize sources and match all.
    """
    logger.debug("Reloading all submissions for exercise %s", exercise)
    submissions_url = config["host"] + API_SUBMISSION_LIST_URL % { "eid": exercise.key }
    tasks.reload_exercise_submissions.delay(exercise.id, submissions_url)


def recompare(exercise, config):
    """
    Clear all comparisons of submissions to given exercise and match all from scratch.
    """
    logger.debug("Recomparing all submissions for exercise %s", exercise)
    exercise.clear_all_matches()
    tasks.match_all_unmatched_submissions_for_exercise.delay(exercise.id)


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


def load_exercise_template_from_api_data(exercise_data):
    """
    Do a GET request for each exercise template url in exercise, and return the template source of response, concatenated with newlines.
    """
    # It is possible to define multiple templates from multiple urls for
    # a single exercise.
    # However, in most cases 'templates' will hold just one url.
    source = ""
    template_urls = exercise_data.get("templates", None)
    if template_urls:
        template_data = (request_template_content(url) for url in template_urls.split(" ") if url)
        # Join all non-empty templates into a single string, separated by newlines.
        # If there is only one non-empty template in template_data,
        # this will simply evaluate to that template, with no extra newline.
        source = '\n'.join(t for t in template_data if t)
    return source


def load_exercise_template(exercise, config):
    """
    Get the exercise template source from the A+ API for an Exercise object and return it as a string.
    """
    exercise_url = config["host"] + API_EXERCISE_URL % {"eid": exercise.key}
    data = get_api_client(exercise.course).load_data(exercise_url)
    if data is None:
        logger.error("A+ API returned None when loading from %s", exercise_url)
        return ""
    return load_exercise_template_from_api_data(data)


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
