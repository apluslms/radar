DEBUG = True
#SECRET_KEY = 'not a very secret key'
ADMINS = (
)
# NOTE: All other services define this in settings.py
ALLOWED_HOSTS = ["*"]

STATIC_ROOT = '/local/radar/static/'
MEDIA_ROOT = '/local/radar/media/'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'radar',
    },
}

PROVIDERS['a+'].update({'host': 'http://plus:8000'})

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': '/run/radar/django-cache',
    },
    "exercise_templates": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": "/run/radar/django_cache_exercises",
        "TIMEOUT": 3600,
        "OPTIONS": {
            "MAX_ENTRIES": 100,
        },
    },
}

#CELERY_BROKER_URL = "amqp://"
CELERY_RESULT_BACKEND = 'file:///var/celery/results'

LOGGING['loggers'].update({
    '': {
        'level': 'INFO',
        'handlers': ['debug_console'],
        'propagate': True,
    },
    #'django.db.backends': {
    #    'level': 'DEBUG',
    #},
})

# kate: space-indent on; indent-width 4;
# vim: set expandtab ts=4 sw=4:
