"""
Django settings for radar project.

For more information on this file, see
https://docs.djangoproject.com/en/1.7/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.7/ref/settings/
"""

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import os

BASE_DIR = os.path.dirname(os.path.dirname(__file__))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.7/howto/deployment/checklist/

#ADMINS = (("Teemu", "teemu.t.lehtinen@aalto.fi"),)

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'r#=r)@i3iucw1tak*3(!h8une%=r7-rif63)7f(5(gm+-@^-)0'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

TEMPLATE_DEBUG = True

ALLOWED_HOSTS = []


# Application definition

INSTALLED_APPS = (
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'bootstrapform',
    'data',
    'review',
)

MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
)

TOKENIZER_CHOICES = (("skip", "Skip"), ("scala", "Scala"))
TOKENIZERS = {
    "skip": {
        "tokenize": "tokenizer.skip.tokenize",
        "separator": "###### %s ######"
    },
    "scala": {
        "tokenize": "tokenizer.scala.tokenize",
        "separator": "/****** %s ******/"
    },
    "python": {
        "tokenize": "tokenizer.python.tokenize", 
        "separator": "###### %s ######"
    },
    "text": {
        "tokenize": "tokenizer.text.tokenize",
        "separator": "###### %s ######"
    },
    "java": {
        "tokenize": "tokenizer.java.tokenize",
        "separator": "/****** %s ******/"
    },
}

PROVIDER_CHOICES = (("a+", "A+"), ("filesystem", "File system"))
PROVIDERS = {   
    "a+": {
        "hook": "provider.aplus.hook",
        "cron": "provider.aplus.cron",
        "reload": "provider.aplus.reload",
        "host": "http://localhost:8000",
        "user": "root",
        "key": "4511004ec512bbcccbed7aa31d479a93fa039a72",
    },
    "filesystem": {
        "hook": "provider.filesystem.hook",
        "cron": "provider.filesystem.cron",
    },
}

REVIEW_CHOICES = ((-10, "False alert"), (0, "Unspecified match"), (5, "Suspicious match"), (10, "Plagiate"))
REVIEWS = (
    { "value": REVIEW_CHOICES[0][0], "name": REVIEW_CHOICES[0][1], "class": "success" },
    { "value": REVIEW_CHOICES[1][0], "name": REVIEW_CHOICES[1][1], "class": "default" },
    { "value": REVIEW_CHOICES[2][0], "name": REVIEW_CHOICES[2][1], "class": "warning" },
    { "value": REVIEW_CHOICES[3][0], "name": REVIEW_CHOICES[3][1], "class": "danger" },
)

MATCH_ALGORITHM = "matcher.jplag.match"
MATCH_STORE_MIN_SIMILARITY = 0.2
MATCH_STORE_MAX_COUNT = 20

MAX_JSON_COMPARISONS = 300
CRON_STOP_SECONDS = 120

ROOT_URLCONF = 'radar.urls'

WSGI_APPLICATION = 'radar.wsgi.application'

LOGIN_REDIRECT_URL = 'index'


# Database
# https://docs.djangoproject.com/en/1.7/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

# Internationalization
# https://docs.djangoproject.com/en/1.7/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.7/howto/static-files/

STATIC_URL = '/static/'

# Add project level templates and static files
TEMPLATE_DIRS = (os.path.join(BASE_DIR, 'templates'),)
STATICFILES_DIRS = (os.path.join(BASE_DIR, 'static'),)

# Directory to store all the submitted files.
SUBMISSION_DIRECTORY = os.path.join(BASE_DIR, "submission_files")


LOGGING = {
  'version': 1,
  'disable_existing_loggers': False,
  'formatters': {
    'verbose': {
      'format': '[%(asctime)s: %(levelname)s/%(module)s] %(message)s'
    },
  },
  'handlers': {
    'console': {
      'level': 'DEBUG',
      'class': 'logging.StreamHandler',
      'stream': 'ext://sys.stdout',
      'formatter': 'verbose',
    },
    'email': {
      'level': 'ERROR',
      'class': 'django.utils.log.AdminEmailHandler',
    },
  },
  'loggers': {
    'radar': {
      'level': 'DEBUG',
      'handlers': ['email', 'console'],
      'propagate': True
    },
  },
}

try:
    from local_settings import *
    def merge_dict(a, b):
        for key in b:
            if isinstance(b[key], dict) and key in a and isinstance(a[key], dict):
                merge_dict(a[key], b[key])
            else:
                a[key] = b[key]
    for var in ["PROVIDERS_MERGE",]:
        if var in locals():
            merge_dict(PROVIDERS, locals()[var])
except ImportError:
    pass
