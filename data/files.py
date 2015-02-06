"""
Storing submission source in file system.

"""
from django.conf import settings
import os


def get_submission_text(submission):
    path = path_to_submission_text(submission)
    if os.path.exists(path):
        with open(path, "r") as f:
            return f.read()
    return ""


def put_submission_text(submission, text):
    path = path_to_submission_text(submission)
    dirpath = os.path.dirname(path)
    if not os.path.exists(dirpath):
        os.makedirs(dirpath)
    with open(path, "w") as f:
        f.write(text)


def path_to_submission_text(submission):
    return os.path.join(settings.SUBMISSION_DIRECTORY,
                        submission.exercise.course.name,
                        submission.exercise.name,
                        "%s.%d" % (submission.student.name, submission.pk))


def join_files(file_map, config):
    content = []
    for file_name in sorted(file_map.keys()):
        content.append(config["separator"] % (file_name))
        content.append(file_map[file_name])
    return os.linesep.join(content)
