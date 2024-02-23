from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _

from aplus_client.client import AplusTokenClient
from aplus_client.django.models import ApiNamespace


class Token(models.Model):
    user = models.ForeignKey(
        'RadarUser', on_delete=models.CASCADE, related_name="tokens"
    )
    site = models.ForeignKey(ApiNamespace, on_delete=models.PROTECT)
    token = models.CharField(_("API token"), max_length=40, null=True)

    class Meta:
        unique_together = ('user', 'site')


class RadarUser(AbstractUser):
    def get_api_client(self, site):
        try:
            token = self.tokens.get(site=site)
        except Token.DoesNotExist:
            return None
        return AplusTokenClient(token.token)

    def has_api_token(self, site):
        return self.tokens.filter(site=site).exists()

    def add_api_token(self, token, site):
        if not self.has_api_token(site):
            Token.objects.create(user=self, site=site, token=token)

    def __str__(self):
        return self.email
