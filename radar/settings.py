# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import os

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

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

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.memcached.MemcachedCache",
        "LOCATION": "127.0.0.1:11211",
    },
    # Exercise template sources are not stored in the database, but fetched from the provider API each time before the exercise settings view is rendered.
    # This cache stores the fetched templates for 1 hour.
    "exercise_templates": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": "/var/tmp/django_cache",
        "TIMEOUT": 3600,
        "OPTIONS": {
            "MAX_ENTRIES": 100,
        },
    },
}

# Short name and display name of available tokenizers.
TOKENIZER_CHOICES = (
    ("skip", "Skip"),
    ("scala", "Scala"),
    ("python", "Python"),
    ("js", "JavaScript (ECMA 2016)"),
    ("html", "HTML5"),
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
        # For creating new submissions that were POSTed from the provider
        "hook": "provider.aplus.hook",
        # Deletes all submissions and matches, then reloads everything from the API and compares all reloaded submissions
        "full_reload": "provider.aplus.reload",
        # Deletes matches, then compares all existing submissions
        "recompare": "provider.aplus.recompare",
        # Retrieves the contents of a submission from the provider API
        "get_submission_text": "data.aplus.get_submission_text",
        # Queues a read to the provider API that fetches all exercises in a course
        "async_api_read": "provider.aplus.async_api_read",
        # Override these in local settings
        "host": "http://localhost:8000",
        "token": "asd123",
    },
    # Obsolete and not implemented
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

MATCH_ALGORITHM = "matchlib.matchers.greedy_string_tiling"

# Weigths are obsolete
MATCH_ALGORITHMS = {
    "jplag_ext": {
        "description": "Greedy string tiling, longest matching substring",
        "callable": "matcher.jplag_ext.match",
        "tokenized_input": True,
        "weight": 1.0
    },
    "md5sum": {
        "description": "MD5 checksum of the submission source",
        "callable": None,
        "tokenized_input": False,
        "weight": 1.0
    },

    # # Example
    # "jplag": {
    #     # Reference to a known algorithm, or a one line explanation on how the algorithm computes the similarity
    #     "description": "Greedy string tiling, longest matching substring",
    #     # Python-importable dotted path to the function within the Django project
    #     "callable": "matcher.jplag.match",
    #     # True if the callable accepts tokenized strings as input (regular match algorithm).
    #     # False if the similarity is produced using some custom scheme that is hand coded (e.g. md5sum of the submission source, yielding binary similarity)
    #     "tokenized_input": True,
    #     # Decimal number that is multiplied with the output of the callable to produce the final similarity.
    #     "weight": 0.5
    # },
}

MATCH_STORE_MAX_COUNT = 10
# Minimum similarity for two submissions to be stored into the database as a Comparison instance
MATCH_STORE_MIN_SIMILARITY = 0.2
# Amount of float digits when serializing similarity
SIMILARITY_PRECISION = 3

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
LOGOUT_REDIRECT_URL = 'index'


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
# celery.chord tasks (used by matcher.tasks.match_submissions) are not supported with the RPC backend, therefore we use Memcached
CELERY_RESULT_BACKEND = "cache+memcached://127.0.0.1:11211/"

from r_django_essentials.conf import update_settings_with_file, update_secret_from_file

update_settings_with_file(__name__,
                          os.environ.get('RADAR_LOCAL_SETTINGS', 'local_settings'),
                          quiet='RADAR_LOCAL_SETTINGS' in os.environ)
update_secret_from_file(__name__, os.environ.get('RADAR_SECRET_KEY_FILE', 'secret_key'))
