"""
Storing submission source in file system.

"""
import fcntl
import os
import codecs

from django.conf import settings


def acquire_lock():
    f = open(os.path.join(settings.SUBMISSION_DIRECTORY, "manage.lock"), "w")
    try:
        fcntl.lockf(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        return None
    return f


def get_text(exercise, name):
    path = path_to_exercise(exercise, name)
    if os.path.exists(path):
        with codecs.open(path, "r", "utf-8") as f:
            return f.read()
    return ""


def put_text(exercise, name, text):
    path = path_to_exercise(exercise, name)
    dirpath = os.path.dirname(path)
    if not os.path.exists(dirpath):
        os.makedirs(dirpath)
    with codecs.open(path, "w", "utf-8") as f:
        f.write(text)


def get_submission_text(submission):
    return get_text(submission.exercise, "%s.%d" % (submission.student.key, submission.pk))


def put_submission_text(submission, text):
    return put_text(submission.exercise, "%s.%d" % (submission.student.key, submission.pk), text)


def path_to_exercise(exercise, name):
    return os.path.join(settings.SUBMISSION_DIRECTORY, exercise.course.key, exercise.key, name)


def join_files(file_map, config):
    content = []
    for file_name in sorted(file_map.keys()):
        content.append(config["separator"] % (file_name))
        content.append(file_map[file_name])
    return os.linesep.join(content)
