import logging

logger = logging.getLogger("radar.tokenizer")

def cron():
  """
  Tokenizes natural text to a sequence of high level structural tokens
  that are independent from word choices. Either the length of text to
  match should be long or class of words should be detected.
  
  """
  logger.error("Missing natural text tokenizer")
