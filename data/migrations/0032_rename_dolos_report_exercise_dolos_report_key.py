# Generated by Django 4.2.11 on 2024-04-09 07:49

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("data", "0031_exercise_dolos_report"),
    ]

    operations = [
        migrations.RenameField(
            model_name="exercise",
            old_name="dolos_report",
            new_name="dolos_report_key",
        ),
    ]
