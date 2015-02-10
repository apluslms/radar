


import logging
import re

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.aggregates import Avg
from django.utils.encoding import python_2_unicode_compatible


logger = logging.getLogger("radar.model")


def _make_choices(settings_value):
    choices = []
    for key in settings_value.keys():
        choices.append((key, settings_value[key]["name"]))
    return choices


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
    name = URLKeyField(max_length=64, unique=True, help_text="Unique alphanumeric course instance id")
    provider = models.CharField(max_length=16, choices=_make_choices(settings.PROVIDERS), help_text="Provider for submission data", default=next(iter(settings.PROVIDERS)))
    tokenizer = models.CharField(max_length=16, choices=_make_choices(settings.TOKENIZERS), help_text="Tokenizer for the submission contents", default=next(iter(settings.TOKENIZERS)))
    minimum_match_tokens = models.IntegerField(default=15, help_text="Minimum number of tokens to consider a match")
    tolerance = models.FloatField(default=0.4, help_text="Automatically hide matches that this ratio of submissions have in common")
    reviewers = models.ManyToManyField(User, blank=True, null=True, help_text="Reviewers for match analysis")
    archived = models.BooleanField(db_index=True, default=False)
    objects = CourseManager()

    class Meta:
        ordering = ["-created"]

    @property
    def provider_name(self):
        return settings.PROVIDERS[self.provider]["name"]

    @property    
    def tokenizer_name(self):
        return settings.TOKENIZERS[self.tokenizer]["name"]

    def has_access(self, user):
        return user.is_staff or self.reviewers.filter(pk=user.pk).exists()

    def get_exercise(self, name):
        exercise, _ = self.exercises.get_or_create(name=URLKeyField.safe_version(name))
        return exercise

    def get_student(self, name):
        student, _ = self.students.get_or_create(name=URLKeyField.safe_version(name))
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
    name = URLKeyField(max_length=64, help_text="Alphanumeric exercise id")
    override_tokenizer = models.CharField(max_length=8, choices=_make_choices(settings.TOKENIZERS), blank=True, null=True)
    override_minimum_match_tokens = models.IntegerField(blank=True, null=True)
    override_tolerance = models.FloatField(blank=True, null=True)

    class Meta:
        unique_together = ("course", "name")
        ordering = ["course", "name", "created"]

    @property
    def tokenizer(self):
        return self.override_tokenizer if self.override_tokenizer is not None else self.course.tokenizer

    @property
    def minimum_match_tokens(self):
        return self.override_minimum_match_tokens if self.override_minimum_match_tokens is not None else self.course.minimum_match_tokens

    @property
    def tolerance(self):
        return self.override_tolerance if self.override_tolerance is not None else self.course.tolerance

    @property
    def size(self):
        if not hasattr(self, "_size"):
            self._size = Submission.objects.filter(exercise=self).values("student").distinct().count()
        return self._size
    
    @property
    def active_limit(self):
        if not hasattr(self, "_limit"):
            self._limit = int(self.size * self.tolerance)
        return self._limit
    
    def active_groups(self):
        return self.match_groups.filter(hide=False, size__lt=self.active_limit).order_by("-size")
    
    def hidden_groups(self):
        return self.match_groups.exclude(hide=False, size__lt=self.active_limit).order_by("hide", "size")

    def __str__(self):
        return "%s/%s (%s)" % (self.course.name, self.name, self.created)


@python_2_unicode_compatible
class Student(models.Model):
    """
    Each submission includes a student key and student objects are created as needed.
    
    """
    created = models.DateTimeField(auto_now_add=True)
    course = models.ForeignKey(Course, related_name="students")
    name = URLKeyField(max_length=64, help_text="Alphanumeric student id")

    class Meta:
        unique_together = ("course", "name")
        ordering = ["course", "name", "created"]

    def __str__(self):
        return "%s: %s (%s)" % (self.course.name, self.name, self.created)


@python_2_unicode_compatible
class Submission(models.Model):
    """
    A submission for an exercise.
    
    """
    created = models.DateTimeField(auto_now_add=True)
    exercise = models.ForeignKey(Exercise, related_name="submissions")
    student = models.ForeignKey(Student, related_name="submissions")
    grade = models.FloatField(default=0.0)
    tokens = models.TextField(blank=True, null=True, default=None)
    token_positions = models.TextField(blank=True, null=True, default=None)
    matching_finished = models.BooleanField(db_index=True, default=False)

    def __str__(self):
        return "%s/%s: %s grade=%.1f (%s)" % (self.exercise.course.name, self.exercise.name, self.student.name, self.grade, self.created)


class MatchGroupManager(models.Manager):

    def find_group(self, exercise, tokens):
        for group in self.filter(exercise=exercise):
            if tokens in group.tokens:
                return group
            if group.tokens in tokens:
                group.tokens = tokens
                group.save()
                logger.debug("Match group expanded, length %d", len(tokens))
                return group
        group = MatchGroup(exercise=exercise, tokens=tokens)
        group.save()
        logger.debug("New match group, length %d", len(tokens))
        return group


@python_2_unicode_compatible
class MatchGroup(models.Model):
    """
    Groups common matches together.
    
    """
    exercise = models.ForeignKey(Exercise, related_name="match_groups")
    tokens = models.TextField()
    size = models.IntegerField(db_index=True, default=0)
    average_grade = models.FloatField(default=0.0)
    hide = models.BooleanField(db_index=True, default=False)
    plagiate = models.BooleanField(default=False)
    objects = MatchGroupManager()

    def add_match(self, submission, beg, length):
        if self.matches.filter(submission=submission, first_token=beg, length=length).exists():
            return
        end = beg + length
        for m in self.matches.filter(submission=submission):
            if m.overlaps(beg, end):
                logger.debug("Forget overlapping match: %d-%d", m.first_token, m.last_token)
                beg = min(beg, m.first_token)
                end = max(end, m.last_token)
                m.delete()
        logger.debug("Record match: %d-%d", beg, end)
        self.matches.create(submission=submission, first_token=beg, length=(end - beg))

    def recalculate(self):
        for compare in MatchGroup.objects.filter(exercise=self.exercise).exclude(pk=self.pk):
            if compare.tokens in self.tokens:
                logger.debug("Join group, length %d", len(compare.tokens))
                compare.matches.update(group=self)
                compare.delete()
        # TODO confirm this filter works
        submissions = Submission.objects.filter(matches__group=self)
        self.size = submissions.values("student").distinct().count()
        self.average_grade = submissions.aggregate(a=Avg("grade"))["a"]
        self.save()
        logger.debug("Updated group %s", self)

    def __str__(self):
        return "%s/%s: %d size=%d average_grade=%1.f" % (self.exercise.course.name, self.exercise.name, self.id, self.size, self.average_grade)


class MatchManager(models.Manager):

    def record(self, submission_a, submission_b, match):
        """
        Record a match between two submissions.
        
        """
        tokens = submission_a.tokens[match.a:match.a_end]
        group = MatchGroup.objects.find_group(submission_a.exercise, tokens)
        group.add_match(submission_a, match.a, match.length)
        group.add_match(submission_b, match.b, match.length)
        group.recalculate()


@python_2_unicode_compatible
class Match(models.Model):
    """
    Records matches in match groups.
    
    """
    submission = models.ForeignKey(Submission, related_name="matches")
    group = models.ForeignKey(MatchGroup, related_name="matches")
    first_token = models.IntegerField()
    length = models.IntegerField()
    objects = MatchManager()

    @property
    def last_token(self):
        return self.first_token + self.length

    @property
    def is_active(self):
        return self.group.hide == False and self.group.size < self.submission.exercise.active_limit

    def overlaps(self, beg, end):
        return (beg >= self.first_token and beg <= self.last_token) \
            or (end >= self.first_token and end <= self.last_token) \
            or (beg < self.first_token and end > self.last_token)

    def __str__(self):
        return "%s/%s: %s group=%d length=%d" % (self.submission.exercise.course.name, self.submission.exercise.name, self.submission.student.name, self.group.id, self.length)


@python_2_unicode_compatible
class ProviderQueue(models.Model):
    """
    Queues a submission for provider. Some providers can not create
    a submission object based on the hook alone.
    
    """
    created = models.DateTimeField(auto_now_add=True)
    course = models.ForeignKey(Course, related_name="+")
    data = models.CharField(max_length=128)
    processed = models.BooleanField(db_index=True, default=False)

    def __str__(self):
        return "%s (%s)" % (self.course.name, self.created)
