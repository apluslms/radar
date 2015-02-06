import os

from data import files
from data.models import Submission
from radar.config import tokenizer


def hook(request, course, config):
    """
    Ignore - there is only command line interface for file system provider.
    
    """
    pass


def cron(course):
    """
    Nothing to do.
    
    """
    pass


def load_submission_dir(exercise, path):
    """
    Inserts a submission from directory for a given exercise.
    
    """
    text = files.join_files(_read_directory(path), tokenizer(exercise))
    student = exercise.course.get_student(_safe_student_name(path))
    submission = Submission(exercise=exercise, student=student)
    submission.save()
    files.put_submission_text(submission, text)
    return submission


def _read_directory(path):
    file_map = {}
    for file_name in os.listdir(path):
        file_path = os.path.join(path, file_name)
        if os.path.isfile(file_path):
            with open(file_path, "r") as f:
                file_map[file_name] = f.read()
    return file_map


def _safe_student_name(path):
    (name, _) = os.path.basename(path).split(".", 1)
    return name
