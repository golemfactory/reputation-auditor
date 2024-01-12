# Generated by Django 4.1.7 on 2024-01-11 16:01

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0015_alter_cpubenchmark_total_time_sec'),
    ]

    operations = [
        migrations.CreateModel(
            name='Task',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('started_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('finished_at', models.DateTimeField(null=True)),
            ],
        ),
        migrations.AddField(
            model_name='taskcompletion',
            name='task',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='api.task'),
        ),
    ]
