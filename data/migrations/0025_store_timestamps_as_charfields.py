# Generated by Django 2.0 on 2019-01-03 13:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('data', '0024_store_exercise_matching_timestamp'),
    ]

    operations = [
        migrations.AlterField(
            model_name='exercise',
            name='matching_start_time',
            field=models.CharField(blank=True, default=None, help_text='If not None, then an isoformat timestamp which should match to all incoming matching results. If None or does not match incoming results, then these results will be ignored.', max_length=50, null=True),
        ),
        migrations.AlterField(
            model_name='submission',
            name='matching_start_time',
            field=models.CharField(blank=True, default=None, help_text='Timestamp in isoformat that is a checksum for validating incoming matching results. If not None or does not match the timestamp of the parent exercise, then results will be discarded.', max_length=50, null=True),
        ),
    ]
