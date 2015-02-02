# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import data.models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Course',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('name', data.models.URLKeyField(help_text=b'Unique alphanumeric course instance id', unique=True, max_length=64)),
                ('provider', models.CharField(default=b'a+', help_text=b'Provider for submission data', max_length=16, choices=[(b'a+', b'A+'), (b'filesystem', b'File system')])),
                ('tokenizer', models.CharField(default=b'python', help_text=b'Tokenizer for the submission contents', max_length=16, choices=[(b'python', b'Python'), (b'text', b'Natural text'), (b'java', b'Java'), (b'scala', b'Scala')])),
                ('minimum_match_tokens', models.IntegerField(default=15, help_text=b'Minimum number of tokens to consider a match')),
                ('tolerance', models.FloatField(default=0.4, help_text=b'Automatically hide matches that this ratio of submissions have in common')),
                ('archived', models.BooleanField(default=False, db_index=True)),
                ('reviewers', models.ManyToManyField(help_text=b'Reviewers for match analysis', to=settings.AUTH_USER_MODEL, null=True, blank=True)),
            ],
            options={
                'ordering': ['-created'],
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Exercise',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('name', data.models.URLKeyField(help_text=b'Alphanumeric exercise id', max_length=64)),
                ('override_tokenizer', models.CharField(blank=True, max_length=8, null=True, choices=[(b'python', b'Python'), (b'text', b'Natural text'), (b'java', b'Java'), (b'scala', b'Scala')])),
                ('override_minimum_match_tokens', models.IntegerField(null=True, blank=True)),
                ('override_tolerance', models.FloatField(null=True, blank=True)),
                ('course', models.ForeignKey(related_name='exercises', to='data.Course')),
            ],
            options={
                'ordering': ['course', 'name', 'created'],
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Match',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('first_token', models.IntegerField()),
                ('length', models.IntegerField()),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='MatchGroup',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('tokens', models.TextField()),
                ('size', models.IntegerField(default=0, db_index=True)),
                ('average_grade', models.FloatField(default=0.0)),
                ('hide', models.BooleanField(default=False, db_index=True)),
                ('plagiate', models.BooleanField(default=False)),
                ('exercise', models.ForeignKey(related_name='match_groups', to='data.Exercise')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ProviderQueue',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('data', models.CharField(max_length=128)),
                ('processed', models.BooleanField(default=False, db_index=True)),
                ('course', models.ForeignKey(related_name='+', to='data.Course')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Student',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('name', data.models.URLKeyField(help_text=b'Alphanumeric student id', max_length=64)),
                ('course', models.ForeignKey(related_name='students', to='data.Course')),
            ],
            options={
                'ordering': ['course', 'name', 'created'],
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Submission',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('grade', models.FloatField(default=0.0)),
                ('tokens', models.TextField(default=None, null=True, blank=True)),
                ('token_positions', models.TextField(default=None, null=True, blank=True)),
                ('matching_finished', models.BooleanField(default=False, db_index=True)),
                ('exercise', models.ForeignKey(related_name='submissions', to='data.Exercise')),
                ('student', models.ForeignKey(related_name='submissions', to='data.Student')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='student',
            unique_together=set([('course', 'name')]),
        ),
        migrations.AddField(
            model_name='match',
            name='group',
            field=models.ForeignKey(related_name='matches', to='data.MatchGroup'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='match',
            name='submission',
            field=models.ForeignKey(related_name='matches', to='data.Submission'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='exercise',
            unique_together=set([('course', 'name')]),
        ),
    ]
