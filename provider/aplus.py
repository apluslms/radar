import base64
import json
import logging
from urllib.request import urlopen

from data import files
from data.models import ProviderQueue, Submission
from radar.config import tokenizer


API_URL = "http://%(host)s/api/v1/submission_content/%(sid)s/" + \
            "?format=json&username=%(user)s&api_key=%(key)s"
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


def _detect_submission_id(request):
    if request.method != "POST" or POST_KEY not in request.POST:
        logger.error("Received invalid request to A+ submission hook")
        return None
    try:
        return int(request.POST[POST_KEY])
    except ValueError:
        logger.exception("Received invalid A+ submission id \"%s\" from hook", request.POST[POST_KEY])
        return None


def cron(course, config):
    """
    Creates a complete submission using the A+ API.
    System guarantees the cron calls are never parallel.
    
    """
    logger.info("Running A+ provider for submission queue")
    for queued in ProviderQueue.objects.filter(course=course, processed=False):
        try:
            data = _fetch_submission_data(int(queued.data), config)
            text = files.join_files(_decode_files(data["files"]), tokenizer(course))
            # TODO fetch exercise title from api
            exercise = course.get_exercise(data["exercise"])
            student = course.get_student("_".join(_decode_students(data["student_ids"])))
            submission = Submission(exercise=exercise, student=student)
            submission.grade = float(data["service_points"]) / float(data["service_max_points"])
            submission.save()
            files.put_submission_text(submission, text)

            queued.processed = True
            queued.save()
        except Exception:
            logger.exception("Failed to handle queued A+ submission")
    pass


def _fetch_submission_data(sid, config):
    context = {
        "host": config["host"],
        "user": config["user"],
        "key": config["key"],
        "sid": sid,
    }
    url = API_URL % (context)
    logger.info("Requesting A+ API: %s", url)
    resource = urlopen(url, timeout=6)
    data = resource.read().decode(resource.headers.get_content_charset())
    return json.loads(data)


def _decode_files(file_map):
    for key in file_map.keys():
        file_map[key] = base64.b64decode(file_map[key].encode('ascii')).decode("utf-8")
    return file_map


def _decode_students(students):
    return map(lambda u: "null" if u is None else u, students)
