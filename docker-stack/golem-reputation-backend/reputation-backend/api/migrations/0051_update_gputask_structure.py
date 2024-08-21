from django.db import migrations, models

def update_gputask_structure(apps, schema_editor):
    GPUTask = apps.get_model('api', 'GPUTask')
    for task in GPUTask.objects.all():
        if isinstance(task.gpu_info, list):
            # If gpu_info is already a list, we need to restructure it
            gpu_burn_gflops = 0
            for gpu in task.gpu_info:
                if 'gpu_burn_gflops' in gpu:
                    gpu_burn_gflops += gpu.pop('gpu_burn_gflops', 0) * gpu.get('quantity', 1)
            
            new_structure = {
                'gpus': task.gpu_info,
                'gpu_burn_gflops': gpu_burn_gflops
            }
            task.gpu_info = new_structure
            task.gpu_burn_gflops = gpu_burn_gflops
        elif isinstance(task.gpu_info, dict) and 'gpus' in task.gpu_info:
            # If it's already in the correct structure, just extract gpu_burn_gflops
            task.gpu_burn_gflops = task.gpu_info.get('gpu_burn_gflops', 0)
        else:
            # If it's in an unexpected format, set default values
            task.gpu_info = {'gpus': [], 'gpu_burn_gflops': 0}
            task.gpu_burn_gflops = 0
        
        task.save()

class Migration(migrations.Migration):

    dependencies = [
        ('api', '0050_fix_gputask_json_structure'),
    ]

    operations = [
        migrations.AddField(
            model_name='gputask',
            name='gpu_burn_gflops',
            field=models.FloatField(default=0),
            preserve_default=False,
        ),
        migrations.RunPython(update_gputask_structure),
    ]