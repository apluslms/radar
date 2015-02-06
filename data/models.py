import re

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.aggregates import Avg

from matcher.tokens import overlap


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
    
    class Meta:
        ordering = ["-created"]
    
    def get_exercise(self, name):
        exercise, _ = self.exercises.get_or_create(name=URLKeyField.safe_version(name))
        return exercise
    
    def get_student(self, name):
        student, _ = self.students.get_or_create(name=URLKeyField.safe_version(name))
        return student
    
    def __unicode__(self):
        return "%s (%s)" % (self.name, self.created)


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
    
    def __unicode__(self):
        return "%s/%s (%s)" % (self.course.name, self.name, self.created)


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
        
    def __unicode__(self):
        return "%s: %s (%s)" % (self.course.name, self.name, self.created)


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
    
    def __unicode__(self):
        return "%s/%s: %s grade=%.1f (%s)" % (self.exercise.course.name, self.exercise.name, self.student.name, self.grade, self.created)


class MatchGroupManager(models.Manager):
    
    def _find_group(self, exercise, tokens):
        for group in self.filter(exercise=exercise):
            if tokens in group.tokens:
                return group
            if group.tokens in tokens:
                group.tokens = tokens
                group.save()
                return group
        group = MatchGroup(exercise=exercise, tokens=tokens)
        group.save()
        return group
    
    def _join_included(self, group):
        for compare in self.filter(exercise=group.exercise).exclude(pk=group.pk):
            if compare.tokens in group.tokens:
                compare.matches.update(group=group)
                compare.delete()


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

    def _recalculate(self):
        MatchGroup.objects._join_included(self)
        self.size = len(self.matches)
        self.average_grade = self.matches.submission.aggregate(a=Avg("grade"))["a"]
        self.save()
    
    def __unicode__(self):
        return "%s/%s: size=%d average_grade=%1.f" % (self.exercise.course.name, self.exercise.name, self.id, self.size, self.average_grade)


class MatchManager(models.Manager):

    def record(self, submission_a, first_token_a, submission_b, first_token_b, length):
        """
        Record a match between two submissions.
        
        """
        tokens = submission_a.tokens[first_token_a:(first_token_a + length)]
        group = MatchGroup.objects._find_group(submission_a.exercise, tokens)
        self._add_to_group(submission_a, group, first_token_a, length)
        self._add_to_group(submission_b, group, first_token_b, length)
        group._recalculate()
    
    def _add_to_group(self, submission, group, first_token, length):
        beg = first_token
        end = first_token + length
        for match in self.filter(submission=submission, group=group):
            terminals = overlap(beg, end, match.first_token, match.first_token + match.length)
            if terminals is not None:
                (beg, end) = terminals
                match.delete()
        match = Match(submission=submission, group=group, first_token=beg, length=end - beg)
        match.save()


class Match(models.Model):
    """
    Records matches in match groups.
    
    """
    submission = models.ForeignKey(Submission, related_name="matches")
    group = models.ForeignKey(MatchGroup, related_name="matches")
    first_token = models.IntegerField()
    length = models.IntegerField()
    objects = MatchManager()
    
    def __unicode__(self):
        return "%s/%s: %s group=%d length=%d" % (self.submission.exercise.course.name, self.submission.exercise.name, self.submission.student.name, self.group.id, self.length)


class ProviderQueue(models.Model):
    """
    Queues a submission for provider. Some providers can not create
    a submission object based on the hook alone.
    
    """
    created = models.DateTimeField(auto_now_add=True)
    course = models.ForeignKey(Course, related_name="+")
    data = models.CharField(max_length=128)
    processed = models.BooleanField(db_index=True, default=False)

    def __unicode__(self):
        return "%s (%s)" % (self.course.name, self.created)
