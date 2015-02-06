from data.files import get_submission_text
from tokenizer.executor import run

def cron(submission):
    """
    Tokenizes a submission to a sequence of high level structural tokens
    that are independent from names or values.
    
    Runs a scala subprocess.
    
    """
    parsed = run(
        ["scala", "-cp", "tokenizer/scalariform.jar:tokenizer", "ScalariformTokens"],
        get_submission_text(submission))
    (tokens, positions) = parsed.split("\n")
    submission.tokens = tokens
    submission.token_positions = positions
    submission.save()
