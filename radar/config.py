from django.conf import settings
from django.utils.module_loading import import_by_path
from django.core.exceptions import ImproperlyConfigured

class ConfigError(Exception):
    pass

def provider(course):
    if course.provider not in settings.PROVIDERS:
        raise ConfigError("Unknown course provider settings.")
    return settings.PROVIDERS[course.provider]

def tokenizer(exercise):
    if exercise.tokenizer not in settings.TOKENIZERS:
        raise ConfigError("Unknown exercise tokenizer settings.")
    return settings.TOKENIZERS[exercise.tokenizer]

def configured_function(config, key):
    if key not in config:
        raise ConfigError("Missing required configuration key: %s" % (key))
    return named_function(config[key])

def named_function(name):
    try:
        return import_by_path(name)
    except ImproperlyConfigured:
        raise ConfigError("Unknown function configured: %s" % name)
