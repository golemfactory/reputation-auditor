from django.db import migrations, models

def update_nodestatushistory(apps, schema_editor):
    NodeStatusHistory = apps.get_model('api', 'NodeStatusHistory')
    Provider = apps.get_model('api', 'Provider')

    for history in NodeStatusHistory.objects.all():
        if history.provider:
            history.node_id = history.provider.node_id
            history.save()

class Migration(migrations.Migration):

    dependencies = [
        ('api', '0051_update_gputask_structure'),
    ]

    operations = [
        migrations.AddField(
            model_name='nodestatushistory',
            name='node_id',
            field=models.CharField(max_length=42, null=True),
        ),
        migrations.RunPython(update_nodestatushistory),
        migrations.RemoveField(
            model_name='nodestatushistory',
            name='provider',
        ),
        migrations.AlterField(
            model_name='nodestatushistory',
            name='node_id',
            field=models.CharField(max_length=42),
        ),
        migrations.RemoveIndex(
            model_name='nodestatushistory',
            name='api_nodesta_provide_94f647_idx',
        ),
        migrations.AddIndex(
            model_name='nodestatushistory',
            index=models.Index(fields=['node_id', 'timestamp'], name='node_status_history_idx'),
        ),
    ]