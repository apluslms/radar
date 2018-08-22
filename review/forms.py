from django import forms
from django.conf import settings

# from data.files import put_text
from data.models import Comparison
from radar.config import tokenizer_config
from tokenizer.tokenizer import tokenize_source


class ExerciseForm(forms.Form):
    name = forms.CharField(label="Name", max_length=128)
    paused = forms.BooleanField(label="Pause matching submissions", required=False)

    def save(self, exercise):
        exercise.name = self.cleaned_data["name"]
        exercise.paused = self.cleaned_data["paused"]
        exercise.save()


class ExerciseTokenizerForm(forms.Form):
    tokenizer = forms.ChoiceField(label="Tokenizer type", choices=settings.TOKENIZER_CHOICES)
    minimum_match_tokens = forms.IntegerField(label="Minimum match tokens",
        help_text="Minimum number of tokens to consider a match")
    template = forms.CharField(label="Template code", widget=forms.Textarea, required=False,
        help_text="Anything to be excluded from the submission comparison")

    def save(self, exercise):
        new_tokenizer = self.cleaned_data["tokenizer"]
        exercise.override_tokenizer = new_tokenizer if new_tokenizer != exercise.course.tokenizer else None

        tokens, _ = tokenize_source(
            self.cleaned_data["template"],
            tokenizer_config(new_tokenizer)
        )
        if exercise.template_tokens != tokens:
            exercise.template_tokens = tokens

        new_min_match_tokens = self.cleaned_data["minimum_match_tokens"]

        exercise.override_minimum_match_tokens = (new_min_match_tokens
                if new_min_match_tokens != exercise.course.minimum_match_tokens
                else None)
        exercise.save()
