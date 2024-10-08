# Generated by Django 4.1.7 on 2024-05-10 21:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0034_pingresult_region'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pingresult',
            name='region',
            field=models.CharField(default='europe', max_length=255),
        ),
        migrations.AddIndex(
            model_name='cpubenchmark',
            index=models.Index(fields=['provider'], name='api_cpubenc_provide_e48d9e_idx'),
        ),
        migrations.AddIndex(
            model_name='cpubenchmark',
            index=models.Index(fields=['benchmark_name'], name='api_cpubenc_benchma_e34474_idx'),
        ),
        migrations.AddIndex(
            model_name='cpubenchmark',
            index=models.Index(fields=['created_at'], name='api_cpubenc_created_3196d9_idx'),
        ),
        migrations.AddIndex(
            model_name='cpubenchmark',
            index=models.Index(fields=['events_per_second'], name='api_cpubenc_events__127ed1_idx'),
        ),
        migrations.AddIndex(
            model_name='cpubenchmark',
            index=models.Index(fields=['provider', 'created_at'], name='api_cpubenc_provide_8afed3_idx'),
        ),
        migrations.AddIndex(
            model_name='cpubenchmark',
            index=models.Index(fields=['benchmark_name', 'created_at'], name='api_cpubenc_benchma_2ab614_idx'),
        ),
        migrations.AddIndex(
            model_name='diskbenchmark',
            index=models.Index(fields=['provider'], name='api_diskben_provide_ed0c97_idx'),
        ),
        migrations.AddIndex(
            model_name='diskbenchmark',
            index=models.Index(fields=['benchmark_name'], name='api_diskben_benchma_6e6a8c_idx'),
        ),
        migrations.AddIndex(
            model_name='diskbenchmark',
            index=models.Index(fields=['created_at'], name='api_diskben_created_cc2fef_idx'),
        ),
        migrations.AddIndex(
            model_name='diskbenchmark',
            index=models.Index(fields=['reads_per_second'], name='api_diskben_reads_p_bcec9e_idx'),
        ),
        migrations.AddIndex(
            model_name='diskbenchmark',
            index=models.Index(fields=['writes_per_second'], name='api_diskben_writes__5d7d4f_idx'),
        ),
        migrations.AddIndex(
            model_name='diskbenchmark',
            index=models.Index(fields=['read_throughput_mb_ps'], name='api_diskben_read_th_672067_idx'),
        ),
        migrations.AddIndex(
            model_name='diskbenchmark',
            index=models.Index(fields=['write_throughput_mb_ps'], name='api_diskben_write_t_1ab569_idx'),
        ),
        migrations.AddIndex(
            model_name='diskbenchmark',
            index=models.Index(fields=['provider', 'created_at'], name='api_diskben_provide_e97775_idx'),
        ),
        migrations.AddIndex(
            model_name='diskbenchmark',
            index=models.Index(fields=['benchmark_name', 'created_at'], name='api_diskben_benchma_8ae2d4_idx'),
        ),
        migrations.AddIndex(
            model_name='diskbenchmark',
            index=models.Index(fields=['provider', 'benchmark_name', 'created_at'], name='api_diskben_provide_07e240_idx'),
        ),
        migrations.AddIndex(
            model_name='memorybenchmark',
            index=models.Index(fields=['provider'], name='api_memoryb_provide_c9e66d_idx'),
        ),
        migrations.AddIndex(
            model_name='memorybenchmark',
            index=models.Index(fields=['benchmark_name'], name='api_memoryb_benchma_2f14fe_idx'),
        ),
        migrations.AddIndex(
            model_name='memorybenchmark',
            index=models.Index(fields=['created_at'], name='api_memoryb_created_9a5d93_idx'),
        ),
        migrations.AddIndex(
            model_name='memorybenchmark',
            index=models.Index(fields=['throughput_mi_b_sec'], name='api_memoryb_through_954d60_idx'),
        ),
        migrations.AddIndex(
            model_name='memorybenchmark',
            index=models.Index(fields=['provider', 'created_at'], name='api_memoryb_provide_fb5b6d_idx'),
        ),
        migrations.AddIndex(
            model_name='memorybenchmark',
            index=models.Index(fields=['benchmark_name', 'created_at'], name='api_memoryb_benchma_b43c88_idx'),
        ),
        migrations.AddIndex(
            model_name='memorybenchmark',
            index=models.Index(fields=['provider', 'benchmark_name', 'created_at'], name='api_memoryb_provide_e7197b_idx'),
        ),
        migrations.AddIndex(
            model_name='nodestatushistory',
            index=models.Index(fields=['provider', 'timestamp'], name='api_nodesta_provide_94f647_idx'),
        ),
        migrations.AddIndex(
            model_name='taskcompletion',
            index=models.Index(fields=['provider', 'timestamp'], name='api_taskcom_provide_81ddd1_idx'),
        ),
        migrations.AddIndex(
            model_name='taskcompletion',
            index=models.Index(fields=['task'], name='api_taskcom_task_id_1e012f_idx'),
        ),
        migrations.AddIndex(
            model_name='taskcompletion',
            index=models.Index(condition=models.Q(('is_successful', True)), fields=['provider', 'is_successful'], name='idx_provider_success'),
        ),
        migrations.AddIndex(
            model_name='taskcompletion',
            index=models.Index(fields=['type'], name='api_taskcom_type_f4153f_idx'),
        ),
    ]
