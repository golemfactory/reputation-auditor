# Generated by Django 4.1.7 on 2024-02-20 15:49

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0030_nodestatushistory_provider_created_at_and_more'),
    ]

    operations = [
        migrations.DeleteModel(
            name='ScanCount',
        ),
    ]
