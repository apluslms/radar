# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('data', '0004_exercise_paused'),
    ]

    operations = [
        migrations.AddField(
            model_name='submission',
            name='longest_authored_tile',
            field=models.IntegerField(blank=True, null=True, default=None),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='comparison',
            name='review',
            field=models.IntegerField(choices=[(-10, 'False alert'), (0, 'Unspecified match'), (5, 'Suspicious match'), (10, 'Plagiate'), (9, 'Approved plagiate')], default=0),
            preserve_default=True,
        ),
    ]
