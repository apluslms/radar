from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string


class ConfigError(Exception):
    pass

def choice_name(choices, name):
    return next((c[1] for c in choices if c[0] == name), "unknown")

def provider_config(key):
    if key not in settings.PROVIDERS:
        raise ConfigError("Unknown provider settings.")
    return settings.PROVIDERS[key]

def tokenizer_config(key):
    if key not in settings.TOKENIZERS:
        raise ConfigError("Unknown tokenizer settings.")
    return settings.TOKENIZERS[key]

def configured_function(config, key):
    if key not in config:
        raise ConfigError("Missing required configuration key: %s" % (key))
    return named_function(config[key])

def named_function(name):
    try:
        return import_string(name)
    except ImproperlyConfigured as e:
        raise e
        #raise ConfigError("Unknown function configured: %s" % name)
