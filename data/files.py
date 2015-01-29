"""
File system operations.

"""
import os

from django.conf import settings


def get_submission_text(submission):
    path = path_to_submission_text(submission)
    if os.path.exists(path):
        with open(path, "r") as file:
            return file.read()


def put_submission_text(submission, text):
    path = path_to_submission_text(submission)
    os.makedirs(os.path.dirname(path))
    with open(path, "w") as file:
        file.write(text)


def path_to_submission_text(submission):
    return os.path.join(settings.SUBMISSION_DIRECTORY, submission.course.name, submission.exercise.name,
                        "%s.%d" % (submission.student.name, submission.pk))


def join_files(file_map, tokenizer):
    content = []
    for file_name in sorted(file_map.keys, key=str.lower):
        content.append(settings.TOKENIZERS[tokenizer]["separator"] % (file_name))
        content.append(file_map[file_name])
    return os.linesep.join(content)


def read_directory(path):
    file_map = {}
    for file_name in os.listdir(path):
        file_path = os.path.join(path, file_name)
        if os.path.isfile(file_path):
            with open(file_path, "r") as file:
                file_map[file_name] = file.read()
    return file_map


def student_name(path):
    (name, ) = os.path.basename(path).split(".", 1)[0]
    return name
