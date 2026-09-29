"""
Build Dolos datasets from Radar submissions.

Dolos only understands the relationships between submissions through the
``info.csv`` metadata bundled with the ZIP it analyses: each file may carry a
``full_name`` (author), a ``label`` (colour group) and a ``created_at``
(timeline). We additionally encode the structure in the ZIP path
(``course/exercise/...``) so a single report can span many exercises and many
courses.

This module is deliberately free of Django and network imports so the dataset
builder stays runnable on its own (see the ``__main__`` self-check at the
bottom: ``python -m review.dolos_reports``).
"""
import concurrent.futures
import csv
import datetime
import logging
import os
import tempfile
import types
import zipfile


logger = logging.getLogger(__name__)

INFO_COLUMNS = ["filename", "full_name", "label", "created_at", "exercise", "course"]


# Radar tokenizer -> Dolos language name (see LanguagePicker in
# dolos/lib/src/lib/language.ts). Anything Dolos has no parser for
# (skip/text/html/css/matlab/unknown) falls back to "char", Dolos's
# character-based tokenizer: it analyses any content and never throws.
_DOLOS_LANGUAGES = {
    "python": "python",
    "scala": "scala",
    "c": "c",
    "cpp": "cpp",
    "java": "java",
    "js": "javascript",
}


def dolos_language(tokenizer):
    """Map a Radar tokenizer to a valid Dolos language; unknown -> 'char'."""
    return _DOLOS_LANGUAGES.get(tokenizer, "char")


def submission_path(submission):
    """Relative ZIP path encoding course/exercise/student for a submission."""
    exercise = submission.exercise
    return "/".join(
        [
            exercise.course.key,
            exercise.key,
            "%s_%s.txt" % (submission.student.key, submission.id),
        ]
    )


def write_submission_files(work_dir, submissions, label_fn, get_text):
    """
    Write each submission's source into ``work_dir`` under its
    :func:`submission_path`. Does not write ``info.csv`` -- callers that want
    a single dataset from one batch of submissions should use
    :func:`write_dataset`; callers building a dataset incrementally across
    several batches (e.g. one call per exercise) should collect the returned
    rows themselves and write ``info.csv`` once at the end.

    ``label_fn(submission)`` returns the Dolos colour label and
    ``get_text(submission)`` returns the source code.

    A submission whose ``get_text`` raises (e.g. a transient provider API
    error) is skipped rather than aborting the whole batch -- one flaky fetch
    should not fail an entire report. Returns ``(rows, skipped_count)``.
    """
    submissions = list(submissions)

    def safe_get_text(submission):
        try:
            return get_text(submission)
        except Exception:
            logger.warning(
                "Skipping submission %s (exercise %s): failed to fetch source",
                submission.id, submission.exercise.key, exc_info=True,
            )
            return None

    # get_text often does network I/O (e.g. one HTTP request per submission
    # file against the A+ API), which dominates report generation time when
    # done one submission at a time. Threads overlap that I/O; the GIL isn't
    # held while waiting on the network, so this scales well even though it's
    # not multiprocessing.
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
        texts = list(executor.map(safe_get_text, submissions))

    rows = []
    skipped = 0
    for submission, text in zip(submissions, texts):
        if text is None:
            skipped += 1
            continue
        rel_path = submission_path(submission)
        abs_path = os.path.join(work_dir, *rel_path.split("/"))
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as source_file:
            source_file.write(text)
        created_at = submission.provider_submission_time
        if isinstance(created_at, datetime.datetime):
            created_at = created_at.strftime("%Y-%m-%d %H:%M:%S %z")
        exercise = submission.exercise
        student = submission.student
        student_label = student.display_name
        rows.append(
            {
                "filename": rel_path,
                "full_name": student_label,
                "label": label_fn(submission),
                "created_at": created_at or "",
                "exercise": exercise.name,
                "course": exercise.course.name,
            }
        )
    return rows, skipped


def write_dataset(work_dir, submissions, label_fn, get_text):
    """
    Write each submission's source into ``work_dir`` under its
    :func:`submission_path` and an ``info.csv`` at the root.

    ``label_fn(submission)`` returns the Dolos colour label and
    ``get_text(submission)`` returns the source code. Returns the info rows.
    """
    rows, skipped = write_submission_files(work_dir, submissions, label_fn, get_text)
    if skipped:
        logger.warning("write_dataset: skipped %d/%d submission(s) due to fetch errors",
                       skipped, skipped + len(rows))
    write_info_csv(work_dir, rows)
    return rows


def write_info_csv(work_dir, rows):
    """Write ``info.csv`` at the root of ``work_dir`` from already-collected rows."""
    with open(os.path.join(work_dir, "info.csv"), "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=INFO_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def course_progress_cache_key(task_id):
    """Cache key for a course-wide report task's progress payload, shared
    between the Celery task (writer) and the polling views (reader)."""
    return "dolos_report:course_progress:%s" % task_id


def refresh_progress_cache_key(task_id):
    """Cache key for a submission-refresh task's progress payload."""
    return "dolos_report:refresh_progress:%s" % task_id


def zip_dataset(src_dir, zip_path):
    """Zip ``src_dir`` into ``zip_path`` preserving relative paths (info.csv at root)."""
    with zipfile.ZipFile(zip_path, "w") as zip_handle:
        for root, _dirs, files in os.walk(src_dir):
            for filename in files:
                file_path = os.path.join(root, filename)
                zip_handle.write(file_path, arcname=os.path.relpath(file_path, src_dir))


def _demo():
    """Self-check with fake submissions; run: ``python -m review.dolos_reports``."""
    def fake(course_key, ex_key, ex_name, course_name, student_key, sub_id, student_name=None):
        course = types.SimpleNamespace(key=course_key, name=course_name)
        display_name = "%s (%s)" % (student_name, student_key) if student_name else student_key
        return types.SimpleNamespace(
            id=sub_id,
            key=str(sub_id),
            student=types.SimpleNamespace(key=student_key, display_name=display_name),
            exercise=types.SimpleNamespace(key=ex_key, name=ex_name, course=course),
            provider_submission_time=None,
        )

    submissions = [
        fake("c1", "e1", "Ex 1", "Course 1", "alice", 1),
        fake("c1", "e2", "Ex 2", "Course 1", "alice", 2),
        fake("c1", "e1", "Ex 1", "Course 1", "bob", 3, "Bob Example"),
    ]
    with tempfile.TemporaryDirectory() as work_dir:
        write_dataset(
            work_dir,
            submissions,
            label_fn=lambda s: s.exercise.name,
            get_text=lambda s: "code",
        )
        for rel in ("c1/e1/alice_1.txt", "c1/e2/alice_2.txt", "c1/e1/bob_3.txt"):
            assert os.path.isfile(os.path.join(work_dir, *rel.split("/"))), rel
        with open(os.path.join(work_dir, "info.csv")) as info:
            reader = csv.DictReader(info)
            assert reader.fieldnames == INFO_COLUMNS, reader.fieldnames
            read_rows = list(reader)
        # Zip outside work_dir so it is not included in itself.
        zip_path = os.path.join(tempfile.gettempdir(), "dolos_reports_demo.zip")
        zip_dataset(work_dir, zip_path)
        with zipfile.ZipFile(zip_path) as archive:
            names = set(archive.namelist())
        os.remove(zip_path)

    assert len(read_rows) == 3, len(read_rows)
    # Alice submitted to two different exercises -> Dolos sees her across exercises.
    alice_labels = {r["label"] for r in read_rows if r["full_name"].startswith("alice")}
    assert alice_labels == {"Ex 1", "Ex 2"}, alice_labels
    assert {r["full_name"] for r in read_rows} == {"alice", "Bob Example (bob)"}
    assert "info.csv" in names
    assert "c1/e1/alice_1.txt" in names
    # Radar tokenizers must map to names Dolos actually accepts, else the CLI
    # throws (LanguageError) and the report fails with "Oops".
    assert dolos_language("js") == "javascript"
    assert dolos_language("python") == "python"
    assert dolos_language("skip") == "char"
    assert dolos_language("matlab") == "char"
    assert dolos_language(None) == "char"
    print("dolos_reports self-check ok")


if __name__ == "__main__":
    _demo()
