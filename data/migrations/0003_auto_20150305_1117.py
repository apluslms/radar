# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('data', '0002_auto_20150222_1829'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='exercise',
            options={'ordering': ['course', 'name', 'created']},
        ),
        migrations.RemoveField(
            model_name='providerqueue',
            name='processed',
        ),
        migrations.AddField(
            model_name='submission',
            name='provider_url',
            field=models.CharField(null=True, blank=True, default=None, max_length=256),
            preserve_default=True,
        ),
    ]
