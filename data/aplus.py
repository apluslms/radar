"""
Retrieving submission data from the A+ API, without storing the content on disk.

"""
import logging

from django.conf import settings

from provider.aplus import get_api_client, API_SUBMISSION_URL
from data import files
from radar.config import tokenizer_config

logger = logging.getLogger("radar.data.aplus")


def get_submission_text(submission, config):
    api_client = get_api_client(submission.exercise.course)
    if api_client is None:
        logger.error("No API client available for submission %s", submission)
        return None
    submission_api_url = config["host"] + API_SUBMISSION_URL % { "sid": submission.key }
    data = api_client.load_data(submission_api_url)
    if data is None or "files" not in data:
        logger.error("Invalid API data returned from %s", submission_api_url)
        return None
    logger.debug("Doing GET for each submission file URL for submission %s", submission)
    files_data = {}
    for d in data["files"]:
        response = api_client.do_get(d["url"], timeout=(3.2, 30))
        if len(response.content) > settings.SUBMISSION_BYTES_LIMIT:
            logger.error(
                "Failed GET from %s: response content size %d bytes exceeds limit %d",
                d["url"],
                len(response.content),
                settings.SUBMISSION_BYTES_LIMIT
            )
            continue
        response.encoding = "utf-8"
        files_data[d["filename"]] = response.text
    if not files_data:
        return None
    return files.join_files(files_data, tokenizer_config(submission.exercise.tokenizer))
