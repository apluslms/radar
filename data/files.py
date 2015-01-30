"""
File system operations.

"""
import os

from django.conf import settings


def get_submission_text(submission):
    path = path_to_submission_text(submission)
    if os.path.exists(path):
        with open(path, "r") as f:
            return f.read()


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


def join_files(file_map, tokenizer):
    content = []
    for file_name in sorted(file_map.keys(), key=str.lower):
        content.append(settings.TOKENIZERS[tokenizer]["separator"] % (file_name))
        content.append(file_map[file_name])
    return os.linesep.join(content)


def read_directory(path):
    file_map = {}
    for file_name in os.listdir(path):
        file_path = os.path.join(path, file_name)
        if os.path.isfile(file_path):
            with open(file_path, "r") as f:
                file_map[file_name] = f.read()
    return file_map


def safe_student_name(path):
    (name, _) = os.path.basename(path).split(".", 1)
    return name
