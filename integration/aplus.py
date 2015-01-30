import logging
import json
import urllib2

API_URL = "http://%(host)s/api/v1/submission_content/%(sid)s/" +\
            "?format=json&username=%(user)s&api_key=%(key)s"
POST_KEY = "submission_id"

logger = logging.getLogger("radar.hook")


def get_submission(request, config):
    """
    Each integration should provide a function to react
    to new submission hook and take action to retrieve
    or process the submission data.
    
    """
    sid = detect_submission_id(request)
    if sid != None:
        data = fetch_submission_data(sid, config)
        #TODO pick user, exercise, grade, content
        #TODO create models and file


def detect_submission_id(request):
    if request.method != "POST" or POST_KEY not in request.POST:
        logger.error("Received invalid request to A+ submission hook")
        return None
    try:
        return int(request.POST[POST_KEY])
    except ValueError:
        logger.error("Received invalid A+ submission id \"%s\" from hook"
                     % (request.POST[POST_KEY]))
        return None


def fetch_submission_data(sid, config):
    context = {
        "host": config["host"],
        "user": config["user"],
        "key": config["key"],
        "sid": sid,
    }
    return json.load(urllib2.urlopen(API_URL % context, timeout=6))
