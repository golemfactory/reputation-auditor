# Generated by Django 4.1.7 on 2024-01-04 23:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0009_alter_nodestatus_first_seen_scan_count'),
    ]

    operations = [
        migrations.AlterField(
            model_name='nodestatus',
            name='first_seen_scan_count',
            field=models.IntegerField(null=True),
        ),
    ]
