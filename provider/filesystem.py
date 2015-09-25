import os

from data import files
from data.models import Submission
from radar.config import tokenizer_config


def hook(request, course, config):
    """
    Ignore - there is only command line interface for file system provider.

    """
    pass


def cron(course, config):
    """
    Nothing to do.

    """
    pass


def load_submission_dir(exercise, path):
    """
    Inserts a submission from directory for a given exercise.

    """
    if not os.path.isdir(path):
        return None
    text = files.join_files(_read_directory(path), tokenizer_config(exercise.tokenizer))
    (name, n) = _safe_student_name(path)
    student = exercise.course.get_student(name)
    if student.submissions.filter(exercise=exercise).count() < n:
        submission = Submission(exercise=exercise, student=student)
        submission.save()
        files.put_submission_text(submission, text)
        return submission
    return None


def _read_directory(path):
    file_map = {}
    for file_name in os.listdir(path):
        file_path = os.path.join(path, file_name)
        if os.path.isfile(file_path):
            with open(file_path, "rb") as f:
                file_map[file_name] = f.read().decode("utf-8", "ignore")
    return file_map


def _safe_student_name(path):
    print(path)
    (name, num) = os.path.basename(path).split(".", 1)
    return (name, int(num))
