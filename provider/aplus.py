import logging
import time

from data import files
from data.models import ProviderQueue, Submission, Comparison
from radar.config import tokenizer_config
from review.views import get_radar_config


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
        queue = ProviderQueue(course=course, data=str(sid))
        queue.save()


def cron(course, config):
    """
    Creates a complete submission using the A+ API.
    System guarantees the cron calls are never parallel.

    """
    count = 0
    for queued in ProviderQueue.objects.filter(course=course):
        try:
            if count > 0:
                time.sleep(0.5)
            logger.info("Processing queued A+ submission with id %s for %s", queued.data, course)
            # We need someone with a token to the A+ API.
            api_client = _get_api_client(course)
            submission_url = config["host"] + API_SUBMISSION_URL % { "sid": queued.data }
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

            exercise = course.get_exercise(str(exercise_data["id"]))
            if exercise.name == "unknown":
                logger.debug("Exercise '%s' with id %d does not yet exist in Radar, creating a new entry.", exercise_name, exercise_data["id"])
                exercise.set_from_config(exercise_data)
                exercise.save()
                Comparison.objects.clean_for_exercise(exercise)
                exercise.clear_tokens_and_matches()

            # TODO: save each student separately and mark as allowed duplicates
            student = course.get_student("_".join(_decode_students(data["submitters"])))
            submission = Submission.objects.create(
                exercise=exercise,
                student=student,
                provider_url=data["html_url"],
                grade=data["grade"],
            )

            files_data = {
                d["filename"]: api_client.do_get(d["url"]).text
                for d in data["files"]
            }

            text = files.join_files(files_data, tokenizer_config(exercise.tokenizer))
            files.put_submission_text(submission, text)

            queued.delete()
            count += 1
            logger.info("Processing queued A+ entry for %s", course)
        except Exception:
            logger.exception("Failed to handle queued A+ submission")


def reload(exercise, config):
    """
    Clears all submissions and fetches the current submission list from A+.

    """
    api_client = _get_api_client(exercise.course)
    submissions_url = config["host"] + API_SUBMISSION_LIST_URL % { "eid": exercise.key }
    exercise.submissions.all().delete()
    for submission in api_client.load_data(submissions_url):
        ProviderQueue.objects.create(course=exercise.course, data=submission["id"])


# TODO a better solution would probably be to configure A+ to allow API access to the Radar service itself and not use someones LTI login tokens to fetch stuff from the API
def _get_api_client(course):
    """
    Return the AplusTokenClient of the first user with staff status from list of course reviewers.
    """
    api_user = course.reviewers.filter(is_staff=True).first()
    return api_user.get_api_client(course.namespace)


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

