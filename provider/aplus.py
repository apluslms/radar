import base64
import logging
import time
import requests

from data import files
from data.models import ProviderQueue, Submission, URLKeyField
from radar.config import tokenizer_config


POST_KEY = "submission_id"
API_SUBMISSION_URL = "/api/v2/submissions/%(sid)s/"
API_SUBMISSION_LIST_URL = "/api/v2/exercises/%(eid)s/submissions/"


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

            exercise = course.get_exercise(str(data["exercise"]["id"]))
            if exercise.name == "unknown":
                exercise.name = data["exercise"]["display_name"]
                exercise.save()

            # TODO: save each student separately and mark as allowed duplicates
            student = course.get_student("_".join(_decode_students(data["submitters"])))
            submission = Submission.objects.create(
                exercise=exercise,
                student=student,
                provider_url=data["html_url"],
                grade=data["grade"],
            )

            text = files.join_files(
                _decode_files(data["files"]),
                tokenizer_config(exercise.tokenizer)
            )
            files.put_submission_text(submission, text)

            queued.delete()
            count += 1
        except Exception:
            logger.exception("Failed to handle queued A+ submission")


def reload(exercise, config):
    """
    Clears all submissions and fetches the current submission list from A+.

    """
    data = _fetch_submission_list_data(exercise.key, config)
    exercise.submissions.all().delete()
    for s in data:
        ProviderQueue.objects.create(course=exercise.course, data=s["id"])


def _detect_submission_id(request):
    if request.method != "POST" or POST_KEY not in request.POST:
        logger.error("Received invalid request to A+ submission hook")
        return None
    try:
        return int(request.POST[POST_KEY])
    except ValueError:
        logger.exception("Received invalid A+ submission id \"%s\" from hook", request.POST[POST_KEY])
        return None


def _fetch_submission_list_data(eid, config):
    results = []
    url = config["host"] + API_SUBMISSION_LIST_URL % { "eid": eid }
    while url:
        data = _get(url, config).json()
        results.extend(data["results"])
        url = data["next"]
    return results


def _fetch_submission_data(sid, config):
    return _get(
        config["host"] + API_SUBMISSION_URL % { "sid": sid }, config
    ).json()


def _decode_files(files, config):
    return {
        data["filename"]: _get(data["url"], config).text
        for data in files
    }


def _decode_students(students):
    return [
        u["student_id"] if u["student_id"] else u["username"]
        for u in students
    ]


def _get(url, config):
    logger.info("Requesting A+ API: %s", url)
    response = requests.get(url, timeout=6, headers={
        "Authorization": "Token " + config['token'],
    })
    response.raise_for_status()
    return response
