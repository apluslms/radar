# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('data', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='submission',
            name='matching_finished',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='course',
            name='reviewers',
            field=models.ManyToManyField(help_text=b'Reviewers for match analysis', to=settings.AUTH_USER_MODEL, null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='course',
            name='source',
            field=models.CharField(help_text=b'Source of submission data', max_length=8, choices=[(b'a+', b'A+'), (b'filesystem', b'Filesystem')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='course',
            name='tokenizer',
            field=models.CharField(help_text=b'Tokenizer for the submission contents', max_length=8, choices=[(b'scala', b'Scala'), (b'java', b'Java'), (b'python', b'Python'), (b'text', b'Natural Text')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='exercise',
            name='override_tokenizer',
            field=models.CharField(blank=True, max_length=8, null=True, choices=[(b'scala', b'Scala'), (b'java', b'Java'), (b'python', b'Python'), (b'text', b'Natural Text')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='submission',
            name='token_positions',
            field=models.TextField(default=None, null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='submission',
            name='tokens',
            field=models.TextField(default=None, null=True, blank=True),
            preserve_default=True,
        ),
    ]
