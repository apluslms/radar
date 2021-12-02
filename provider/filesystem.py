import os
import logging

from data import files
from data.models import Submission
from radar.config import tokenizer_config
from provider.insert import submission_exists, insert_submission, prepare_submission
from provider import tasks


logger = logging.getLogger("radar.provider")


def hook(request, course, config):
    logger.info("Ignored hook request for filesystem course %s", course)


def load_submission_dir(exercise, path):
    """
    Inserts a submission from directory for a given exercise.
    """
    if not os.path.isdir(path):
        raise NameError("Submissions to add need to be directories")
    submitter_id, submission_key = _path_name_to_submission(path)
    if submission_exists(submission_key):
        logger.info('Skipping existing submission %s', submission_key)
        return None
    submission = insert_submission(exercise, submission_key, submitter_id)
    text = files.join_files(_read_directory(path), tokenizer_config(exercise.tokenizer))
    files.put_submission_text(submission, text)
    prepare_submission(submission)
    return submission


def _path_name_to_submission(path):
    p = os.path.abspath(path)
    timestamp = os.path.basename(p)
    submitter_id = os.path.basename(os.path.dirname(p))
    return (submitter_id, "{}/{}".format(submitter_id, timestamp))

def _read_directory(path):
    file_map = {}
    for file_name in os.listdir(path):
        file_path = os.path.join(path, file_name)
        if os.path.isfile(file_path):
            with open(file_path, "rb") as f:
                file_map[file_name] = f.read().decode("utf-8", "ignore")
    return file_map


def reload(exercise, config):
    logger.info("Clearing all submissions for exercise %s", exercise)
    exercise.course.similarity_graph_json = ''
    exercise.course.save()
    exercise.submissions.all().delete()
    exercise.touch_all_timestamps()


def recompare(exercise, config):
    logger.info("Resetting all submission matches for exercise %s", exercise)
    exercise.course.similarity_graph_json = ''
    exercise.course.save()
    exercise.clear_all_matches()
    exercise.touch_all_timestamps()
    # Matching proceeds with CLI command
    # matcher_tasks.match_exercise(exercise.id)


def recompare_all_unmatched(course):
    tasks.recompare_all_unmatched(course.id)


def async_api_read(request, course, has_radar_config):
    logger.info("Ignored API read request for filesystem course %s", course)


def load_exercise_template(exercise, config, invalidate_cache=False):
    return ""
