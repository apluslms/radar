# Generated by Django 2.0 on 2018-06-11 15:49

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('data', '0007_auto_20180604_1505'),
    ]

    operations = [
        migrations.CreateModel(
            name='SimilarityFunction',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('weight', models.FloatField()),
                ('name', models.CharField(max_length=256, unique=True)),
                ('description', models.TextField(blank=True, null=True)),
                ('function', models.CharField(blank=True, max_length=256, null=True)),
                ('tokenized_input', models.BooleanField()),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='data.Course')),
            ],
        ),
        migrations.AlterField(
            model_name='comparison',
            name='review',
            field=models.IntegerField(choices=[(-10, 'False alert'), (0, 'Unspecified match'), (1, 'Approved plagiate'), (5, 'Suspicious match'), (10, 'Plagiate')], default=0),
        ),
    ]