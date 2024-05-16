# Generated by Django 4.1.7 on 2024-05-16 10:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stats', '0003_dailyproviderstats_total_provider_rejected_without_operator'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='dailyproviderstats',
            index=models.Index(fields=['date'], name='stats_daily_date_ff2dd0_idx'),
        ),
    ]
