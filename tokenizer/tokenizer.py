import json
import logging
import re

from radar.config import tokenizer_config, configured_function


logger = logging.getLogger("radar.tokenizer")


def tokenize_submission(submission, submission_text, p_config):
    """
    Tokenizes a submission.

    """
    logger.info("Tokenizing submission %s", submission)
    tokens, indexes = tokenize_source(
        submission_text,
        tokenizer_config(submission.exercise.tokenizer)
    )
    return tokens, json.dumps(indexes)


def tokenize_source(source, t_config):
    """
    Tokenizes source string for an exercise.

    """
    f = configured_function(t_config, "tokenize")
    return f(source, t_config)


def watermarker(submission_text):
    watermarks = []
    mark = re.findall('[\u200c\u200b]+', submission_text)
    for i in mark:
        watermarks.append(int(i.replace('\u200b','1').replace('\u200c','0'),2))
    if watermarks:
        return(watermarks)
