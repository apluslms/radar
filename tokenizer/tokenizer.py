import json
import logging

from radar.config import tokenizer_config, configured_function


logger = logging.getLogger("radar.tokenizer")


def tokenize_submission(submission, p_config):
    """
    Tokenizes a submission.

    """
    logger.info("Tokenizing submission %s", submission)
    get_submission_text = configured_function(p_config, "get_submission_text")
    source = get_submission_text(submission, p_config)
    tokens, indexes = tokenize_source(source, tokenizer_config(submission.exercise.tokenizer))
    submission.tokens = tokens
    submission.indexes_json = json.dumps(indexes)
    submission.save()


def tokenize_source(source, t_config):
    """
    Tokenizes source string for an exercise.

    """
    f = configured_function(t_config, "tokenize")
    return f(source, t_config)


