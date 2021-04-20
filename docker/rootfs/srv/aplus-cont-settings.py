DEBUG = True
#SECRET_KEY = 'not a very secret key'
ADMINS = (
)
#ALLOWED_HOSTS = ["*"]

STATIC_ROOT = '/local/aplus/static/'
MEDIA_ROOT = '/local/aplus/media/'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'aplus',
    },
}

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': '/run/aplus/django-cache',
    },
}

REMOTE_PAGE_HOSTS_MAP = {
    "grader:8080": "localhost:8080",
}
OVERRIDE_SUBMISSION_HOST = "http://plus:8000"

#CELERY_BROKER_URL = "amqp://"

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
