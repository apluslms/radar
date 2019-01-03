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
        # Stream over contents of submission file 'd' in chunks
        # Stop streaming if the file is too large
        response = api_client.do_get(d["url"], timeout=(3.2, 18), stream=True)
        if response.encoding is None:
            response.encoding = "utf-8"
        chunks = []
        total_length = 0
        for chunk in response.iter_content(chunk_size=512, decode_unicode=True):
            total_length += len(chunk)
            if total_length > settings.SUBMISSION_BYTES_LIMIT:
                logger.error(
                    "Failed GET from %s: response content size exceeded limit %d during streaming of submission file",
                    d["url"],
                    settings.SUBMISSION_BYTES_LIMIT
                )
                break
            chunks.append(chunk)
        else:
            files_data[d["filename"]] = ''.join(chunks)
    if not files_data:
        return None
    return files.join_files(files_data, tokenizer_config(submission.exercise.tokenizer))
