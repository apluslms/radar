from data.files import get_submission_text
from tokenizer.executor import run
import logging

logger = logging.getLogger("radar.tokenizer")

def cron(submission, config):
    """
    Tokenizes a submission to a sequence of high level structural tokens
    that are independent from names or values.
    
    Runs a scala subprocess.
    
    """
    try:
      parsed = run(
          ("scala", "-cp",
           "tokenizer/scalariform:tokenizer/scalariform/scalariform.jar", "ScalariformTokens"),
          get_submission_text(submission))
      lines = parsed.decode("utf-8").split("\n", 1)
      submission.tokens = lines[0]
      submission.token_positions = lines[1]
      submission.save()
      logger.debug("Tokenized submission: %s" % (submission))
    except Exception:
      # TODO lower log level as bad submissions will not tokenize
      logger.exception("Failed to tokenize submission: %s" % (submission))
