# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings
import data.models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Course',
            fields=[
                ('id', models.AutoField(auto_created=True, serialize=False, primary_key=True, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('name', data.models.URLKeyField(unique=True, max_length=64, help_text='Unique alphanumeric course _instance_ name')),
                ('source', models.CharField(help_text='Source of submission data', max_length=8, choices=[('plus', 'A+'), ('filesystem', 'Filesystem')])),
                ('tokenizer', models.CharField(help_text='Tokenizer for the submission contents', max_length=8)),
                ('minimum_match_tokens', models.IntegerField(default=15, help_text='Minimum number of tokens to consider a match')),
                ('tolerance', models.FloatField(default=0.4, help_text='Automatically hide matches that this ratio of submissions have in common')),
                ('reviewers', models.ManyToManyField(help_text='Reviewers for match analysis', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created'],
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Exercise',
            fields=[
                ('id', models.AutoField(auto_created=True, serialize=False, primary_key=True, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('name', models.CharField(max_length=64)),
                ('override_tokenizer', models.CharField(null=True, blank=True, max_length=8)),
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
                ('id', models.AutoField(auto_created=True, serialize=False, primary_key=True, verbose_name='ID')),
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
                ('id', models.AutoField(auto_created=True, serialize=False, primary_key=True, verbose_name='ID')),
                ('tokens', models.TextField()),
                ('size', models.IntegerField(default=0)),
                ('average_grade', models.FloatField(default=0.0)),
                ('hide', models.BooleanField(default=False)),
                ('plagiate', models.BooleanField(default=False)),
                ('exercise', models.ForeignKey(related_name='match_groups', to='data.Exercise')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Student',
            fields=[
                ('id', models.AutoField(auto_created=True, serialize=False, primary_key=True, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('name', models.CharField(max_length=64)),
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
                ('id', models.AutoField(auto_created=True, serialize=False, primary_key=True, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('tokens', models.TextField()),
                ('token_positions', models.TextField()),
                ('file', models.CharField(max_length=32)),
                ('grade', models.FloatField()),
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
