try:
    import django
except ImportError:
    raise ImportError("aplus_client.django requires django and is only usful with it")

default_app_config = 'aplus_client.django.apps.AplusClientConfig'
