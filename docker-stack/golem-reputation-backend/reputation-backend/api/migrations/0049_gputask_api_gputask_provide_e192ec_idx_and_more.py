# Generated by Django 4.1.7 on 2024-08-19 13:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0048_convert_gputask_to_json_structure'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='gputask',
            index=models.Index(fields=['provider'], name='api_gputask_provide_e192ec_idx'),
        ),
        migrations.AddIndex(
            model_name='gputask',
            index=models.Index(fields=['created_at'], name='api_gputask_created_5ab4ed_idx'),
        ),
    ]
