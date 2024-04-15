from django import forms
from django.conf import settings

from radar.config import tokenizer_config
from tokenizer.tokenizer import tokenize_source


class DeleteExerciseFrom(forms.Form):
    # Required is false to enable deletion of exercises with empty names
    name = forms.CharField(label="Name", max_length=128, required=False)


class ExerciseForm(forms.Form):
    name = forms.CharField(label="Name", max_length=128)
    paused = forms.BooleanField(label="Pause matching submissions", required=False)
    tokenizer = forms.ChoiceField(
        label="Tokenizer type", choices=settings.TOKENIZER_CHOICES
    )
    minimum_match_tokens = forms.IntegerField(
        label="Minimum match tokens",
        help_text="Minimum number of tokens to consider a match",
    )

    def save(self, exercise):
        exercise.name = self.cleaned_data["name"]
        exercise.paused = self.cleaned_data["paused"]
        new_tokenizer = self.cleaned_data["tokenizer"]
        if new_tokenizer != exercise.course.tokenizer:
            exercise.override_tokenizer = new_tokenizer
        new_min_match_tokens = self.cleaned_data["minimum_match_tokens"]
        if new_min_match_tokens != exercise.course.minimum_match_tokens:
            exercise.override_minimum_match_tokens = new_min_match_tokens
        exercise.save()


class ExerciseTemplateForm(forms.Form):
    template = forms.CharField(
        label="Template code",
        widget=forms.Textarea,
        required=False,
        help_text="Anything to be excluded from the submission comparison",
    )

    def save(self, exercise):
        submitted_template = self.cleaned_data["template"]
        tokenizer = exercise.override_tokenizer or exercise.course.tokenizer
        tokens, _ = tokenize_source(submitted_template, tokenizer_config(tokenizer))
        if exercise.template_tokens != tokens:
            exercise.template_tokens = tokens
            exercise.template_text = submitted_template
        exercise.save()
