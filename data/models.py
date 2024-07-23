import datetime
import json
import logging
import re

from django.conf import settings
from django.core.exceptions import ValidationError, FieldError
from django.db import models

from aplus_client.django.models import NamespacedApiObject
from radar.config import choice_name, tokenizer_config
from tokenizer.tokenizer import tokenize_source


logger = logging.getLogger("radar.model")


class URLKeyField(models.CharField):

    def clean(self, value, model_instance):
        value = super(URLKeyField, self).clean(value, model_instance)
        if not re.match(r'[A-z0-9]+', value):
            raise ValidationError('Only characters a-z, A-Z, 0-9 and _ are accepted.')
        return value

    @staticmethod
    def safe_version(text):
        return "".join([c for c in text if re.match(r'[A-z0-9]', c)])


class CourseManager(NamespacedApiObject.Manager):

    def get_available_courses(self, user):
        if user.is_staff:
            return self.all()
        return self.filter(reviewers=user)


class Course(NamespacedApiObject):
    """
    A course can receive submissions.

    """

    created = models.DateTimeField(auto_now_add=True)
    key = URLKeyField(
        max_length=64, unique=True, help_text="Unique alphanumeric course instance id"
    )
    name = models.CharField(max_length=255, help_text="Descriptive course name")
    provider = models.CharField(
        max_length=16,
        choices=settings.PROVIDER_CHOICES,
        help_text="Provider for submission data",
        default=settings.PROVIDER_CHOICES[0][0],
    )
    tokenizer = models.CharField(
        max_length=16,
        choices=settings.TOKENIZER_CHOICES,
        help_text="Tokenizer for the submission contents",
        default=settings.TOKENIZER_CHOICES[0][0],
    )
    minimum_match_tokens = models.IntegerField(
        default=15, help_text="Minimum number of tokens to consider a match"
    )
    reviewers = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="courses",
        blank=True,
        help_text="Reviewers for match analysis",
    )
    archived = models.BooleanField(db_index=True, default=False)
    similarity_graph_json = models.TextField(
        blank=True,
        default='',
        help_text="JSON-serialized string of the similarity graph definition returned by"
                  " data.graph.generate_match_graph",
    )
    objects = CourseManager()

    class Meta:
        ordering = ["-created"]

    @property
    def provider_name(self):
        return choice_name(settings.PROVIDER_CHOICES, self.provider)

    @property
    def tokenizer_name(self):
        return choice_name(settings.TOKENIZER_CHOICES, self.tokenizer)

    @property
    def submissions(self):
        return Submission.objects.filter(exercise__course=self)

    @property
    def matched_submissions(self):
        return Submission.objects.filter(exercise__course=self, matched=True)

    @property
    def marked_submissions(self):
        return Submission.objects.filter(
            exercise__course=self, comparison__review__gte=5
        )

    @property
    def exercises_with_unmatched_submissions(self):
        return [e for e in self.exercises.all() if e.has_unassigned_submissions]

    def all_comparisons(self, min_similarity):
        return Comparison.objects.filter(submission_a__exercise__course=self).filter(
            similarity__gte=min_similarity
        )

    def all_student_pair_matches(self, min_similarity):
        """
        Return non-empty QuerySets of Comparisons for each exercise and each student on this course.
        Filter by minimum similarity.
        """
        for student in self.students.all():
            for exercise in self.exercises.all():
                comparisons = (
                    # Include all Comparison objects with at least the given minimum similarity
                    self.all_comparisons(min_similarity)
                    # Include only one exercise at a time
                    # We assume no submissions of different exercises are compared
                    .filter(submission_a__exercise=exercise)
                    # Include only one student at a time
                    .filter(submission_a__student=student)
                    # Exclude template comparisons
                    .exclude(submission_b__isnull=True)
                )
                if comparisons:
                    yield comparisons

    def has_access(self, user):
        return user.is_staff or self.reviewers.filter(pk=user.pk).exists()

    def has_exercise(self, key_str):
        return self.exercises.filter(key=URLKeyField.safe_version(key_str)).exists()

    def get_exercise(self, key_str):
        exercise, _ = self.exercises.get_or_create(
            key=URLKeyField.safe_version(key_str)
        )
        return exercise

    def get_student(self, key_str):
        student, _ = self.students.get_or_create(key=URLKeyField.safe_version(key_str))
        return student

    def __str__(self):
        return "%s (%s)" % (self.name, self.created)


class Exercise(models.Model):
    """
    Each submission includes an exercise key and exercise objects are created as needed.

    """

    created = models.DateTimeField(auto_now_add=True)
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="exercises"
    )
    key = URLKeyField(max_length=64, help_text="Alphanumeric exercise id")
    name = models.CharField(
        max_length=255, default="unknown", help_text="Descriptive exercise name"
    )
    override_tokenizer = models.CharField(
        max_length=8, choices=settings.TOKENIZER_CHOICES, blank=True, null=True
    )
    override_minimum_match_tokens = models.IntegerField(blank=True, null=True)
    template_tokens = models.TextField(blank=True, default="")
    template_text = models.TextField(blank=True, default="")
    paused = models.BooleanField(default=False)
    matching_start_time = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        default=None,
        help_text="If not None, then an isoformat timestamp which should match to all incoming matching results."
                  " If None or does not match incoming results, then these results will be ignored.",
    )
    dolos_report_status = models.TextField(blank=True, default="")
    dolos_report_timestamp = models.TextField(blank=True, default="")
    dolos_report_raw_timestamp = models.IntegerField(blank=True, default=0)
    dolos_report_generated = models.BooleanField(blank=True, default=False)
    dolos_report_id = models.TextField(blank=True, default="")
    dolos_report_key = models.TextField(blank=True, default="")
    dolos_report_token = models.TextField(blank=True, default="")

    class Meta:
        unique_together = ("course", "key")
        ordering = ["course", "name", "created"]

    @property
    def tokenizer(self):
        return (
            self.override_tokenizer
            if self.override_tokenizer is not None
            else self.course.tokenizer
        )

    @property
    def tokenizer_name(self):
        return choice_name(settings.TOKENIZER_CHOICES, self.tokenizer)

    @property
    def minimum_match_tokens(self):
        return (
            self.override_minimum_match_tokens
            if self.override_minimum_match_tokens is not None
            else self.course.minimum_match_tokens
        )

    @property
    def template_length(self):
        return len(self.template_tokens)

    @property
    def student_count(self):
        return (
            Submission.objects.filter(exercise=self)
            .values("student")
            .distinct()
            .count()
        )

    @property
    def valid_submissions(self):
        return self.submissions.filter(invalid=False)

    @property
    def invalid_submissions(self):
        return self.submissions.filter(invalid=True)

    @property
    def valid_matched_submissions(self):
        return self.valid_submissions.filter(matched=True)

    @property
    def valid_unmatched_submissions(self):
        return self.valid_submissions.filter(
            matched=False, matching_start_time__isnull=True
        )

    @property
    def submissions_currently_matching(self):
        return self.valid_submissions.filter(
            matched=False,
            matching_start_time__isnull=False,
            matching_start_time=self.matching_start_time,
        )

    @property
    def has_unassigned_submissions(self):
        return self.valid_unmatched_submissions.exists()

    @property
    def submissions_max_similarity(self):
        return (
            self.valid_matched_submissions.values("student__id")
            .annotate(m=models.Max('max_similarity'))
            .order_by('-m')
            .values_list('m', flat=True)
        )

    @property
    def submissions_max_similarity_json(self):
        return json.dumps(list(self.submissions_max_similarity))

    def top_comparisons(self, rows):
        max_list = (
            self.valid_matched_submissions.values('student__id')
            .annotate(m=models.Max('max_similarity'))
            .order_by('-m')[:rows]
        )

        compared_list = self._comparisons_by_submission(
            self.valid_matched_submissions.filter(student__id=each['student__id'])
            .order_by('-max_similarity')
            .first()
            .id
            for each in max_list
        )

        # Filter the comparisons such that only unique ones are maintained, while identical ones are removed.
        # Done using Python sets which cannot have duplicate values.
        unique_set = set()

        for comparison_row in compared_list:
            unique_set.update(comparison_row["matches"])

        sorted_unique_set = sorted(
            unique_set, key=lambda comparison: comparison.similarity, reverse=True
        )

        return sorted_unique_set

    def comparisons_for_student(self, local_student):
        student_list = self._comparisons_by_submission(
            self.valid_matched_submissions.filter(student=local_student)
            .order_by("created")
            .values_list("id", flat=True)
        )

        unique_set = set()

        for single_student in student_list:
            unique_set.update(single_student["matches"])

        return unique_set

    def _comparisons_by_submission(self, submissions):
        comparisons = []
        for s_id in submissions:
            comparisons.append(
                {
                    "submission_id": s_id,
                    "matches": list(
                        Comparison.objects.exclude(submission_b__isnull=True)
                        .filter(
                            models.Q(submission_a__id=s_id)
                            | models.Q(submission_b__id=s_id)
                        )
                        .order_by("-similarity")
                        .select_related(
                            "submission_a",
                            "submission_b",
                            "submission_a__exercise",
                            "submission_a__student",
                            "submission_b__student",
                        )[: settings.SUBMISSION_VIEW_WIDTH]
                    ),
                }
            )
        return comparisons

    def set_from_config(self, config):
        self.name = config["name"]
        self.key = config["exercise_key"]
        if "template_source" in config:
            tokens, _ = tokenize_source(
                config["template_source"], tokenizer_config(config["tokenizer"])
            )
            self.template_tokens = tokens
        if config["tokenizer"] != self.course.tokenizer:
            self.override_tokenizer = config["tokenizer"]
        if config["minimum_match_tokens"] != self.course.minimum_match_tokens:
            self.override_minimum_match_tokens = config["minimum_match_tokens"]

    def clear_all_matches(self):
        """
        Delete all Comparison instances for valid, matched submissions.
        """
        Comparison.objects.clean_for_exercise(self)
        self.submissions.update(
            max_similarity=0, matched=False, matching_start_time=None
        )
        self.matching_start_time = None
        self.save()

    def touch_all_timestamps(self):
        """
        Update timestamp of this exercise and all its submissions to show we are expecting matching results with that
         timestamp to these submissions.
        """
        now = datetime.datetime.utcnow().isoformat()
        self.matching_start_time = now
        self.valid_unmatched_submissions.update(matching_start_time=now)
        self.save()

    def __str__(self):
        return "%s/%s (%s)" % (self.course.name, self.name, self.created)


# What's with the ForeignKey and unique_together with Course?
# Why not ManyToMany to Course?
class Student(models.Model):
    """
    Each submission includes a student key and student objects are created as needed.

    """

    created = models.DateTimeField(auto_now_add=True)
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="students"
    )
    key = URLKeyField(max_length=64, help_text="Alphanumeric student id")

    name = models.CharField(
        max_length=64,
        blank=True,
        default='No Name',
        help_text="Full name of the student",
    )
    email = models.EmailField(blank=True, default='No Email')

    class Meta:
        unique_together = ("course", "key")
        ordering = ["course", "key"]

    def __str__(self):
        return "%s: %s (%s)" % (self.course.name, self.key, self.created)


class Submission(models.Model):
    """
    A submission for an exercise.

    """

    key = URLKeyField(
        max_length=64, unique=True, help_text="Alphanumeric unique submission id"
    )
    created = models.DateTimeField(auto_now_add=True)
    exercise = models.ForeignKey(
        Exercise, on_delete=models.CASCADE, related_name="submissions"
    )
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="submissions"
    )
    provider_url = models.CharField(max_length=256, blank=True, null=True, default=None)
    provider_submission_time = models.DateTimeField(blank=True, null=True, default=None)
    grade = models.FloatField(default=0.0)
    tokens = models.TextField(blank=True, null=True, default=None)
    source_checksum = models.TextField(
        blank=True,
        null=True,
        default=None,
        help_text="MD5 checksum of all characters in the submission source",
    )
    indexes_json = models.TextField(blank=True, null=True, default=None)
    authored_token_count = models.IntegerField(blank=True, null=True, default=None)
    longest_authored_tile = models.IntegerField(blank=True, null=True, default=None)
    max_similarity = models.FloatField(
        db_index=True, default=0.0, help_text="Maximum average similarity."
    )
    max_with = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        help_text="The submission the max_similarity refers to",
        blank=True,
        null=True,
    )
    matched = models.BooleanField(
        default=False, help_text="Is this Submission waiting to be matched"
    )
    invalid = models.BooleanField(
        default=False,
        help_text="Is this Submission invalid in a way it cannot be matched",
    )
    matching_start_time = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        default=None,
        help_text="If not None, then this submission is currently being matched and waiting for results."
                  " None if submission is not currently being matched.",
    )

    @property
    def submissions_to_compare(self):
        return self.exercise.valid_matched_submissions.exclude(
            student=self.student
        ).exclude(longest_authored_tile__lt=self.exercise.minimum_match_tokens)

    def as_dict(self):
        """
        Return self in serializable format with minimal data needed to compute submission similarity.
        """
        template_marks, authored_token_count, longest_authored_tile = (
            self.template_marks()
        )
        return {
            "id": self.id,
            "tokens": self.tokens,
            "checksum": self.source_checksum,
            "ignore_marks": template_marks,
            "authored_token_count": authored_token_count,
            "longest_authored_tile": longest_authored_tile,
        }

    @property
    def template_comparison(self):
        return Comparison.objects.filter(
            submission_a=self, submission_b__isnull=True
        ).first()

    def template_matches(self):
        ct = self.template_comparison
        if ct is None:
            raise FieldError("Template matches requested before matching a submission")
        return json.loads(ct.matches_json)

    def template_marks(self):
        """
        Return a tuple of (marks, authored_count, longest_tile) where
            - marks: Bitmask string of token marks that have matched with the exercise template
            - authored_count: Amount of unique, non-template tokens
            - longest_tile: Amount of tokens in the longest tile with non-template tokens
        """
        token_count = len(self.tokens)
        marks = [False] * token_count
        authored_count = token_count
        longest_tile = 0
        s = 0
        for m in self.template_matches():
            match_start, match_len = m[0], m[2]
            # Mark tokens that have matched with template
            for i in range(match_start, match_start + match_len):
                marks[i] = True
            # Template tokens have not been authored by the student
            authored_count -= match_len
            longest_tile = max(longest_tile, match_start - s)
            s = match_start + match_len
        longest_tile = max(longest_tile, token_count - s)
        return ''.join(str(int(m)) for m in marks), authored_count, longest_tile

    def __str__(self):
        return (
            "%s/%s: %s grade=%.1f (created: %s)"
            % (
                self.exercise.course.name,
                self.exercise.name,
                self.student.key,
                self.grade,
                self.created,
            )
            + (" (submitted: %s)" % self.provider_submission_time)
            if self.provider_submission_time
            else ""
        )


class ComparisonManager(models.Manager):

    def clean_for_exercise(self, exercise):
        self.filter(submission_a__exercise=exercise).delete()


class Comparison(models.Model):
    """
    Comparison of two submissions, with a resulting similarity score.
    When submission_b is null, the Comparison contains the result from comparison submission_a to an exercise template.
    """

    submission_a = models.ForeignKey(
        Submission, on_delete=models.CASCADE, related_name="+"
    )
    submission_b = models.ForeignKey(
        Submission, on_delete=models.CASCADE, related_name="+", blank=True, null=True
    )
    similarity = models.FloatField(
        default=None,
        null=True,
        help_text="Similarity score resulting from the comparison of two submissions.",
    )
    matches_json = models.TextField(
        blank=True,
        null=True,
        default=None,
        help_text="JSON-serialized array of 3-element arrays, containing the index mappings and lengths of matches."
                  " E.g. [[i, j, n], ... ] where n is the match length, i starting index of the match in submission_a,"
                  " and j in submission_b.",
    )
    review = models.IntegerField(choices=settings.REVIEW_CHOICES, default=0)
    objects = ComparisonManager()

    class Meta:
        unique_together = ("submission_a", "submission_b")
        ordering = [
            "-similarity",
        ]

    @property
    def review_options(self):
        return settings.REVIEWS

    @property
    def review_name(self):
        return choice_name(settings.REVIEW_CHOICES, self.review)

    @property
    def review_class(self):
        return next(
            (m["class"] for m in settings.REVIEWS if m["value"] == self.review),
            "unknown",
        )

    def update_review(self, review):
        try:
            r = int(review)
            if choice_name(settings.REVIEW_CHOICES, r) != "unknown":
                self.review = r
                self.save()
                return True
        except ValueError:
            pass
        return False

    def __str__(self):
        c = (
            "template"
            if self.submission_b is None
            else "vs %s" % (self.submission_b.student.key)
        )
        return "%s/%s: %s %s similarity %.2f" % (
            self.submission_a.exercise.course.name,
            self.submission_a.exercise.name,
            self.submission_a.student.key,
            c,
            self.similarity,
        )


class TaskError(models.Model):
    """
    Fatal error during asynchronous task execution.
    """

    created = models.DateTimeField(auto_now_add=True)
    package = models.CharField(max_length=100, default='-empty-')
    namespace = models.CharField(max_length=200, default='-empty-')
    error_string = models.TextField()

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return "Failed task in package {}, occurred at {}, with error {}".format(
            self.package, self.created, self.error_string
        )
