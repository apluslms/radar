from django.apps import AppConfig


class RadarConfig(AppConfig):
    name = 'radar'
    verbose_name = 'Radar'

    def ready(self):
        # Load our receivers
        # This is important as receiver hooks are not connected otherwise.
        from . import receivers  # NOQA
