# Generated by Django 2.0 on 2018-08-16 14:35

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('data', '0020_store_similarity_graph_in_course_model'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='course',
            name='similarity_graph_expired',
        ),
        migrations.RemoveField(
            model_name='course',
            name='similarity_graph_json',
        ),
    ]
