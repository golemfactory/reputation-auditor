# Generated by Django 4.1.7 on 2024-01-04 22:17

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0006_nodestatus_version'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='nodestatus',
            name='version',
        ),
    ]
