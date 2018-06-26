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
    key = URLKeyField(max_length=64, unique=True, help_text="Unique alphanumeric course instance id")
    name = models.CharField(max_length=128, help_text="Descriptive course name")
    provider = models.CharField(max_length=16, choices=settings.PROVIDER_CHOICES, help_text="Provider for submission data", default=settings.PROVIDER_CHOICES[0][0])
    tokenizer = models.CharField(max_length=16, choices=settings.TOKENIZER_CHOICES, help_text="Tokenizer for the submission contents", default=settings.TOKENIZER_CHOICES[0][0])
    minimum_match_tokens = models.IntegerField(default=15, help_text="Minimum number of tokens to consider a match")
    reviewers = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="courses", blank=True, help_text="Reviewers for match analysis")
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

    def all_comparisons(self, min_similarity):
        return (Comparison.objects
                    .filter(submission_a__exercise__course=self)
                    .filter(similarity__gte=min_similarity))

    def has_access(self, user):
        return user.is_staff or self.reviewers.filter(pk=user.pk).exists()

    def has_exercise(self, key_str):
        return self.exercises.filter(key=URLKeyField.safe_version(key_str)).count() > 0

    def get_exercise(self, key_str):
        exercise, _ = self.exercises.get_or_create(key=URLKeyField.safe_version(key_str))
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
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="exercises")
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
            .annotate(m=models.Max('max_similarity')).order_by('-m')\
            .values_list('m', flat=True)

    @property
    def submissions_max_similarity_json(self):
        return json.dumps(list(self.submissions_max_similarity))

    def comparison_results_max_similarity_with_function(self, similarity_function):
        """
        Return an iterator over query sets of all comparison results for all submissions of this exercise, where the similarity is computed with the given similarity function.
        """
        return (ComparisonResult.objects
                .filter(
                    comparison__submission_a=submission,
                    comparison__submission_b__isnull=False,
                    function=similarity_function)
                .aggregate(models.Max("similarity"))
                for submission in self.matched_submissions)

    def top_comparisons(self):
        max_list = (self.matched_submissions
                .values('student__id')
                .annotate(m=models.Max('max_similarity'))
                .order_by('-m')[:settings.SUBMISSION_VIEW_HEIGHT])
        return self._comparisons_by_submission(
            self.matched_submissions
            .filter(student__id=each['student__id'])
            .order_by('-max_similarity')
            .first().id
            for each in max_list
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
                "matches": list(
                    Comparison.objects
                    .exclude(submission_b__isnull=True)
                    .filter(models.Q(submission_a__id=s) | models.Q(submission_b__id=s))
                    .order_by("-similarity")
                    .select_related(
                        "submission_a",
                        "submission_b",
                        "submission_a__exercise",
                        "submission_a__student",
                        "submission_b__student"
                    )[:settings.SUBMISSION_VIEW_WIDTH]
                )
            })
        return comparisons

    def set_from_config(self, config):
        self.name = config["name"]
        self.key = config["exercise_key"]
        tokens, _ = tokenize_source(
            config["template_source"],
            tokenizer_config(config["tokenizer"])
        )
        # files.put_text(self, ".template", config["template"])
        self.template_tokens = tokens
        if config["tokenizer"] != self.course.tokenizer:
            self.override_tokenizer = config["tokenizer"]
        if config["minimum_match_tokens"] != self.course.minimum_match_tokens:
            self.override_minimum_match_tokens = config["minimum_match_tokens"]

    def clear_all_matches(self):
        Comparison.objects.clean_for_exercise(self)
        self.submissions.update(indexes_json=None, max_similarity=None)

    def clear_tokens_and_matches(self):
        self.submissions.update(tokens=None, indexes_json=None, max_similarity=None)

    def __str__(self):
        return "%s/%s (%s)" % (self.course.name, self.name, self.created)


# What's with the ForeignKey and unique_together with Course?
# Why not ManyToMany to Course?
class Student(models.Model):
    """
    Each submission includes a student key and student objects are created as needed.

    """
    created = models.DateTimeField(auto_now_add=True)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="students")
    key = URLKeyField(max_length=64, help_text="Alphanumeric student id")

    class Meta:
        unique_together = ("course", "key")
        ordering = ["course", "key"]

    def __str__(self):
        return "%s: %s (%s)" % (self.course.name, self.key, self.created)


class Submission(models.Model):
    """
    A submission for an exercise.

    """
    key = URLKeyField(max_length=64, unique=True, help_text="Alphanumeric unique submission id")
    created = models.DateTimeField(auto_now_add=True)
    exercise = models.ForeignKey(Exercise, on_delete=models.CASCADE, related_name="submissions")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="submissions")
    provider_url = models.CharField(max_length=256, blank=True, null=True, default=None)
    provider_submission_time = models.DateTimeField(blank=True, null=True, default=None)
    grade = models.FloatField(default=0.0)
    tokens = models.TextField(blank=True, null=True, default=None)
    source_checksum = models.TextField(blank=True, null=True, default=None,
            help_text="MD5 checksum of all characters in the submission source")
    indexes_json = models.TextField(blank=True, null=True, default=None)
    authored_token_count = models.IntegerField(blank=True, null=True, default=None)
    longest_authored_tile = models.IntegerField(blank=True, null=True, default=None)
    max_similarity = models.FloatField(db_index=True, blank=True, null=True, default=None,
            help_text="Maximum weighted average over all similarity scores computed by different similarity functions")

    @property
    def submissions_to_compare(self):
        return self.exercise.matched_submissions\
            .exclude(student=self.student)\
            .exclude(longest_authored_tile__lt=self.exercise.minimum_match_tokens)

    @property
    def template_comparison(self):
        return Comparison.objects.filter(submission_a=self, submission_b__isnull=True).first()

    def max_similarity_from_comparisons(self):
        """
        Return the maximum similarity (or default to 0) over all comparisons this submission participates in.
        """
        res = (Comparison.objects
                .filter(submission_a=self)
                .aggregate(models.Max("similarity")).get("similarity__max"))
        return res or 0

    def template_matches(self):
        ct = self.template_comparison
        if ct is None:
            raise FieldError("Template matches requested before matching a submission")
        return json.loads(ct.matches_json)

    def template_marks(self): # TODO understand what this does and document
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
        return ("%s/%s: %s grade=%.1f (created: %s)"
                % (self.exercise.course.name,
                   self.exercise.name,
                   self.student.key,
                   self.grade,
                   self.created)
                + (" (submitted: %s)" % self.provider_submission_time)
                  if self.provider_submission_time else "")


class ComparisonManager(models.Manager):

    def clean_for_exercise(self, exercise):
        self.filter(submission_a__exercise=exercise).delete()


class Comparison(models.Model):
    """
    Comparison of two submissions, with a resulting similarity score.
    When submission_b is null, the Comparison contains the result from comparison submission_a to an exercise template.
    """
    submission_a = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="+")
    submission_b = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="+", blank=True, null=True)
    similarity = models.FloatField(default=None, null=True,
            help_text="Similarity score resulting from the comparison of two submissions. This value should be used as an aggregate of the similarity scores produced by different similarity functions.")
    similarity_function = models.CharField(max_length=200,
            help_text="Name of the similarity function used to compute the similarity of this comparison")
    matches_json = models.TextField(blank=True, null=True, default=None)
    review = models.IntegerField(choices=settings.REVIEW_CHOICES, default=0)
    objects = ComparisonManager()

    class Meta:
        unique_together = ("submission_a", "submission_b", "similarity_function")
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

    @property
    def max_similarity(self):
        res = self.results.aggregate(models.Max("similarity")).get("similarity__max")
        return res or 0

    @property
    def avg_similarity(self):
        res = self.results.aggregate(models.Avg("similarity")).get("similarity__avg")
        return res or 0

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
