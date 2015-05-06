# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='LTIClient',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('key', models.CharField(help_text='LTI client service key', max_length=128)),
                ('secret', models.CharField(help_text='LTI client service secret', max_length=128)),
                ('description', models.TextField()),
            ],
            options={
                'ordering': ['key'],
            },
            bases=(models.Model,),
        ),
    ]
