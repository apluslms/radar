"""
Django settings for radar project.

For more information on this file, see
https://docs.djangoproject.com/en/1.7/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.7/ref/settings/
"""

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import os
from django.conf.global_settings import LOGIN_REDIRECT_URL
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

TOKENIZERS = {
    "skip": { "name": "Skip", "cron": "tokenizer.skip.cron",
              "separator": "" },
    "scala": { "name": "Scala", "cron": "tokenizer.scala.cron",
              "separator": "/****** %s ******/" },
    "python": { "name": "Python", "cron": "tokenizer.python.cron",
               "separator": "###### %s ######" },
    "text": { "name": "Natural text", "cron": "tokenizer.text.cron",
             "separator": "###### %s ######", "lang_class": "" },
    "java": { "name": "Java", "cron": "tokenizer.java.cron",
             "separator": "/****** %s ******/" },
}

PROVIDERS = {   
    "a+": { "name": "A+",
           "hook": "provider.aplus.hook",
           "cron": "provider.aplus.cron",
           "host": "http://localhost:8000",
           "user": "root",
           "key": "4511004ec512bbcccbed7aa31d479a93fa039a72" },
    "filesystem": { "name": "File system",
                   "hook": "provider.filesystem.hook",
                   "cron": "provider.filesystem.cron" },
}

MATCH_ALGORITHM = "matcher.jplag.match"

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
                a[key] = merge_dict(a[key], b[key])
            else:
                a[key] = b[key]
    if "PROVIDERS_MERGE" in locals():
        merge_dict(PROVIDERS, PROVIDERS_MERGE)
except ImportError:
    pass
