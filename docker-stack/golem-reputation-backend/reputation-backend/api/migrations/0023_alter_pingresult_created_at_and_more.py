# Generated by Django 4.1.7 on 2024-01-23 15:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0022_pingresult_created_at_pingresultp2p_created_at'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pingresult',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AlterField(
            model_name='pingresultp2p',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
    ]
