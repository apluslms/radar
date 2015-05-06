from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from django.core.exceptions import ValidationError
from oauthlib.oauth1 import RequestValidator

KEY_LENGTH = 6, 128

@python_2_unicode_compatible
class LTIClient(models.Model):
    """
    A client service from which users can login to this service.
    
    """
    key = models.CharField(max_length=128, help_text='LTI client service key')
    secret = models.CharField(max_length=128, help_text='LTI client service secret')
    description = models.TextField()

    class Meta:
        ordering = ['key']

    def clean_key(self):
        validator = RequestValidator()
        self._clean_word(self.key, validator.safe_characters, KEY_LENGTH)

    def clean_secret(self):
        self._clean_word(self.secret, None, KEY_LENGTH)

    def _clean_word(self, word, charset, length):
        if charset is not None and set(word) > charset:
            raise ValidationError('Only following characters are allowed: %s' % (charset))
        minlen, maxlen = length
        if len(word) < minlen:
            raise ValidationError('Minimum length is %d.' % (minlen))
        if len(word) > maxlen:
            raise ValidationError('Maximum length is %d.' % (maxlen))

    def __str__(self):
        return "%s" % (self.key)
