import json
import logging
import subprocess

from radar.config import tokenizer_config, configured_function
from data.files import get_submission_text


logger = logging.getLogger("radar.tokenizer")

class RunError(Exception):
    pass


def tokenize_submission(submission):
    """
    Tokenizes a submission.
    
    """
    logger.info("Tokenizing submission %s", submission)
    source = get_submission_text(submission)
    (tokens, indexes_json) = tokenize_source(source, tokenizer_config(submission.exercise.tokenizer))
    submission.tokens = tokens
    submission.indexes_json = indexes_json
    submission.save()


def tokenize_source(source, t_config):
    """
    Tokenizes source string for an exercise.
    
    """
    f = configured_function(t_config, "tokenize")
    return f(source, t_config)


def run(cmd, stdin):
    """
    Runs a command in subprocess.

    @param stdin the standard input str
    @return the standard output str
    """
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate(bytes(stdin, 'UTF-8'))
    if p.returncode != 0:
        raise RunError(err)
    return out


def indexes_to_json(line):
    """
    Parses data from a line formatted: <b:Int>-<e:Int>,<b:Int>-<e:Int>,...
    
    @param line an input line str
    @return json output str
    """
    return json.dumps(
        list(map(lambda s: list(map(int, s.split("-"))), line.split(","))),
        separators=(",", ":"))
