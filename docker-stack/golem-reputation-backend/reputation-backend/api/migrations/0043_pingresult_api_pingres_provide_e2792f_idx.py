# Generated by Django 4.1.7 on 2024-05-24 09:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0042_pingresult_from_non_p2p_pinger_and_more'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='pingresult',
            index=models.Index(fields=['provider', 'from_non_p2p_pinger'], name='api_pingres_provide_e2792f_idx'),
        ),
    ]
