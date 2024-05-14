# Generated by Django 4.1.7 on 2024-05-14 10:59

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0035_alter_pingresult_region_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='GPUTask',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('pcie', models.IntegerField()),
                ('memory_total', models.IntegerField()),
                ('memory_free', models.IntegerField()),
                ('cuda_cap', models.DecimalField(decimal_places=2, max_digits=4)),
                ('provider', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='api.provider')),
            ],
        ),
    ]