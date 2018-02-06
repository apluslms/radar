from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class AplusClientConfig(AppConfig):
    name = 'aplus_client.django'
    label = 'aplus_client'
    verbose_name = _("Aplus client")
