# Generated by Django 4.1.7 on 2024-01-05 09:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0011_remove_pingresult_region'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pingresult',
            name='ping_tcp',
            field=models.IntegerField(),
        ),
        migrations.AlterField(
            model_name='pingresult',
            name='ping_udp',
            field=models.IntegerField(),
        ),
    ]
