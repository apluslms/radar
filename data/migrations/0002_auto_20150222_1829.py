# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import data.models
from django.utils.timezone import utc
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('data', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Comparison',
            fields=[
                ('id', models.AutoField(primary_key=True, auto_created=True, serialize=False, verbose_name='ID')),
                ('similarity', models.FloatField(default=0.0)),
                ('matches_json', models.TextField(blank=True, null=True, default=None)),
                ('review', models.IntegerField(choices=[(-10, 'False alert'), (0, 'Unspecified match'), (5, 'Suspicious match'), (10, 'Plagiate')], default=0)),
                ('submission_a', models.ForeignKey(to='data.Submission', related_name='+')),
                ('submission_b', models.ForeignKey(blank=True, null=True, to='data.Submission', related_name='+')),
            ],
            options={
                'ordering': ['-similarity'],
            },
            bases=(models.Model,),
        ),
        migrations.RemoveField(
            model_name='match',
            name='group',
        ),
        migrations.RemoveField(
            model_name='match',
            name='submission',
        ),
        migrations.DeleteModel(
            name='Match',
        ),
        migrations.RemoveField(
            model_name='matchgroup',
            name='exercise',
        ),
        migrations.DeleteModel(
            name='MatchGroup',
        ),
        migrations.AlterUniqueTogether(
            name='comparison',
            unique_together=set([('submission_a', 'submission_b')]),
        ),
        migrations.AlterModelOptions(
            name='exercise',
            options={'ordering': ['course', 'created']},
        ),
        migrations.AlterModelOptions(
            name='student',
            options={'ordering': ['course', 'key']},
        ),
        migrations.RenameField(
            model_name='student',
            old_name='name',
            new_name='key',
        ),
        migrations.RenameField(
            model_name='submission',
            old_name='token_positions',
            new_name='indexes_json',
        ),
        migrations.RemoveField(
            model_name='course',
            name='tolerance',
        ),
        migrations.RemoveField(
            model_name='submission',
            name='matching_finished',
        ),
        migrations.RenameField(
            model_name='course',
            old_name='name',
            new_name='key',
        ),
        #migrations.AddField(
        #    model_name='course',
        #    name='key',
        #    field=data.models.URLKeyField(max_length=64, unique=True, default=datetime.datetime(2015, 2, 22, 18, 29, 19, 355569, tzinfo=utc), help_text='Unique alphanumeric course instance id'),
        #    preserve_default=False,
        #),
        migrations.RenameField(
            model_name='exercise',
            old_name='name',
            new_name='key',
        ),
        #migrations.AddField(
        #    model_name='exercise',
        #    name='key',
        #    field=data.models.URLKeyField(max_length=64, default=datetime.datetime(2015, 2, 22, 18, 29, 24, 547614, tzinfo=utc), help_text='Alphanumeric exercise id'),
        #    preserve_default=False,
        #),
        migrations.AddField(
            model_name='exercise',
            name='template_tokens',
            field=models.TextField(blank=True, default=''),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='submission',
            name='authored_token_count',
            field=models.IntegerField(blank=True, null=True, default=None),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='submission',
            name='max_similarity',
            field=models.FloatField(blank=True, db_index=True, null=True, default=None),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='course',
            name='name',
            field=models.CharField(max_length=128, help_text='Descriptive course name'),
            preserve_default=True,
        ),
        #migrations.AlterField(
        #    model_name='course',
        #    name='name',
        #    field=models.CharField(max_length=128, help_text='Descriptive course name'),
        #    preserve_default=True,
        #),
        migrations.AlterField(
            model_name='course',
            name='tokenizer',
            field=models.CharField(choices=[('skip', 'Skip'), ('scala', 'Scala')], max_length=16, default='skip', help_text='Tokenizer for the submission contents'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='exercise',
            name='name',
            field=models.CharField(max_length=128, default='unknown', help_text='Descriptive exercise name'),
            preserve_default=True,
        ),
        #migrations.AlterField(
        #    model_name='exercise',
        #    name='name',
        #    field=models.CharField(max_length=128, default='unknown', help_text='Descriptive exercise name'),
        #    preserve_default=True,
        #),
        migrations.AlterField(
            model_name='exercise',
            name='override_tokenizer',
            field=models.CharField(blank=True, max_length=8, null=True, choices=[('skip', 'Skip'), ('scala', 'Scala')]),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='exercise',
            unique_together=set([('course', 'key')]),
        ),
        migrations.RemoveField(
            model_name='exercise',
            name='override_tolerance',
        ),
        migrations.AlterUniqueTogether(
            name='student',
            unique_together=set([('course', 'key')]),
        ),
    ]
