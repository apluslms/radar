# Generated by Django 4.2.11 on 2024-04-09 07:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("data", "0030_auto_20211201_0442"),
    ]

    operations = [
        migrations.AddField(
            model_name="exercise",
            name="dolos_report",
            field=models.TextField(blank=True, default=""),
        ),
    ]
