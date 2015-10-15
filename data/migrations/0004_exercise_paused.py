# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('data', '0003_auto_20150305_1117'),
    ]

    operations = [
        migrations.AddField(
            model_name='exercise',
            name='paused',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
    ]
