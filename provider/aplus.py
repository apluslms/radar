import base64
import json
import logging
import time
from urllib.request import urlopen

from data import files
from data.models import ProviderQueue, Submission, URLKeyField
from radar.config import tokenizer_config


API_EXERCISE_URL = "/api/v1/exercise/%(eid)s/"
API_SUBMISSION_URL = "/api/v1/submission_content/%(sid)s/"
API_QS = "?format=json&username=%(user)s&api_key=%(key)s"
VIEW_URL = "/exercise/submissions/inspect/%(sid)s/"

POST_KEY = "submission_id"

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
            logger.info("Processing queued A+ entry for %s", course)
            data = _fetch_submission_data(queued.data, config)
            exercise = course.get_exercise(data["exercise"])
            if exercise.name == "unknown":
                e_data = _fetch_exercise_data(data["exercise"], config)
                exercise.name = e_data["name"]
                exercise.save()
            student = course.get_student("_".join(_decode_students(data["student_ids"])))
            url = config["host"] + VIEW_URL % { "sid": queued.data }
            submission = Submission(exercise=exercise, student=student, provider_url=url)
            if data["service_max_points"] > 0:
                submission.grade = float(data["service_points"]) / float(data["service_max_points"])
            else:
                submission.grade = 0
            submission.save()
            text = files.join_files(_decode_files(data["files"]), tokenizer_config(exercise.tokenizer))
            files.put_submission_text(submission, text)

            queued.delete()
            count += 1
        except Exception:
            logger.exception("Failed to handle queued A+ submission")


def reload(exercise, config):
    """
    Clears all submissions and fetches the current submission list from A+.

    """
    if exercise.key.startswith("apiv1exercise"):
        eid = exercise.key[13:]
        e_data = _fetch_exercise_data(API_EXERCISE_URL % { "eid": eid }, config)
        exercise.name = e_data["name"]
        exercise.save()
        exercise.submissions.all().delete()
        for url in e_data["submissions"]:
            s = URLKeyField.safe_version(url)
            if s.startswith("apiv1submission"):
                queue = ProviderQueue(course=exercise.course, data=s[15:])
                queue.save()


def _detect_submission_id(request):
    if request.method != "POST" or POST_KEY not in request.POST:
        logger.error("Received invalid request to A+ submission hook")
        return None
    try:
        return int(request.POST[POST_KEY])
    except ValueError:
        logger.exception("Received invalid A+ submission id \"%s\" from hook", request.POST[POST_KEY])
        return None


def _fetch_submission_data(sid, config):
    qs = API_QS % { "user": config["user"], "key": config["key"] }
    url = config["host"] + API_SUBMISSION_URL % { "sid": sid } + qs
    logger.info("Requesting A+ API: %s", url)
    resource = urlopen(url, timeout=6)
    data = resource.read().decode(resource.headers.get_content_charset() or "utf-8")
    return json.loads(data)


def _fetch_exercise_data(url, config):
    qs = API_QS % { "user": config["user"], "key": config["key"] }
    url = config["host"] + url + qs
    logger.info("Requesting A+ API: %s", url)
    resource = urlopen(url, timeout=6)
    data = resource.read().decode(resource.headers.get_content_charset() or "utf-8")
    return json.loads(data)


def _decode_files(file_map):
    for key in file_map.keys():
        try:
            file_map[key] = base64.b64decode(file_map[key].encode('ascii')).decode("utf-8", "ignore")
        except Exception:
            file_map[key] = "encode error"
            logger.exception("Unable to decode submission file from A+ API: %s", key)
    return file_map


def _decode_students(students):
    return map(lambda u: "null" if u is None else u, students)
