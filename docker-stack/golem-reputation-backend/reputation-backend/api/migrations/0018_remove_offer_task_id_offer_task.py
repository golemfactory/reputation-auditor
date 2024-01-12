# Generated by Django 4.1.7 on 2024-01-11 19:56

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0017_offer'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='offer',
            name='task_id',
        ),
        migrations.AddField(
            model_name='offer',
            name='task',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, to='api.task'),
            preserve_default=False,
        ),
    ]
