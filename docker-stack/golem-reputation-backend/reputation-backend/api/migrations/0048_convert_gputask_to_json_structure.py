# Generated by Django 4.1.7 on 2024-06-18 10:00

from django.db import migrations, models
import json

def convert_gputask_to_json(apps, schema_editor):
    GPUTask = apps.get_model('api', 'GPUTask')
    for task in GPUTask.objects.all():
        # Convert existing fields to a JSON structure
        gpu_info = {"gpus": []}
        
        # Check for each field and add it to the JSON if it exists
        fields = ['name', 'pcie', 'memory_total', 'memory_free', 'cuda_cap', 'gpu_burn_gflops']
        gpu_data = {}
        for field in fields:
            if hasattr(task, field):
                value = getattr(task, field)
                if field == 'cuda_cap':
                    value = float(value) if value is not None else None
                gpu_data[field] = value
        
        if gpu_data:
            gpu_data['quantity'] = 1
            gpu_info['gpus'].append(gpu_data)
        
        task.gpu_info = gpu_info
        task.save()

class Migration(migrations.Migration):

    dependencies = [
        ('api', '0047_cpubenchmark_api_cpubenc_benchma_c0006e_idx'),
    ]

    operations = [
        migrations.AddField(
            model_name='gputask',
            name='gpu_info',
            field=models.JSONField(default=dict),
            preserve_default=False,
        ),
        migrations.RunPython(convert_gputask_to_json),
        # Remove old fields only if they exist
        migrations.RemoveField(
            model_name='gputask',
            name='name',
        ),
        migrations.RemoveField(
            model_name='gputask',
            name='pcie',
        ),
        migrations.RemoveField(
            model_name='gputask',
            name='memory_total',
        ),
        migrations.RemoveField(
            model_name='gputask',
            name='memory_free',
        ),
        migrations.RemoveField(
            model_name='gputask',
            name='cuda_cap',
        ),
        migrations.RemoveField(
            model_name='gputask',
            name='gpu_burn_gflops',
        ),
    ]