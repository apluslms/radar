# Generated by Django 4.2.11 on 2024-04-15 07:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("data", "0035_exercise_dolos_report_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="exercise",
            name="template_text",
            field=models.TextField(blank=True, default=""),
        ),
    ]
