import logging

logger = logging.getLogger("radar.tokenizer")

def cron():
    """
    Tokenizes natural text to a sequence of high level structural tokens
    that are independent from word choices. A minimum length to match
    should be long.
    
    Language depended word tokenizers could classify words and improve
    matching accuracy.
    
    """
    logger.error("Missing natural text tokenizer")
