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

        exercise.submissions.update(max_similarity=None)
        exercise.save()
        Comparison.objects.clean_for_exercise(exercise)



class ExerciseOneLineForm(forms.Form):
    exercise_key = forms.CharField(label="Key", max_length=64)
    name = forms.CharField(label="Name", max_length=128)
    paused = forms.BooleanField(label="Pause matching submissions", required=False)
    tokenizer = forms.ChoiceField(label="Tokenizer type", choices=settings.TOKENIZER_CHOICES)
    minimum_match_tokens = forms.IntegerField(label="Minimum match tokens",
        help_text="Minimum number of tokens to consider a match")
    template = forms.CharField(label="Template code", required=False,
        help_text="Anything to be excluded from the submission comparison",
        widget=forms.Textarea(attrs={"cols": 20, "rows": 2}))

    def save(self, exercise):
        exercise.name = self.cleaned_data["name"]
        exercise.paused = self.cleaned_data["paused"]

        (tokens, _) = tokenize_source(self.cleaned_data["template"], tokenizer_config(self.cleaned_data["tokenizer"]))
        # put_text(exercise, ".template", self.cleaned_data["template"])
        exercise.template_tokens = tokens

        if self.cleaned_data["tokenizer"] == exercise.course.tokenizer:
            exercise.override_tokenizer = None
        else:
            exercise.override_tokenizer = self.cleaned_data["tokenizer"]

        if self.cleaned_data["minimum_match_tokens"] == exercise.course.minimum_match_tokens:
            exercise.override_minimum_match_tokens = None
        else:
            exercise.override_minimum_match_tokens = self.cleaned_data["minimum_match_tokens"]
        exercise.save()

        Comparison.objects.clean_for_exercise(exercise)
        exercise.clear_tokens_and_matches()

ExerciseOneLineFormSet = forms.formset_factory(ExerciseOneLineForm, extra=0)
