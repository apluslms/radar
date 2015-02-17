import logging

logger = logging.getLogger("radar.tokenizer")

def cron(submission, config):
    """
    Skips the tokenizing with an empty result.
    
    """
    submission.tokens = ""
    submission.token_positions = ""
    submission.save()
