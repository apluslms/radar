"""This file is executed by service-base -> django-migrate.sh"""
import os
import sys
import django
from datetime import timedelta
from django.utils import timezone

def create_default_users():
    from accounts.models import RadarUser

    ur = RadarUser.objects.create(
        username="root",
        email="root@localhost.invalid",
        first_name="Ruth",
        last_name="Robinson",
        is_superuser=True,
        is_staff=True,
    )
    ur.set_password("root")
    ur.save()


if __name__ == '__main__':
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "radar.settings")
    sys.path.insert(0, '')
    django.setup()

    create_default_users()
