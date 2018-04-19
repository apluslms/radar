import json
import logging
import time
import requests

from data.models import ProviderQueue, Submission, URLKeyField
from radar.config import provider_config


POST_KEY = "submission_id"
API_SUBMISSION_URL = "/api/v2/submissions/%(sid)s/"
API_EXERCISE_URL = "/api/v2/exercises/%(eid)s/"
API_SUBMISSION_LIST_URL = API_EXERCISE_URL + "submissions/"


logger = logging.getLogger("radar.provider")


def hook(request, course, config):
    """
    Stores the submission id from A+ for further provider work.

    """
    sid = _detect_submission_id(request)
    if sid is not None:
        data = {"sid": str(sid)}
        # len(json.dumps(data)) > 128 is very unlikely
        queue = ProviderQueue(course=course, data=json.dumps(data))
        queue.save()


def cron(course, config):
    """
    Creates a complete submission using the A+ API.
    System guarantees the cron calls are never parallel.

    """
    count = 0
    for queued in ProviderQueue.objects.filter(course=course).filter(failed=False):
        try:
            if count > 0:
                time.sleep(0.5)
            queued_data = json.loads(queued.data)
            if "eid" in queued_data:
                logger.info("Processing queued A+ exercise with id %s for %s", queued_data["eid"], course)

                if not course.has_exercise(queued_data["eid"]):
                    raise Exception("Invalid queued task: queued.data['eid'] exercise key %s does not match any exercise in the database" % queued_data["eid"])
                exercise = course.get_exercise(queued_data["eid"])
                # Fetch all submissions for this exercise and queue them for comparison
                reload(exercise, provider_config(course.provider))
                queued.delete()
                continue

            if "sid" not in queued_data:
                raise Exception("Invalid queued task: missing submission id key 'sid'. Keys were: %s" % list(queued_data.keys()))

            logger.info("Processing queued A+ submission with id %s for %s", queued_data["sid"], course)

            if Submission.objects.filter(key=queued_data["sid"]).exists():
                raise Exception("A+ submission with key %s already exists, will not attempt to process it again" % queued_data["sid"])
            # We need someone with a token to the A+ API.
            api_client = get_api_client(course)
            submission_url = config["host"] + API_SUBMISSION_URL % { "sid": queued_data["sid"] }
            logger.debug("Fetching submission data from %s", submission_url)
            data = api_client.load_data(submission_url)
            exercise_data = data["exercise"]
            exercise_name = exercise_data["display_name"]

            # Check if exercise is configured for Radar, if not, skip to next.
            radar_config = get_radar_config(exercise_data)
            if radar_config is None:
                logger.debug("Exercise '%s' has no Radar configuration, skipping.", exercise_name)
                queued.delete()
                continue
            else:
                logger.debug("Exercise '%s' has a Radar configuration with tokenizer '%s'.", exercise_name, radar_config["tokenizer"])

            # Get or create exercise configuration
            exercise = course.get_exercise(str(exercise_data["id"]))
            if exercise.name == "unknown":
                logger.debug("Exercise '%s' with id %d does not yet exist in Radar, creating a new entry.", exercise_name, exercise_data["id"])
                exercise.set_from_config(radar_config)
                exercise.save()

            logger.debug("Creating a submission for exercise '%s'.", exercise_name)
            # A+ allows more than one submitter for a single submission
            # TODO: if there are more than one unique submitters,
            # set as approved plagiate and show this in the UI
            ## for submitter_id in _decode_students(data["submitters"]):
            submitter_id = "_".join(_decode_students(data["submitters"]))
            student = course.get_student(str(submitter_id))
            Submission.objects.create(
                key=queued_data["sid"],
                exercise=exercise,
                student=student,
                provider_url=data["html_url"],
                grade=data["grade"],
            )

            queued.delete()
            count += 1
            logger.debug("Successfully processed queued A+ submission with id %s for %s", queued_data["sid"], course)
        except Exception:
            logger.exception("Failed to handle queued A+ submission")
            try:
                queued.failed = True
                queued.save()
            except Exception:
                logger.exception("Failed to set queued task to failed state")


def reload(exercise, config):
    """
    Clears all submissions and fetches the current submission list from A+.

    """
    api_client = get_api_client(exercise.course)
    submissions_url = config["host"] + API_SUBMISSION_LIST_URL % { "eid": exercise.key }
    submissions_data = api_client.load_data(submissions_url)
    if submissions_data is None:
        logger.error("Invalid submissions data returned from %s, expected an iterable but got None", submissions_url)
        return
    exercise.submissions.all().delete()
    for submission in submissions_data:
        if not Submission.objects.filter(key=submission["id"]).exists():
            data = {"sid": str(submission["id"])}
            ProviderQueue.objects.create(
                course=exercise.course,
                data=json.dumps(data)
            )
        else:
            logger.error("Got a duplicate submission with id %s from %s", submission ["id"], submissions_url)


def queued_reload(exercise):
    data = {"eid": exercise.key}
    ProviderQueue.objects.create(
        course=exercise.course,
        data=json.dumps(data)
    )


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
       "template_source": load_exercise_template_from_api_data(exercise_data)
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
