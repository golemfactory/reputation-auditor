# Generated by Django 4.1.7 on 2024-01-04 15:00

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0003_alter_provider_cores_alter_provider_cpu_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='nodestatus',
            name='last_seen',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AlterField(
            model_name='nodestatus',
            name='uptime_percentage',
            field=models.FloatField(default=0.0),
        ),
    ]
