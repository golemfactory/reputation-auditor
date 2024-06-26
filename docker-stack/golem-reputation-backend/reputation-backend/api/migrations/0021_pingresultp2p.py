# Generated by Django 4.1.7 on 2024-01-19 14:12

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0020_delete_benchmarktask'),
    ]

    operations = [
        migrations.CreateModel(
            name='PingResultP2P',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_p2p', models.BooleanField(default=False)),
                ('ping_tcp', models.IntegerField()),
                ('ping_udp', models.IntegerField()),
                ('provider', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='api.provider')),
            ],
        ),
    ]
