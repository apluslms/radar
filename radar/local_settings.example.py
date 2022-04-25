"""
Example of a deployment configuration
"""
DEBUG = False

ADMINS = [
    ("Admin Name", "name@example.com"),
]
SERVER_EMAIL = "Radar <radar@radar.example.com>"

ALLOWED_HOSTS = ["radar.example.com"]

PROVIDERS = {
    "a+": {
        "hook": "provider.aplus.hook",
        "full_reload": "provider.aplus.reload",
        "recompare": "provider.aplus.recompare",
        "async_api_read": "provider.aplus.async_api_read",
        "get_submission_text": "data.aplus.get_submission_text",
        # This has to be changed if used outside of Aalto University
        "host": "https://plus.cs.aalto.fi",
    },
}

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'radar'
    }
}

STATIC_ROOT = "static_root"

APLUS_AUTH_LOCAL = {
    "PRIVATE_KEY": open("/srv/radar/radar-private.pem", "r").read(),
    "PUBLIC_KEY": open("/srv/radar/radar-public.pem", "r").read(),
    "REMOTE_AUTHENTICATOR_UID": "aplus",
    "REMOTE_AUTHENTICATOR_KEY": """-----BEGIN PUBLIC KEY-----
xxxxxxxxxxxxxxxxxxxxx
-----END PUBLIC KEY-----""",
    "REMOTE_AUTHENTICATOR_URL": "https://plus.cs.aalto.fi/api/v2/get-token/",
    "DISABLE_JWT_SIGNING": False,
    "DISABLE_LOGIN_CHECKS": False,
}


CELERY_TASK_ROUTES = {
    # High latency due to network I/O, consumed by the celery_io worker,
    # OK to have concurrency > 1
    "provider.tasks.create_submission": {"queue": "io"},
    "provider.tasks.reload_exercise_submissions": {"queue": "io"},

    # Long running task, can take a few minutes. Should have its own worker to
    # avoid blocking celery_main, which consumes from the queue celery e.g. if
    # someone fetches configuration data from the A+ API, this is done with
    # celery_main. Also, possible race condition if user clicks rematch for an
    # exercise many times in succession -> do not use concurrency > 1
    "matcher.tasks.handle_match_results": {"queue": "db"},

    # Consumed by remote Kubernetes workers
    # https://github.com/apluslms/serve-gst-matchlib
    # "matchlib.tasks.*": {"queue": "gst_matchlib_tasks"},

    # If the remote worker is not working or not being used for other reasons
    # Consumed by a local worker
    "matchlib.tasks.*": {"queue": "gst_matchlib_tasks_local"},
}

CELERY_BEAT_SCHEDULE = {
    "update_all_similarity_graphs": {
        "task": "data.tasks.update_all_similarity_graphs",
        # Run every 30 minutes
        "schedule": 30 * 60,
    }
}

MATCH_STORE_MIN_SIMILARITY = 0.5
