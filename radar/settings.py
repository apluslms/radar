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

ALLOWED_HOSTS = []
AUTH_LTI_LOGIN = {
    'ACCEPTED_ROLES': ['Instructor', 'TA'],
    'STAFF_ROLES': ['Instructor', 'TA']
}

AUTH_USER_MODEL = "accounts.RadarUser"

APP_NAME = "Radar"

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
    'accounts',
    'review',
    'aplus_client',
    'django_lti_login',
    'ltilogin',
)

MIDDLEWARE = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
)

# Short name and display name of available tokenizers.
TOKENIZER_CHOICES = (
    ("skip", "Skip"),
    ("scala", "Scala"),
    ("python", "Python"),
    ("js", "JavaScript"),
    ("html", "HTML"),
    ("css", "CSS"),
)
# Tokenizer functions and the separator string injected into the first line
# of each file.
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
    "js": {
        "tokenize": "tokenizer.javascript.tokenize",
        "separator": "/****** %s ******/"
    },
    "html": {
        "tokenize": "tokenizer.html.tokenize",
        "separator": "<!-- %s -->"
    },
    "css": {
        "tokenize": "tokenizer.css.tokenize",
        "separator": "/****** %s ******/"
    },
}

PROVIDER_CHOICES = (("a+", "A+"), ("filesystem", "File system"))
PROVIDERS = {
    "a+": {
        "hook": "provider.aplus.hook",
        "reload": "provider.aplus.reload",
        "get_submission_text": "data.aplus.get_submission_text",
        # Override these in local settings
        "host": "http://localhost:8000",
        "token": "asd123",
    },
    "filesystem": {
        "hook": "provider.filesystem.hook",
        "cron": "provider.filesystem.cron",
        "get_submission_text": "data.files.get_submission_text",
    },
}

REVIEW_CHOICES = (
    (-10, "False alert"),
    (0, "Unspecified match"),
    (1, "Approved plagiate"),
    (5, "Suspicious match"),
    (10, "Plagiate"),
)
REVIEWS = (
    {
        "value": REVIEW_CHOICES[4][0],
        "name": REVIEW_CHOICES[4][1],
        "class": "success"
    },
    {
        "value": REVIEW_CHOICES[0][0],
        "name": REVIEW_CHOICES[0][1],
        "class": "success"
    },
    {
        "value": REVIEW_CHOICES[1][0],
        "name": REVIEW_CHOICES[1][1],
        "class": "default"
    },
    {
        "value": REVIEW_CHOICES[2][0],
        "name": REVIEW_CHOICES[2][1],
        "class": "warning"
    },
    {
        "value": REVIEW_CHOICES[3][0],
        "name": REVIEW_CHOICES[3][1],
        "class": "danger"
    },
)

MATCH_ALGORITHM = "matcher.jplag.match"
#MATCH_ALGORITHM = "matcher.jplag_ext.match"
MATCH_STORE_MIN_SIMILARITY = 0.2
MATCH_STORE_MAX_COUNT = 10

SUBMISSION_VIEW_HEIGHT = 30
SUBMISSION_VIEW_WIDTH = 5

# Maximum size of the HTTP response content in bytes when
# requesting submission file contents from the provider.
SUBMISSION_BYTES_LIMIT = 10**6

# Parameters to stop matching submissions if an exercise gets too many similar submissions.
# If at least AUTO_PAUSE_COUNT submissions exist, and the average similarity
# of these submissions exceeds AUTO_PAUSE_MEAN, put the exercise of these submissions on pause.
AUTO_PAUSE_MEAN = 0.9
AUTO_PAUSE_COUNT = 50

ROOT_URLCONF = 'radar.urls'

WSGI_APPLICATION = 'radar.wsgi.application'

AUTHENTICATION_BACKENDS = [
    'django_lti_login.backends.LTIAuthBackend',
    'django.contrib.auth.backends.ModelBackend',
]

LOGIN_REDIRECT_URL = 'index'


# Database
# https://docs.djangoproject.com/en/1.7/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'APP_DIRS': True,
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

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
      'level': 'INFO',
      'handlers': ['email', 'console'],
      'propagate': True
    },
  },
}

# Celery
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_BROKER_URL = "amqp://localhost:5672"
CELERY_BEAT_SCHEDULE = {
    "match_all_unmatched_submissions": {
        "task": "provider.tasks.match_all_unmatched_submissions",
        "schedule": 60, # Match all submissions once per minute.
    }
}


from r_django_essentials.conf import update_settings_from_module

update_settings_from_module(__name__, "local_settings")
