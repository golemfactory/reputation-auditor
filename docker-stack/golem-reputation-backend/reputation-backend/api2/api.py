from ninja import NinjaAPI, Path
from django.http import JsonResponse
import json
api = NinjaAPI(
    title="Golem Reputation API",
    version="2.0.0",
    description="API for Golem Reputation Backend",
    urls_namespace="api2",
)
import redis



r = redis.Redis(host='redis', port=6379, db=0)


@api.get("/providers/scores")
def list_provider_scores(request, network: str = 'polygon'):
    if network == 'polygon' or network == 'mainnet':
        response = r.get('provider_scores_v2_mainnet')
    elif network == 'goerli' or network == 'mumbai' or network == 'holesky':
        response = r.get('provider_scores_v2_testnet')
    else:
        return JsonResponse({"error": "Network not found"}, status=404)

    if response:
        return json.loads(response)
    else:
        # Handle the case where data is not yet available in Redis
        return JsonResponse({"error": "Data not available"}, status=503)


from api.models import Provider, CpuBenchmark, NodeStatusHistory, TaskCompletion, BlacklistedProvider, BlacklistedOperator, MemoryBenchmark, DiskBenchmark, NetworkBenchmark, PingResult
from api.scoring import calculate_uptime, penalty_weight
from django.db.models import Subquery, OuterRef

from django.db.models import Count, Case, When, FloatField
from django.db.models.functions import Cast
from django.db.models import Q
from datetime import timedelta
from django.utils import timezone
from django.db.models import Avg

@api.get(
    "/filter",
    summary="Retrieve a list of provider IDs",
    description="""
    This endpoint retrieves a list of active provider IDs filtered according to various performance metrics and status indicators.
    The filters include uptime, CPU multi-thread and single-thread performance scores, memory performance metrics, success rate of tasks, and disk performance metrics.
    Each filter is optional and can range between minimum and maximum values provided by the client.
    - `minUptime` and `maxUptime` filter providers based on their uptime percentage.
    - `minCpuMultiThreadScore` and `maxCpuMultiThreadScore` filter providers based on their CPU multi-thread benchmark scores.
    - `minCpuSingleThreadScore` and `maxCpuSingleThreadScore` filter based on CPU single-thread benchmark scores.
    - `minMemorySeqRead` and `maxMemorySeqRead` filter based on minimum and maximum sequential read performance in MiB/sec.
    - `minMemorySeqWrite` and `maxMemorySeqWrite` filter based on minimum and maximum sequential write performance in MiB/sec.
    - `minMemoryRandRead` and `maxMemoryRandRead` filter based on minimum and maximum random read performance in operations per second.
    - `minMemoryRandWrite` and `maxMemoryRandWrite` filter based on minimum and maximum random write performance in operations per second.
    - `minRandomReadDiskThroughput` and `maxRandomReadDiskThroughput` filter based on minimum and maximum random disk read throughput in MB/s.
    - `minRandomWriteDiskThroughput` and `maxRandomWriteDiskThroughput` filter based on minimum and maximum random disk write throughput in MB/s.
    - `minSequentialReadDiskThroughput` and `maxSequentialReadDiskThroughput` filter based on minimum and maximum sequential disk read throughput in MB/s.
    - `minSequentialWriteDiskThroughput` and `maxSequentialWriteDiskThroughput` filter based on minimum and maximum sequential disk write throughput in MB/s.
    - `minNetworkDownloadSpeed` and `maxNetworkDownloadSpeed` filter based on minimum and maximum network download speed in Mbit/s.
    - `minPing` and `maxPing` filter based on minimum and maximum average of the last 5 pings in milliseconds.
    - `minSuccessRate` and `maxSuccessRate` filter providers by the percentage of successfully completed tasks.
    - `minProviderAge` filters providers based on the number of days since their creation. This is useful for ensuring that providers have a track record.
    Providers are only included in the result if they are currently online and not blacklisted.
    """,
)
def filter_providers(request, 
                  minUptime: float = None, maxUptime: float = None, 
                  minCpuMultiThreadScore: float = None, maxCpuMultiThreadScore: float = None, 
                  minCpuSingleThreadScore: float = None, maxCpuSingleThreadScore: float = None, 
                  minMemorySeqRead: float = None, maxMemorySeqRead: float = None,
                  minMemorySeqWrite: float = None, maxMemorySeqWrite: float = None,
                  minMemoryRandRead: float = None, maxMemoryRandRead: float = None,
                  minMemoryRandWrite: float = None, maxMemoryRandWrite: float = None,
                  minRandomReadDiskThroughput: float = None, maxRandomReadDiskThroughput: float = None,
                  minRandomWriteDiskThroughput: float = None, maxRandomWriteDiskThroughput: float = None,
                  minSequentialReadDiskThroughput: float = None, maxSequentialReadDiskThroughput: float = None,
                  minSequentialWriteDiskThroughput: float = None, maxSequentialWriteDiskThroughput: float = None,
                  minNetworkDownloadSpeed: float = None, maxNetworkDownloadSpeed: float = None,
                    minPing: float = None, maxPing: float = None,
                  minSuccessRate: float = None, maxSuccessRate: float = None, 
                  minProviderAgeDays: int = None):
    
    blacklisted_providers = set(BlacklistedProvider.objects.values_list('provider_id', flat=True))
    blacklisted_op_wallets = set(BlacklistedOperator.objects.values_list('wallet', flat=True))

    eligible_providers = Provider.objects.exclude(
        Q(node_id__in=blacklisted_providers) | 
        Q(payment_addresses__golem_com_payment_platform_erc20_mainnet_glm_address__in=blacklisted_op_wallets)
    ).annotate(
        latest_status=Subquery(
            NodeStatusHistory.objects.filter(
                provider=OuterRef('pk')
            ).order_by('-timestamp').values('is_online')[:1]
        )
    ).filter(latest_status=True)

    if minProviderAgeDays is not None:
        minimum_age_date = timezone.now() - timedelta(days=minProviderAgeDays)
        eligible_providers = eligible_providers.filter(created_at__lte=minimum_age_date)


    if minUptime is not None:
        eligible_providers = eligible_providers.filter(node_id__in=[
            p.node_id for p in eligible_providers if calculate_uptime(p.node_id) >= minUptime])

    if maxUptime is not None:
        eligible_providers = eligible_providers.filter(node_id__in=[
            p.node_id for p in eligible_providers if calculate_uptime(p.node_id) <= maxUptime])

    if minCpuMultiThreadScore is not None:
        eligible_providers = eligible_providers.annotate(latest_cpu_multi_thread_score=Subquery(
            CpuBenchmark.objects.filter(
                provider=OuterRef('pk'),
                benchmark_name="CPU Multi-thread Benchmark"
            ).order_by('-created_at').values('events_per_second')[:1]
        )).filter(latest_cpu_multi_thread_score__gte=minCpuMultiThreadScore)

    if maxCpuMultiThreadScore is not None:
        eligible_providers = eligible_providers.annotate(latest_cpu_multi_thread_score=Subquery(
            CpuBenchmark.objects.filter(
                provider=OuterRef('pk'),
                benchmark_name="CPU Multi-thread Benchmark"
            ).order_by('-created_at').values('events_per_second')[:1]
        )).filter(latest_cpu_multi_thread_score__lte=maxCpuMultiThreadScore)
    
    if minCpuSingleThreadScore is not None:
        eligible_providers = eligible_providers.annotate(latest_cpu_single_thread_score=Subquery(
            CpuBenchmark.objects.filter(
                provider=OuterRef('pk'),
                benchmark_name="CPU Single-thread Benchmark"
            ).order_by('-created_at').values('events_per_second')[:1]
        )).filter(latest_cpu_single_thread_score__gte=minCpuSingleThreadScore)

    if maxCpuSingleThreadScore is not None:
        eligible_providers = eligible_providers.annotate(latest_cpu_single_thread_score=Subquery(
            CpuBenchmark.objects.filter(
                provider=OuterRef('pk'),
                benchmark_name="CPU Single-thread Benchmark"
            ).order_by('-created_at').values('events_per_second')[:1]
        )).filter(latest_cpu_single_thread_score__lte=maxCpuSingleThreadScore)

    if minSuccessRate is not None:
        eligible_providers = eligible_providers.annotate(
            successful_tasks=Count('taskcompletion', filter=Q(taskcompletion__is_successful=True)),
            total_tasks=Count('taskcompletion'),
            calculated_success_rate=Case(
                When(total_tasks=0, then=None),
                default=(Cast('successful_tasks', FloatField()) / Cast('total_tasks', FloatField()) * 100)
            )
        ).filter(calculated_success_rate__gte=minSuccessRate)

    if maxSuccessRate is not None:
        eligible_providers = eligible_providers.annotate(
            successful_tasks=Count('taskcompletion', filter=Q(taskcompletion__is_successful=True)),
            total_tasks=Count('taskcompletion'),
            calculated_success_rate=Case(
                When(total_tasks=0, then=None),
                default=(Cast('successful_tasks', FloatField()) / Cast('total_tasks', FloatField()) * 100)
            )
        ).filter(calculated_success_rate__lte=maxSuccessRate)

    if minMemorySeqRead is not None:
        eligible_providers = eligible_providers.annotate(
            latest_mem_seq_read=Subquery(
                MemoryBenchmark.objects.filter(
                    provider=OuterRef('pk'),
                    benchmark_name="Sequential_Read_Performance__Single_Thread_"
                ).order_by('-created_at').values('throughput_mi_b_sec')[:1]
            )
        ).filter(latest_mem_seq_read__gte=minMemorySeqRead)

    if maxMemorySeqRead is not None:
        eligible_providers = eligible_providers.annotate(
            latest_mem_seq_read=Subquery(
                MemoryBenchmark.objects.filter(
                    provider=OuterRef('pk'),
                    benchmark_name="Sequential_Read_Performance__Single_Thread_"
                ).order_by('-created_at').values('throughput_mi_b_sec')[:1]
            )
        ).filter(latest_mem_seq_read__lte=maxMemorySeqRead)

    if minMemorySeqWrite is not None:
        eligible_providers = eligible_providers.annotate(
            latest_mem_seq_write=Subquery(
                MemoryBenchmark.objects.filter(
                    provider=OuterRef('pk'),
                    benchmark_name="Sequential_Write_Performance__Single_Thread_"
                ).order_by('-created_at').values('throughput_mi_b_sec')[:1]
            )
        ).filter(latest_mem_seq_write__gte=minMemorySeqWrite)

    if maxMemorySeqWrite is not None:
        eligible_providers = eligible_providers.annotate(
            latest_mem_seq_write=Subquery(
                MemoryBenchmark.objects.filter(
                    provider=OuterRef('pk'),
                    benchmark_name="Sequential_Write_Performance__Single_Thread_"
                ).order_by('-created_at').values('throughput_mi_b_sec')[:1]
            )
        ).filter(latest_mem_seq_write__lte=maxMemorySeqWrite)

    if minMemoryRandRead is not None:
        eligible_providers = eligible_providers.annotate(
            latest_mem_rand_read=Subquery(
                MemoryBenchmark.objects.filter(
                    provider=OuterRef('pk'),
                    benchmark_name="Random_Read_Performance__Multi_threaded_"
                ).order_by('-created_at').values('throughput_mi_b_sec')[:1]
            )
        ).filter(latest_mem_rand_read__gte=minMemoryRandRead)

    if maxMemoryRandRead is not None:
        eligible_providers = eligible_providers.annotate(
            latest_mem_rand_read=Subquery(
                MemoryBenchmark.objects.filter(
                    provider=OuterRef('pk'),
                    benchmark_name="Random_Read_Performance__Multi_threaded_"
                ).order_by('-created_at').values('throughput_mi_b_sec')[:1]
            )
        ).filter(latest_mem_rand_read__lte=maxMemoryRandRead)


    if minMemoryRandWrite is not None:
        eligible_providers = eligible_providers.annotate(
            latest_mem_rand_write=Subquery(
                MemoryBenchmark.objects.filter(
                    provider=OuterRef('pk'),
                    benchmark_name="Random_Write_Performance__Multi_threaded_"
                ).order_by('-created_at').values('throughput_mi_b_sec')[:1]
            )
        ).filter(latest_mem_rand_write__gte=minMemoryRandWrite)

    if maxMemoryRandWrite is not None:
        eligible_providers = eligible_providers.annotate(
            latest_mem_rand_write=Subquery(
                MemoryBenchmark.objects.filter(
                    provider=OuterRef('pk'),
                    benchmark_name="Random_Write_Performance__Multi_threaded_"
                ).order_by('-created_at').values('throughput_mi_b_sec')[:1]
            )
        ).filter(latest_mem_rand_write__lte=maxMemoryRandWrite)

    if minRandomReadDiskThroughput is not None:
        eligible_providers = eligible_providers.annotate(
            latest_disk_random_read_throughput=Subquery(
                DiskBenchmark.objects.filter(
                    provider=OuterRef('pk'),
                    benchmark_name="FileIO_rndrd"
                ).order_by('-created_at').values('read_throughput_mb_ps')[:1]
            )
        ).filter(latest_disk_random_read_throughput__gte=minRandomReadDiskThroughput)

    if maxRandomReadDiskThroughput is not None:
        eligible_providers = eligible_providers.annotate(
            latest_disk_random_read_throughput=Subquery(
                DiskBenchmark.objects.filter(
                    provider=OuterRef('pk'),
                    benchmark_name="FileIO_rndrd"
                ).order_by('-created_at').values('read_throughput_mb_ps')[:1]
            )
        ).filter(latest_disk_random_read_throughput__lte=maxRandomReadDiskThroughput)

    if minRandomWriteDiskThroughput is not None:
        eligible_providers = eligible_providers.annotate(
            latest_disk_random_write_throughput=Subquery(
                DiskBenchmark.objects.filter(
                    provider=OuterRef('pk'),
                    benchmark_name="FileIO_rndwr"
                ).order_by('-created_at').values('write_throughput_mb_ps')[:1]
            )
        ).filter(latest_disk_random_write_throughput__gte=minRandomWriteDiskThroughput)

    if maxRandomWriteDiskThroughput is not None:
        eligible_providers = eligible_providers.annotate(
            latest_disk_random_write_throughput=Subquery(
                DiskBenchmark.objects.filter(
                    provider=OuterRef('pk'),
                    benchmark_name="FileIO_rndwr"
                ).order_by('-created_at').values('write_throughput_mb_ps')[:1]
            )
        ).filter(latest_disk_random_write_throughput__lte=maxRandomWriteDiskThroughput)

    if minSequentialReadDiskThroughput is not None:
        eligible_providers = eligible_providers.annotate(
            latest_disk_sequential_read_throughput=Subquery(
                DiskBenchmark.objects.filter(
                    provider=OuterRef('pk'),
                    benchmark_name="FileIO_seqrd"
                ).order_by('-created_at').values('read_throughput_mb_ps')[:1]
            )
        ).filter(latest_disk_sequential_read_throughput__gte=minSequentialReadDiskThroughput)

    if maxSequentialReadDiskThroughput is not None:
        eligible_providers = eligible_providers.annotate(
            latest_disk_sequential_read_throughput=Subquery(
                DiskBenchmark.objects.filter(
                    provider=OuterRef('pk'),
                    benchmark_name="FileIO_seqrd"
                ).order_by('-created_at').values('read_throughput_mb_ps')[:1]
            )
        ).filter(latest_disk_sequential_read_throughput__lte=maxSequentialReadDiskThroughput)

    if minSequentialWriteDiskThroughput is not None:
        eligible_providers = eligible_providers.annotate(
            latest_disk_sequential_write_throughput=Subquery(
                DiskBenchmark.objects.filter(
                    provider=OuterRef('pk'),
                    benchmark_name="FileIO_seqwr"
                ).order_by('-created_at').values('write_throughput_mb_ps')[:1]
            )
        ).filter(latest_disk_sequential_write_throughput__gte=minSequentialWriteDiskThroughput)

    if maxSequentialWriteDiskThroughput is not None:
        eligible_providers = eligible_providers.annotate(
            latest_disk_sequential_write_throughput=Subquery(
                DiskBenchmark.objects.filter(
                    provider=OuterRef('pk'),
                    benchmark_name="FileIO_seqwr"
                ).order_by('-created_at').values('write_throughput_mb_ps')[:1]
            )
        ).filter(latest_disk_sequential_write_throughput__lte=maxSequentialWriteDiskThroughput)

    if minNetworkDownloadSpeed is not None:
        eligible_providers = eligible_providers.annotate(
            latest_network_download_speed=Subquery(
                NetworkBenchmark.objects.filter(
                    provider=OuterRef('pk'),
                ).order_by('-created_at').values('mbit_per_second')[:1]
            )
        ).filter(latest_network_download_speed__gte=minNetworkDownloadSpeed)

    if maxNetworkDownloadSpeed is not None:
        eligible_providers = eligible_providers.annotate(
            latest_network_download_speed=Subquery(
                NetworkBenchmark.objects.filter(
                    provider=OuterRef('pk'),
                ).order_by('-created_at').values('mbit_per_second')[:1]
            )
        ).filter(latest_network_download_speed__lte=maxNetworkDownloadSpeed)

    if minPing is not None:
            eligible_providers = eligible_providers.annotate(
                avg_ping_udp=Subquery(
                    PingResult.objects.filter(provider=OuterRef('pk'))
                    .order_by('-created_at').values('ping_udp')[:5]
                    .annotate(avg_value=Avg('ping_udp'))
                    .values('avg_value')[:1]
                )
            ).filter(avg_ping_udp__gte=minPing)

    if maxPing is not None:
        eligible_providers = eligible_providers.annotate(
            avg_ping_udp=Subquery(
                PingResult.objects.filter(provider=OuterRef('pk'))
                .order_by('-created_at').values('ping_udp')[:5]
                .annotate(avg_value=Avg('ping_udp'))
                .values('avg_value')[:1]
            )
        ).filter(avg_ping_udp__lte=maxPing)
    provider_ids = eligible_providers.values_list('node_id', flat=True)
    return {"provider_ids": list(provider_ids)}


