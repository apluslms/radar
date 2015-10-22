from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError, FieldError
from django.db import models
from django.utils.encoding import python_2_unicode_compatible
import json
import logging
import re

from radar.config import choice_name


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


class CourseManager(models.Manager):

    def get_available_courses(self, user):
        if user.is_staff:
            return self.all()
        return self.filter(reviewers=user)


@python_2_unicode_compatible
class Course(models.Model):
    """
    A course can receive submissions.

    """
    created = models.DateTimeField(auto_now_add=True)
    key = URLKeyField(max_length=64, unique=True, help_text="Unique alphanumeric course instance id")
    name = models.CharField(max_length=128, help_text="Descriptive course name")
    provider = models.CharField(max_length=16, choices=settings.PROVIDER_CHOICES, help_text="Provider for submission data", default=settings.PROVIDER_CHOICES[0][0])
    tokenizer = models.CharField(max_length=16, choices=settings.TOKENIZER_CHOICES, help_text="Tokenizer for the submission contents", default=settings.TOKENIZER_CHOICES[0][0])
    minimum_match_tokens = models.IntegerField(default=15, help_text="Minimum number of tokens to consider a match")
    reviewers = models.ManyToManyField(User, blank=True, null=True, help_text="Reviewers for match analysis")
    archived = models.BooleanField(db_index=True, default=False)
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
        return Submission.objects.filter(exercise__course=self).exclude(max_similarity__isnull=True)

    @property
    def marked_submissions(self):
        return Submission.objects.filter(exercise__course=self, comparison__review__gte=5)

    def has_access(self, user):
        return user.is_staff or self.reviewers.filter(pk=user.pk).exists()

    def get_exercise(self, key_str):
        exercise, created = self.exercises.get_or_create(key=URLKeyField.safe_version(key_str))
        if created:
            exercise.name = exercise.key
            exercise.save()
        return exercise

    def get_student(self, key_str):
        student, _ = self.students.get_or_create(key=URLKeyField.safe_version(key_str))
        return student

    def __str__(self):
        return "%s (%s)" % (self.name, self.created)


@python_2_unicode_compatible
class Exercise(models.Model):
    """
    Each submission includes an exercise key and exercise objects are created as needed.

    """
    created = models.DateTimeField(auto_now_add=True)
    course = models.ForeignKey(Course, related_name="exercises")
    key = URLKeyField(max_length=64, help_text="Alphanumeric exercise id")
    name = models.CharField(max_length=128, default="unknown", help_text="Descriptive exercise name")
    override_tokenizer = models.CharField(max_length=8, choices=settings.TOKENIZER_CHOICES, blank=True, null=True)
    override_minimum_match_tokens = models.IntegerField(blank=True, null=True)
    template_tokens = models.TextField(blank=True, default="")
    paused = models.BooleanField(default=False)

    class Meta:
        unique_together = ("course", "key")
        ordering = ["course", "name", "created"]

    @property
    def tokenizer(self):
        return self.override_tokenizer if self.override_tokenizer is not None else self.course.tokenizer

    @property
    def tokenizer_name(self):
        return choice_name(settings.TOKENIZER_CHOICES, self.tokenizer)

    @property
    def minimum_match_tokens(self):
        return self.override_minimum_match_tokens if self.override_minimum_match_tokens is not None else self.course.minimum_match_tokens

    @property
    def template_length(self):
        return len(self.template_tokens)

    @property
    def student_count(self):
        return Submission.objects.filter(exercise=self).values("student").distinct().count()

    @property
    def unmatched_submissions(self):
        return self.submissions.filter(max_similarity__isnull=True)

    @property
    def matched_submissions(self):
        return self.submissions.exclude(max_similarity__isnull=True)

    @property
    def submissions_max_similarity(self):
        return self.matched_submissions.values("student__id")\
            .annotate(max_similarity=models.Max('max_similarity'))\
            .order_by('max_similarity')\
            .values_list('max_similarity', flat=True)

    @property
    def submissions_max_similarity_json(self):
        return json.dumps(list(self.submissions_max_similarity))

    def top_comparisons(self):
        return self._comparisons_by_submission(
            self.matched_submissions\
                .values("student__id")\
                .annotate(max_similarity=models.Max('max_similarity'))\
                .order_by('-max_similarity')\
                .values_list('id', flat=True)\
                [:settings.SUBMISSION_VIEW_HEIGHT]
        )

    def comparisons_for_student(self, student):
        return self._comparisons_by_submission(
            self.matched_submissions\
                .filter(student=student)\
                .order_by("created")\
                .values_list("id", flat=True)
        )

    def _comparisons_by_submission(self, submissions):
        comparisons = []
        for s in submissions:
            comparisons.append({
                "submission_id": s,
                "matches": list(Comparison.objects\
                    .exclude(submission_b__isnull=True)\
                    .filter(models.Q(submission_a=s) | models.Q(submission_b=s))\
                    .order_by("-similarity")\
                    .select_related("submission_a", "submission_b",
                        "submission_a__exercise", "submission_a__student",
                        "submission_b__student")[:settings.SUBMISSION_VIEW_WIDTH]
                )
            })
        return comparisons

    def clear_tokens_and_matches(self):
        self.comparisons.delete()
        self.submissions.update(tokens=None, indexes_json=None, max_similarity=None)

    def __str__(self):
        return "%s/%s (%s)" % (self.course.name, self.name, self.created)


@python_2_unicode_compatible
class Student(models.Model):
    """
    Each submission includes a student key and student objects are created as needed.

    """
    created = models.DateTimeField(auto_now_add=True)
    course = models.ForeignKey(Course, related_name="students")
    key = URLKeyField(max_length=64, help_text="Alphanumeric student id")

    class Meta:
        unique_together = ("course", "key")
        ordering = ["course", "key"]

    def __str__(self):
        return "%s: %s (%s)" % (self.course.name, self.key, self.created)


@python_2_unicode_compatible
class Submission(models.Model):
    """
    A submission for an exercise.

    """
    created = models.DateTimeField(auto_now_add=True)
    exercise = models.ForeignKey(Exercise, related_name="submissions")
    student = models.ForeignKey(Student, related_name="submissions")
    provider_url = models.CharField(max_length=256, blank=True, null=True, default=None)
    grade = models.FloatField(default=0.0)
    tokens = models.TextField(blank=True, null=True, default=None)
    indexes_json = models.TextField(blank=True, null=True, default=None)
    authored_token_count = models.IntegerField(blank=True, null=True, default=None)
    longest_authored_tile = models.IntegerField(blank=True, null=True, default=None)
    max_similarity = models.FloatField(db_index=True, blank=True, null=True, default=None)

    @property
    def submissions_to_compare(self):
        return self.exercise.matched_submissions\
            .exclude(student=self.student)\
            .exclude(longest_authored_tile__lt=self.exercise.minimum_match_tokens)

    @property
    def template_comparison(self):
        return Comparison.objects.filter(submission_a=self, submission_b__isnull=True).first()

    def template_matches(self):
        ct = self.template_comparison
        if ct is None:
            raise FieldError("Template matches requested before matching a submission")
        return json.loads(ct.matches_json)

    def template_marks(self):
        token_count = len(self.tokens)
        marks = [ False ] * token_count
        authored = token_count
        longest_tile = 0
        s = 0
        for m in self.template_matches():
            for i in range(0, m[2]):
                marks[m[0] + i] = True
            authored -= m[2]
            if m[0] - s > longest_tile:
                longest_tile = m[0] - s
            s = m[0] + m[2]
        if token_count - s > longest_tile:
            longest_tile = token_count - s
        return marks, authored, longest_tile

    def __str__(self):
        return "%s/%s: %s grade=%.1f (%s)" % (self.exercise.course.name, self.exercise.name, self.student.key, self.grade, self.created)


@python_2_unicode_compatible
class Comparison(models.Model):
    """
    Compares two submissions.

    """
    submission_a = models.ForeignKey(Submission, related_name="+")
    submission_b = models.ForeignKey(Submission, related_name="+", blank=True, null=True)
    similarity = models.FloatField(default=0.0)
    matches_json = models.TextField(blank=True, null=True, default=None)
    review = models.IntegerField(choices=settings.REVIEW_CHOICES, default=0)

    class Meta:
        unique_together = ("submission_a", "submission_b")
        ordering = ["-similarity", ]

    @property
    def review_options(self):
        return settings.REVIEWS

    @property
    def review_name(self):
        return choice_name(settings.REVIEW_CHOICES, self.review)

    @property
    def review_class(self):
        return next((m["class"] for m in settings.REVIEWS if m["value"] == self.review), "unknown")

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
        c = "template" if self.submission_b is None else "vs %s" % (self.submission_b.student.key)
        return "%s/%s: %s %s similarity %.2f" % (self.submission_a.exercise.course.name, self.submission_a.exercise.name, self.submission_a.student.key, c, self.similarity)


@python_2_unicode_compatible
class ProviderQueue(models.Model):
    """
    Queues a submission for provider. Some providers can not create
    a submission object based on the hook alone.

    """
    created = models.DateTimeField(auto_now_add=True)
    course = models.ForeignKey(Course, related_name="+")
    data = models.CharField(max_length=128)

    def __str__(self):
        return "%s (%s)" % (self.course.name, self.created)
