# Generated by Django 4.1.7 on 2024-01-04 15:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0004_alter_nodestatus_last_seen_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='ScanCount',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('scan_count', models.IntegerField(default=0)),
            ],
        ),
    ]
