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
        logger.info("Tokenizing Scala submission %s", submission)
        parsed = run(
            ("scala", "-cp",
             "tokenizer/scalariform:tokenizer/scalariform/scalariform.jar", "ScalariformTokens"),
        get_submission_text(submission))
        lines = parsed.decode("utf-8").split("\n", 1)
        submission.tokens = lines[0].strip()
        submission.token_positions = lines[1].strip()
        submission.save()
    except Exception as e:
        logger.info("Failed to tokenize: %s", e)
        submission.tokens = ""
        submission.token_positions = ""
        submission.save()
