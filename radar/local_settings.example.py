"""
Example of a deployment configuration
"""
DEBUG = False

ALLOWED_HOSTS = ["radar.example.com"]

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.memcached.MemcachedCache",
        "LOCATION": "127.0.0.1:11211",
    },
}

PROVIDERS = {
    "a+": {
        "hook": "provider.aplus.hook",
        "full_reload": "provider.aplus.reload",
        "recompare": "provider.aplus.recompare",
        "get_submission_text": "data.aplus.get_submission_text",
        "host": "https://plus.cs.hut.fi",
    },
}

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'radar'
    }
}

STATIC_ROOT = "static_root"

CELERY_TASK_ROUTES = {
    "provider.tasks.create_submission": {"queue": "io"},
    "matcher.tasks.handle_match_results": {"queue": "io"},
    # Consumed by remote Kubernetes workers
    # https://github.com/apluslms/serve-gst-matchlib
    "matchlib.tasks.match_to_others": {"queue": "gst_matchlib_tasks"},
    "matchlib.tasks.match_all_combinattions": {"queue": "gst_matchlib_tasks"},
}

CELERY_BEAT_SCHEDULE = {
    "update_all_similarity_graphs": {
        "task": "data.tasks.update_all_similarity_graphs",
        "schedule": 30 * 60, # Run every 30 minutes
    }
}

MATCH_STORE_MIN_SIMILARITY = 0.5
