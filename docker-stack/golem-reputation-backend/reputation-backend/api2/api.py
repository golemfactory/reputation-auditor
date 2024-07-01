from ninja import NinjaAPI, Path
from django.http import JsonResponse
from ninja import Query
from typing import Optional
import json
api = NinjaAPI(
    title="Golem Reputation API",
    version="2.0.0",
    description="API for Golem Reputation Backend",
    urls_namespace="api2:api",
    docs_url="/docs/"
)
import redis



r = redis.Redis(host='redis', port=6379, db=0)


@api.get(
    "/providers/scores",
    tags=["Reputation"],
    summary="Retrieve provider scores",
    description="""
    This endpoint retrieves the scores of providers based on the specified network. The scores include various performance metrics.

    The response includes two main sections: `testedProviders` and `untestedProviders`.

    Each provider in `testedProviders` includes:
    - `provider`: An object containing:
        - `id`: The provider's unique identifier.
        - `name`: The provider's name.
        - `walletAddress`: The provider's wallet address.
    - `scores`: An object containing:
        - `successRate`: The percentage of successfully completed tasks.
        - `uptime`: The percentage of time the provider has been online.
        - `cpuSingleThreadScore`: The CPU single-thread benchmark score, normalized and penalized based on deviation.
        - `cpuMultiThreadScore`: The CPU multi-thread benchmark score, normalized and penalized based on deviation.

    Each provider in `untestedProviders` includes:
    - `provider`: An object containing:
        - `id`: The provider's unique identifier.
        - `name`: The provider's name.
        - `walletAddress`: The provider's wallet address.
    - `scores`: An object containing:
        - `uptime`: The percentage of time the provider has been online.

    The CPU scores are normalized and penalized based on the deviation from the average performance of the latest benchmarks. The penalty weights are applied as follows:
    - No penalty for deviations <= 5% (penalty weight = 1.0).
    - A small penalty for deviations between 5% and 15% (penalty weight = 0.7).
    - A larger penalty for deviations > 15% (penalty weight = 0.4).

    These penalties are applied to ensure that providers with consistent performance are rewarded, while those with significant deviations from the average performance are penalized.

    Additionally, the response includes information about rejected providers and operators, detailing the reasons for their rejection.
    """,
)
def list_provider_scores(request, network: str = Query('polygon', description="The network parameter specifies the blockchain network for which provider scores are retrieved. Options include: 'polygon' or 'mainnet' for the main Ethereum network, 'goerli', 'mumbai', or 'holesky' for test networks. Any other value will result in a 404 error, indicating that the network is not supported.")):
    if network == 'polygon' or network == 'mainnet':
        response = r.get('provider_scores_v2_mainnet')
    elif network == 'goerli' or network == 'mumbai' or network == 'holesky':
        response = r.get('provider_scores_v2_testnet')
    else:
        return JsonResponse({"error": "Network not found"}, status=404)

    if response:
        return json.loads(response)
    else:
        # Handle the case where data is not yet available
        return JsonResponse({"error": "Data not available"}, status=503)


from api.models import Provider, CpuBenchmark, NodeStatusHistory, TaskCompletion, BlacklistedProvider, BlacklistedOperator, MemoryBenchmark, DiskBenchmark, NetworkBenchmark, PingResult, GPUTask
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
    tags=["Reputation"],
    summary="Retrieve a list of provider IDs filtered by various criteria",
    description="""
    This endpoint retrieves a list of active provider IDs filtered according to various performance metrics and status indicators. Each filter is optional and can be specified with minimum and maximum values by the client. Providers are only included in the result if they are currently online and not blacklisted. The filters allow for detailed querying based on metrics such as uptime, CPU performance, memory and disk throughput, network speed, and task success rates.
    """,
)
def filter_providers(
    request,
    minProviderAge: Optional[int] = Query(None, description="Minimum number of days since provider creation. This filter helps exclude newer providers that may show a high uptime percentage simply because they've been operational for a short period, such as a provider with 99% uptime over two days, which may not be indicative of long-term reliability for requestors looking to run long-running services."),
    minUptime: Optional[float] = Query(None, description="Minimum uptime percentage"),
    maxUptime: Optional[float] = Query(None, description="Maximum uptime percentage"),
    minGPUScore: Optional[float] = Query(None, description="Minimum GPU benchmark score"),
    maxGPUScore: Optional[float] = Query(None, description="Maximum GPU benchmark score"),
    minCpuMultiThreadScore: Optional[float] = Query(None, description="Minimum CPU multi-thread benchmark score"),
    maxCpuMultiThreadScore: Optional[float] = Query(None, description="Maximum CPU multi-thread benchmark score"),
    minCpuSingleThreadScore: Optional[float] = Query(None, description="Minimum CPU single-thread benchmark score"),
    maxCpuSingleThreadScore: Optional[float] = Query(None, description="Maximum CPU single-thread benchmark score"),
    minMemorySeqRead: Optional[float] = Query(None, description="Minimum sequential read performance in MiB/sec"),
    maxMemorySeqRead: Optional[float] = Query(None, description="Maximum sequential read performance in MiB/sec"),
    minMemorySeqWrite: Optional[float] = Query(None, description="Minimum sequential write performance in MiB/sec"),
    maxMemorySeqWrite: Optional[float] = Query(None, description="Maximum sequential write performance in MiB/sec"),
    minMemoryRandRead: Optional[float] = Query(None, description="Minimum random read performance in MiB/sec"),
maxMemoryRandRead: Optional[float] = Query(None, description="Maximum random read performance in MiB/sec"),
minMemoryRandWrite: Optional[float] = Query(None, description="Minimum random write performance in MiB/sec"),
maxMemoryRandWrite: Optional[float] = Query(None, description="Maximum random write performance in MiB/sec"),
    minRandomReadDiskThroughput: Optional[float] = Query(None, description="Minimum random disk read throughput in MB/s"),
    maxRandomReadDiskThroughput: Optional[float] = Query(None, description="Maximum random disk read throughput in MB/s"),
    minRandomWriteDiskThroughput: Optional[float] = Query(None, description="Minimum random disk write throughput in MB/s"),
    maxRandomWriteDiskThroughput: Optional[float] = Query(None, description="Maximum random disk write throughput in MB/s"),
    minSequentialReadDiskThroughput: Optional[float] = Query(None, description="Minimum sequential disk read throughput in MB/s"),
    maxSequentialReadDiskThroughput: Optional[float] = Query(None, description="Maximum sequential disk read throughput in MB/s"),
    minSequentialWriteDiskThroughput: Optional[float] = Query(None, description="Minimum sequential disk write throughput in MB/s"),
    maxSequentialWriteDiskThroughput: Optional[float] = Query(None, description="Maximum sequential disk write throughput in MB/s"),
    minNetworkDownloadSpeed: Optional[float] = Query(None, description="Minimum network download speed in Mbit/s"),
    maxNetworkDownloadSpeed: Optional[float] = Query(None, description="Maximum network download speed in Mbit/s"),
    minPing: Optional[float] = Query(None, description="Minimum average of the last 5 pings in milliseconds, filtered by the specified region"),
    maxPing: Optional[float] = Query(None, description="Maximum average of the last 5 pings in milliseconds, filtered by the specified region"),
    pingRegion: str = Query("europe", description="Region for ping filter. Options include 'europe', 'asia', and 'us'."),
    minSuccessRate: Optional[float] = Query(None, description="Minimum percentage of successfully completed tasks"),
    maxSuccessRate: Optional[float] = Query(None, description="Maximum percentage of successfully completed tasks"),
    providerHasOpenPorts: Optional[bool] = Query(None, description="If true, only providers with open ports are included in the result. If false, only providers without open ports are included. If not specified, all providers are included."),
    is_p2p: bool = Query(False, description="Specify whether the pings should be peer-to-peer (p2p). If True, pings are conducted from open ports; if False, they are routed through the relay. Defaults to False.")):

    
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

    if minProviderAge is not None:
        minimum_age_date = timezone.now() - timedelta(days=minProviderAge)
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

    ping_filter = Q(region=pingRegion) & Q(is_p2p=is_p2p)

    if minPing is not None:
        eligible_providers = eligible_providers.annotate(
            avg_ping_udp=Subquery(
                PingResult.objects.filter(
                    ping_filter,
                    provider=OuterRef('pk'),
                ).order_by('-created_at').values('ping_udp')[:5]
                .annotate(avg_value=Avg('ping_udp'))
                .values('avg_value')[:1]
            )
        ).filter(avg_ping_udp__gte=minPing)

    if maxPing is not None:
        eligible_providers = eligible_providers.annotate(
            avg_ping_udp=Subquery(
                PingResult.objects.filter(
                    ping_filter,
                    provider=OuterRef('pk'),
                ).order_by('-created_at').values('ping_udp')[:5]
                .annotate(avg_value=Avg('ping_udp'))
                .values('avg_value')[:1]
            )
        ).filter(avg_ping_udp__lte=maxPing)

    if providerHasOpenPorts is not None:
        if providerHasOpenPorts:
            eligible_providers = eligible_providers.filter(
                Q(pingresult__is_p2p=True) & Q(pingresult__from_non_p2p_pinger=True)
            )
        else:
            eligible_providers = eligible_providers.exclude(
                Q(pingresult__is_p2p=True) & Q(pingresult__from_non_p2p_pinger=True)
            )

    if minGPUScore is not None:
        eligible_providers = eligible_providers.annotate(latest_gpu_score=Subquery(
            GPUTask.objects.filter(
                provider=OuterRef('pk')
            ).order_by('-created_at').values('gpu_burn_gflops')[:1]
        )).filter(latest_gpu_score__gte=minGPUScore)

    if maxGPUScore is not None:
        eligible_providers = eligible_providers.annotate(latest_gpu_score=Subquery(
            GPUTask.objects.filter(
                provider=OuterRef('pk')
            ).order_by('-created_at').values('gpu_burn_gflops')[:1]
        )).filter(latest_gpu_score__lte=maxGPUScore)
    
    provider_ids = eligible_providers.values_list('node_id', flat=True)
    return {"provider_ids": list(provider_ids)}

from ninja import Schema
# Bulk create pings
from django.core.exceptions import ObjectDoesNotExist
import os

from ninja.security import HttpBearer


class PingSecret(HttpBearer):
    def authenticate(self, request, token):
        if token == os.getenv('PING_SECRET'):
            return token
class PingSchema(Schema):
    provider_id: str  # Change the type to str to match node_id
    ping_udp: float
    ping_tcp: float
    is_p2p: bool
    from_non_p2p_pinger: Optional[bool] = None

@api.post("/pings", include_in_schema=False, auth=PingSecret())
def create_pings(request, region: str, pings: list[PingSchema]):
    pings_to_create = []
    error_msgs = []

    for ping_data in pings:
        provider_id = ping_data.provider_id  # Get provider_id from the POST request
        try:
            provider = Provider.objects.get(node_id=provider_id)  # Fetch the Provider instance using node_id
            ping_result = PingResult(
                provider=provider,
                is_p2p=ping_data.is_p2p,
                ping_udp=ping_data.ping_udp,
                ping_tcp=ping_data.ping_tcp,
                created_at=timezone.now(),
                region=region
            )
            if ping_data.from_non_p2p_pinger is not None:
                ping_result.from_non_p2p_pinger = ping_data.from_non_p2p_pinger
            pings_to_create.append(ping_result)
        except ObjectDoesNotExist:
            continue

    PingResult.objects.bulk_create(pings_to_create)
    return {"message": "Pings created"}


from django.db.models.fields.json import KeyTextTransform

@api.get(
    "/providers/check_blacklist",
    tags=["Reputation"],
    summary="Check if a provider is blacklisted",
    description="This endpoint checks if a provider is blacklisted based on the provided node_id.",
)
def check_blacklist(request, node_id: str = Query(..., description="The node_id of the provider to check.")):
    # Check if the provider is blacklisted
    is_blacklisted_provider = BlacklistedProvider.objects.filter(provider__node_id=node_id).exists()
    
    # Extract the wallet address from the JSON field for comparison
    wallet_address = Provider.objects.filter(node_id=node_id).annotate(
        wallet=KeyTextTransform('golem.com.payment.platform.erc20-mainnet-glm.address', 'payment_addresses')
    ).values_list('wallet', flat=True).first()
    
    # Check if the provider's wallet is blacklisted
    is_blacklisted_operator = False
    if wallet_address:
        is_blacklisted_operator = BlacklistedOperator.objects.filter(wallet=wallet_address).exists()
    
    return JsonResponse({
        "node_id": node_id,
        "is_blacklisted_provider": is_blacklisted_provider,
        "is_blacklisted_wallet": is_blacklisted_operator
    })





@api.get(
    "/providers/{node_id}/scores",
    tags=["Reputation"],
    summary="Retrieve all scores for a specific provider",
    description="This endpoint retrieves all the scores for a specific provider based on the provided node_id."
)
def get_provider_scores(request, node_id: str = Path(..., description="The node_id of the provider to retrieve scores for.")):
    try:
        provider = Provider.objects.get(node_id=node_id)
    except Provider.DoesNotExist:
        return JsonResponse({"error": "Provider not found"}, status=404)

    scores = {}

    # Uptime
    scores['uptime'] = calculate_uptime(provider.node_id)

    # CPU Multi-thread Score
    scores['cpuMultiThreadScore'] = CpuBenchmark.objects.filter(
        provider=provider,
        benchmark_name="CPU Multi-thread Benchmark"
    ).order_by('-created_at').values_list('events_per_second', flat=True).first()

    # CPU Single-thread Score
    scores['cpuSingleThreadScore'] = CpuBenchmark.objects.filter(
        provider=provider,
        benchmark_name="CPU Single-thread Benchmark"
    ).order_by('-created_at').values_list('events_per_second', flat=True).first()

    # Success Rate
    successful_tasks = TaskCompletion.objects.filter(provider=provider, is_successful=True).count()
    total_tasks = TaskCompletion.objects.filter(provider=provider).count()
    scores['successRate'] = (successful_tasks / total_tasks * 100) if total_tasks > 0 else None

    # Memory Benchmarks
    scores['memorySeqRead'] = MemoryBenchmark.objects.filter(
        provider=provider,
        benchmark_name="Sequential_Read_Performance__Single_Thread_"
    ).order_by('-created_at').values_list('throughput_mi_b_sec', flat=True).first()

    scores['memorySeqWrite'] = MemoryBenchmark.objects.filter(
        provider=provider,
        benchmark_name="Sequential_Write_Performance__Single_Thread_"
    ).order_by('-created_at').values_list('throughput_mi_b_sec', flat=True).first()

    scores['memoryRandRead'] = MemoryBenchmark.objects.filter(
        provider=provider,
        benchmark_name="Random_Read_Performance__Multi_threaded_"
    ).order_by('-created_at').values_list('throughput_mi_b_sec', flat=True).first()

    scores['memoryRandWrite'] = MemoryBenchmark.objects.filter(
        provider=provider,
        benchmark_name="Random_Write_Performance__Multi_threaded_"
    ).order_by('-created_at').values_list('throughput_mi_b_sec', flat=True).first()

    # Disk Benchmarks
    scores['randomReadDiskThroughput'] = DiskBenchmark.objects.filter(
        provider=provider,
        benchmark_name="FileIO_rndrd"
    ).order_by('-created_at').values_list('read_throughput_mb_ps', flat=True).first()

    scores['randomWriteDiskThroughput'] = DiskBenchmark.objects.filter(
        provider=provider,
        benchmark_name="FileIO_rndwr"
    ).order_by('-created_at').values_list('write_throughput_mb_ps', flat=True).first()

    scores['sequentialReadDiskThroughput'] = DiskBenchmark.objects.filter(
        provider=provider,
        benchmark_name="FileIO_seqrd"
    ).order_by('-created_at').values_list('read_throughput_mb_ps', flat=True).first()

    scores['sequentialWriteDiskThroughput'] = DiskBenchmark.objects.filter(
        provider=provider,
        benchmark_name="FileIO_seqwr"
    ).order_by('-created_at').values_list('write_throughput_mb_ps', flat=True).first()

    # Network Download Speed
    scores['networkDownloadSpeed'] = NetworkBenchmark.objects.filter(
        provider=provider
    ).order_by('-created_at').values_list('mbit_per_second', flat=True).first()

    # Ping
    regions = ["europe", "asia", "us"]
    scores['ping'] = {}

    for region in regions:
        scores['ping'][region] = {
            "p2p": PingResult.objects.filter(
                provider=provider,
                region=region,
                is_p2p=True
            ).order_by('-created_at').values_list('ping_udp', flat=True)[:5].aggregate(avg_ping=Avg('ping_udp'))['avg_ping'],
            "non_p2p": PingResult.objects.filter(
                provider=provider,
                region=region,
                is_p2p=False
            ).order_by('-created_at').values_list('ping_udp', flat=True)[:5].aggregate(avg_ping=Avg('ping_udp'))['avg_ping']
        }
    return JsonResponse({"node_id": node_id, "scores": scores})



PRESETS = {
    "service": {
        "minUptime": 0.95
    },
    "network": {
        "minNetworkDownloadSpeed": 80
    },
    "disk": {
        "minRandomReadDiskThroughput": 45,
        "minRandomWriteDiskThroughput": 30
    },
    "memory": {
        "minMemoryRandRead": 15000,
        "minMemoryRandWrite": 2400
    },
    "db": {
        "minUptime": 0.95,
        "minRandomReadDiskThroughput": 45,
        "minRandomWriteDiskThroughput": 30
    },
    "memory_db": {
        "minUptime": 0.95,
        "minMemoryRandRead": 15000,
        "minMemoryRandWrite": 2400
    },
    "compute": {
        "minCpuSingleThreadScore": 1250
    },
    "long_compute": {
        "minUptime": 0.95,
        "minCpuSingleThreadScore": 1250
    },
    "parallel": {
        "minCpuMultiThreadScore": 15000
    },
    "long_parallel": {
        "minUptime": 0.95,
        "minCpuMultiThreadScore": 15000
    },
    "rendering": {
        "minNetworkDownloadSpeed": 80,
        "minCpuMultiThreadScore": 15000
    },
    "cdn": {
        "minUptime": 0.95,
        "minNetworkDownloadSpeed": 80,
        "minRandomReadDiskThroughput": 45,
        "minRandomWriteDiskThroughput": 30
    }
}

class PresetResponse(Schema):
    provider_ids: list[str]
import requests
@api.get(
    "/providers/preset/{preset_name}",
    tags=["Reputation"],
    summary="Retrieve providers based on predefined preset",
    description="""
    This endpoint retrieves a list of providers based on a predefined preset. Each preset specifies a set of filter parameters that are used to query the providers. The available presets are:

    - **service**: High uptime, good network speeds, and other important metrics for service providers.
    - **network**: High network download speed for network-related tasks.
    - **disk**: High disk read/write performance for disk-intensive tasks.
    - **memory**: High memory read/write performance for memory-intensive tasks.
    - **db**: High uptime, good disk read/write performance for database services.
    - **memory_db**: High uptime, good memory read/write performance for database services.
    - **compute**: High single-thread CPU performance for compute-intensive tasks.
    - **long_compute**: High uptime, high single-thread CPU performance for compute-intensive tasks.
    - **parallel**: High multi-thread CPU performance for parallel tasks.
    - **long_parallel**: High uptime, high multi-thread CPU performance for parallel tasks.
    - **rendering**: High network download speed and multi-thread CPU performance for rendering tasks.
    - **cdn**: High uptime, high network download speed, and good disk read/write performance for content delivery network services.
    - **balanced**: Balanced performance across various metrics.
    - **test_environment**: Lower requirements suitable for test environments.
    """,
    response=PresetResponse
)
def filter_providers_by_preset(request, preset_name: str):
    """
    Retrieve providers based on a predefined preset.

    Parameters:
    - preset_name: The name of the preset to use for filtering providers.

    Returns:
    - A list of provider IDs that match the specified preset.
    """
    preset = PRESETS.get(preset_name)
    if not preset:
        return JsonResponse({"error": "Preset not found"}, status=404)
    
    # Proxy the request to filter_providers
    request = requests.get(
        f"http://django:8002/v2/filter",
        params=preset
    )
    return request.json()


@api.get(
    "/providers/all_scores",
    tags=["Reputation"],
    summary="Retrieve all provider scores",
    description="This endpoint retrieves the scores of all providers without any filters applied. It provides a comprehensive view of all available provider scores."
)
def list_all_provider_scores(request):
    providers = Provider.objects.all()
    all_scores = []

    for provider in providers:
        scores = {
            "provider": {
                "id": provider.node_id,
                "name": provider.name,
                "walletAddress": provider.payment_addresses.get('golem.com.payment.platform.erc20-mainnet-glm.address', None)
            },
            "scores": {
                "uptime": calculate_uptime(provider.node_id),
                "cpuMultiThreadScore": CpuBenchmark.objects.filter(
                    provider=provider,
                    benchmark_name="CPU Multi-thread Benchmark"
                ).order_by('-created_at').values_list('events_per_second', flat=True).first(),
                "cpuSingleThreadScore": CpuBenchmark.objects.filter(
                    provider=provider,
                    benchmark_name="CPU Single-thread Benchmark"
                ).order_by('-created_at').values_list('events_per_second', flat=True).first(),
                "successRate": (TaskCompletion.objects.filter(provider=provider, is_successful=True).count() / TaskCompletion.objects.filter(provider=provider).count() * 100) if TaskCompletion.objects.filter(provider=provider).count() > 0 else None,
                "memorySeqRead": MemoryBenchmark.objects.filter(
                    provider=provider,
                    benchmark_name="Sequential_Read_Performance__Single_Thread_"
                ).order_by('-created_at').values_list('throughput_mi_b_sec', flat=True).first(),
                "memorySeqWrite": MemoryBenchmark.objects.filter(
                    provider=provider,
                    benchmark_name="Sequential_Write_Performance__Single_Thread_"
                ).order_by('-created_at').values_list('throughput_mi_b_sec', flat=True).first(),
                "memoryRandRead": MemoryBenchmark.objects.filter(
                    provider=provider,
                    benchmark_name="Random_Read_Performance__Multi_threaded_"
                ).order_by('-created_at').values_list('throughput_mi_b_sec', flat=True).first(),
                "memoryRandWrite": MemoryBenchmark.objects.filter(
                    provider=provider,
                    benchmark_name="Random_Write_Performance__Multi_threaded_"
                ).order_by('-created_at').values_list('throughput_mi_b_sec', flat=True).first(),
                "randomReadDiskThroughput": DiskBenchmark.objects.filter(
                    provider=provider,
                    benchmark_name="FileIO_rndrd"
                ).order_by('-created_at').values_list('read_throughput_mb_ps', flat=True).first(),
                "randomWriteDiskThroughput": DiskBenchmark.objects.filter(
                    provider=provider,
                    benchmark_name="FileIO_rndwr"
                ).order_by('-created_at').values_list('write_throughput_mb_ps', flat=True).first(),
                "sequentialReadDiskThroughput": DiskBenchmark.objects.filter(
                    provider=provider,
                    benchmark_name="FileIO_seqrd"
                ).order_by('-created_at').values_list('read_throughput_mb_ps', flat=True).first(),
                "sequentialWriteDiskThroughput": DiskBenchmark.objects.filter(
                    provider=provider,
                    benchmark_name="FileIO_seqwr"
                ).order_by('-created_at').values_list('write_throughput_mb_ps', flat=True).first(),
                "networkDownloadSpeed": NetworkBenchmark.objects.filter(
                    provider=provider
                ).order_by('-created_at').values_list('mbit_per_second', flat=True).first(),
                "ping": {
                    region: {
                        "p2p": PingResult.objects.filter(
                            provider=provider,
                            region=region,
                            is_p2p=True
                        ).order_by('-created_at').values_list('ping_udp', flat=True)[:5].aggregate(avg_ping=Avg('ping_udp'))['avg_ping'],
                        "non_p2p": PingResult.objects.filter(
                            provider=provider,
                            region=region,
                            is_p2p=False
                        ).order_by('-created_at').values_list('ping_udp', flat=True)[:5].aggregate(avg_ping=Avg('ping_udp'))['avg_ping']
                    } for region in ["europe", "asia", "us"]
                }
            }
        }
        all_scores.append(scores)

    return JsonResponse({"providers": all_scores})


from django.db.models import Min, Max, Avg, Subquery, OuterRef

@api.get(
    "/providers/score_overview",
    tags=["Reputation"],
    summary="Retrieve an overview of provider scores",
    description="This endpoint provides an overview of provider scores, including minimum, maximum, and average values for each metric based on the latest scores for each provider."
)
def get_score_overview(request):
    # Filter providers whose latest NodeStatusHistory is_online=True
    latest_status_subquery = NodeStatusHistory.objects.filter(
        provider=OuterRef('pk')
    ).order_by('-timestamp').values('is_online')[:1]

    providers = Provider.objects.annotate(
        latest_status=Subquery(latest_status_subquery)
    ).filter(latest_status=True)

    # Calculate uptime for each provider
    def calculate_uptime(provider):
        statuses = NodeStatusHistory.objects.filter(provider=provider).order_by('timestamp')

        online_duration = timedelta(0)
        last_online_time = None

        for status in statuses:
            if status.is_online:
                last_online_time = status.timestamp
            elif last_online_time:
                online_duration += status.timestamp - last_online_time
                last_online_time = None

        if last_online_time is not None:
            online_duration += timezone.now() - last_online_time

        total_duration = timezone.now() - provider.created_at
        if total_duration.total_seconds() > 0:
            uptime_percentage = (online_duration.total_seconds() / total_duration.total_seconds()) * 100
        else:
            uptime_percentage = 0
        return uptime_percentage

    uptimes = [calculate_uptime(provider) for provider in providers]
    uptime_overview = {
        "min": min(uptimes) if uptimes else None,
        "max": max(uptimes) if uptimes else None,
        "avg": sum(uptimes) / len(uptimes) if uptimes else None,
    }
    overview = {
        "uptime": uptime_overview,
        "cpuMultiThreadScore": {
            "min": Provider.objects.annotate(latest_cpu_multi_thread_score=Subquery(
                CpuBenchmark.objects.filter(provider=OuterRef('pk'), benchmark_name="CPU Multi-thread Benchmark").order_by('-created_at').values('events_per_second')[:1]
            )).aggregate(min=Min('latest_cpu_multi_thread_score'))['min'],
            "max": Provider.objects.annotate(latest_cpu_multi_thread_score=Subquery(
                CpuBenchmark.objects.filter(provider=OuterRef('pk'), benchmark_name="CPU Multi-thread Benchmark").order_by('-created_at').values('events_per_second')[:1]
            )).aggregate(max=Max('latest_cpu_multi_thread_score'))['max'],
            "avg": Provider.objects.annotate(latest_cpu_multi_thread_score=Subquery(
                CpuBenchmark.objects.filter(provider=OuterRef('pk'), benchmark_name="CPU Multi-thread Benchmark").order_by('-created_at').values('events_per_second')[:1]
            )).aggregate(avg=Avg('latest_cpu_multi_thread_score'))['avg'],
        },
        "cpuSingleThreadScore": {
            "min": Provider.objects.annotate(latest_cpu_single_thread_score=Subquery(
                CpuBenchmark.objects.filter(provider=OuterRef('pk'), benchmark_name="CPU Single-thread Benchmark").order_by('-created_at').values('events_per_second')[:1]
            )).aggregate(min=Min('latest_cpu_single_thread_score'))['min'],
            "max": Provider.objects.annotate(latest_cpu_single_thread_score=Subquery(
                CpuBenchmark.objects.filter(provider=OuterRef('pk'), benchmark_name="CPU Single-thread Benchmark").order_by('-created_at').values('events_per_second')[:1]
            )).aggregate(max=Max('latest_cpu_single_thread_score'))['max'],
            "avg": Provider.objects.annotate(latest_cpu_single_thread_score=Subquery(
                CpuBenchmark.objects.filter(provider=OuterRef('pk'), benchmark_name="CPU Single-thread Benchmark").order_by('-created_at').values('events_per_second')[:1]
            )).aggregate(avg=Avg('latest_cpu_single_thread_score'))['avg'],
        },
        "successRate": {
            "min": Provider.objects.annotate(successful_tasks=Count('taskcompletion', filter=Q(taskcompletion__is_successful=True)),
                                             total_tasks=Count('taskcompletion'),
                                             success_rate=Case(
                                                 When(total_tasks=0, then=None),
                                                 default=(Cast('successful_tasks', FloatField()) / Cast('total_tasks', FloatField()) * 100)
                                             )).aggregate(min=Min('success_rate'))['min'],
            "max": Provider.objects.annotate(successful_tasks=Count('taskcompletion', filter=Q(taskcompletion__is_successful=True)),
                                             total_tasks=Count('taskcompletion'),
                                             success_rate=Case(
                                                 When(total_tasks=0, then=None),
                                                 default=(Cast('successful_tasks', FloatField()) / Cast('total_tasks', FloatField()) * 100)
                                             )).aggregate(max=Max('success_rate'))['max'],
            "avg": Provider.objects.annotate(successful_tasks=Count('taskcompletion', filter=Q(taskcompletion__is_successful=True)),
                                             total_tasks=Count('taskcompletion'),
                                             success_rate=Case(
                                                 When(total_tasks=0, then=None),
                                                 default=(Cast('successful_tasks', FloatField()) / Cast('total_tasks', FloatField()) * 100)
                                             )).aggregate(avg=Avg('success_rate'))['avg'],
        },
        "memorySeqRead": {
            "min": Provider.objects.annotate(latest_mem_seq_read=Subquery(
                MemoryBenchmark.objects.filter(provider=OuterRef('pk'), benchmark_name="Sequential_Read_Performance__Single_Thread_").order_by('-created_at').values('throughput_mi_b_sec')[:1]
            )).aggregate(min=Min('latest_mem_seq_read'))['min'],
            "max": Provider.objects.annotate(latest_mem_seq_read=Subquery(
                MemoryBenchmark.objects.filter(provider=OuterRef('pk'), benchmark_name="Sequential_Read_Performance__Single_Thread_").order_by('-created_at').values('throughput_mi_b_sec')[:1]
            )).aggregate(max=Max('latest_mem_seq_read'))['max'],
            "avg": Provider.objects.annotate(latest_mem_seq_read=Subquery(
                MemoryBenchmark.objects.filter(provider=OuterRef('pk'), benchmark_name="Sequential_Read_Performance__Single_Thread_").order_by('-created_at').values('throughput_mi_b_sec')[:1]
            )).aggregate(avg=Avg('latest_mem_seq_read'))['avg'],
        },
        "memorySeqWrite": {
            "min": Provider.objects.annotate(latest_mem_seq_write=Subquery(
                MemoryBenchmark.objects.filter(provider=OuterRef('pk'), benchmark_name="Sequential_Write_Performance__Single_Thread_").order_by('-created_at').values('throughput_mi_b_sec')[:1]
            )).aggregate(min=Min('latest_mem_seq_write'))['min'],
            "max": Provider.objects.annotate(latest_mem_seq_write=Subquery(
                MemoryBenchmark.objects.filter(provider=OuterRef('pk'), benchmark_name="Sequential_Write_Performance__Single_Thread_").order_by('-created_at').values('throughput_mi_b_sec')[:1]
            )).aggregate(max=Max('latest_mem_seq_write'))['max'],
            "avg": Provider.objects.annotate(latest_mem_seq_write=Subquery(
                MemoryBenchmark.objects.filter(provider=OuterRef('pk'), benchmark_name="Sequential_Write_Performance__Single_Thread_").order_by('-created_at').values('throughput_mi_b_sec')[:1]
            )).aggregate(avg=Avg('latest_mem_seq_write'))['avg'],
        },
        "memoryRandRead": {
            "min": Provider.objects.annotate(latest_mem_rand_read=Subquery(
                MemoryBenchmark.objects.filter(provider=OuterRef('pk'), benchmark_name="Random_Read_Performance__Multi_threaded_").order_by('-created_at').values('throughput_mi_b_sec')[:1]
            )).aggregate(min=Min('latest_mem_rand_read'))['min'],
            "max": Provider.objects.annotate(latest_mem_rand_read=Subquery(
                MemoryBenchmark.objects.filter(provider=OuterRef('pk'), benchmark_name="Random_Read_Performance__Multi_threaded_").order_by('-created_at').values('throughput_mi_b_sec')[:1]
            )).aggregate(max=Max('latest_mem_rand_read'))['max'],
            "avg": Provider.objects.annotate(latest_mem_rand_read=Subquery(
                MemoryBenchmark.objects.filter(provider=OuterRef('pk'), benchmark_name="Random_Read_Performance__Multi_threaded_").order_by('-created_at').values('throughput_mi_b_sec')[:1]
            )).aggregate(avg=Avg('latest_mem_rand_read'))['avg'],
        },
        "memoryRandWrite": {
            "min": Provider.objects.annotate(latest_mem_rand_write=Subquery(
                MemoryBenchmark.objects.filter(provider=OuterRef('pk'), benchmark_name="Random_Write_Performance__Multi_threaded_").order_by('-created_at').values('throughput_mi_b_sec')[:1]
            )).aggregate(min=Min('latest_mem_rand_write'))['min'],
            "max": Provider.objects.annotate(latest_mem_rand_write=Subquery(
                MemoryBenchmark.objects.filter(provider=OuterRef('pk'), benchmark_name="Random_Write_Performance__Multi_threaded_").order_by('-created_at').values('throughput_mi_b_sec')[:1]
            )).aggregate(max=Max('latest_mem_rand_write'))['max'],
            "avg": Provider.objects.annotate(latest_mem_rand_write=Subquery(
                MemoryBenchmark.objects.filter(provider=OuterRef('pk'), benchmark_name="Random_Write_Performance__Multi_threaded_").order_by('-created_at').values('throughput_mi_b_sec')[:1]
            )).aggregate(avg=Avg('latest_mem_rand_write'))['avg'],
        },
        "randomReadDiskThroughput": {
            "min": Provider.objects.annotate(latest_disk_random_read_throughput=Subquery(
                DiskBenchmark.objects.filter(provider=OuterRef('pk'), benchmark_name="FileIO_rndrd").order_by('-created_at').values('read_throughput_mb_ps')[:1]
            )).aggregate(min=Min('latest_disk_random_read_throughput'))['min'],
            "max": Provider.objects.annotate(latest_disk_random_read_throughput=Subquery(
                DiskBenchmark.objects.filter(provider=OuterRef('pk'), benchmark_name="FileIO_rndrd").order_by('-created_at').values('read_throughput_mb_ps')[:1]
            )).aggregate(max=Max('latest_disk_random_read_throughput'))['max'],
            "avg": Provider.objects.annotate(latest_disk_random_read_throughput=Subquery(
                DiskBenchmark.objects.filter(provider=OuterRef('pk'), benchmark_name="FileIO_rndrd").order_by('-created_at').values('read_throughput_mb_ps')[:1]
            )).aggregate(avg=Avg('latest_disk_random_read_throughput'))['avg'],
        },
        "randomWriteDiskThroughput": {
            "min": Provider.objects.annotate(latest_disk_random_write_throughput=Subquery(
                DiskBenchmark.objects.filter(provider=OuterRef('pk'), benchmark_name="FileIO_rndwr").order_by('-created_at').values('write_throughput_mb_ps')[:1]
            )).aggregate(min=Min('latest_disk_random_write_throughput'))['min'],
            "max": Provider.objects.annotate(latest_disk_random_write_throughput=Subquery(
                DiskBenchmark.objects.filter(provider=OuterRef('pk'), benchmark_name="FileIO_rndwr").order_by('-created_at').values('write_throughput_mb_ps')[:1]
            )).aggregate(max=Max('latest_disk_random_write_throughput'))['max'],
            "avg": Provider.objects.annotate(latest_disk_random_write_throughput=Subquery(
                DiskBenchmark.objects.filter(provider=OuterRef('pk'), benchmark_name="FileIO_rndwr").order_by('-created_at').values('write_throughput_mb_ps')[:1]
            )).aggregate(avg=Avg('latest_disk_random_write_throughput'))['avg'],
        },
        "sequentialReadDiskThroughput": {
            "min": Provider.objects.annotate(latest_disk_sequential_read_throughput=Subquery(
                DiskBenchmark.objects.filter(provider=OuterRef('pk'), benchmark_name="FileIO_seqrd").order_by('-created_at').values('read_throughput_mb_ps')[:1]
            )).aggregate(min=Min('latest_disk_sequential_read_throughput'))['min'],
            "max": Provider.objects.annotate(latest_disk_sequential_read_throughput=Subquery(
                DiskBenchmark.objects.filter(provider=OuterRef('pk'), benchmark_name="FileIO_seqrd").order_by('-created_at').values('read_throughput_mb_ps')[:1]
            )).aggregate(max=Max('latest_disk_sequential_read_throughput'))['max'],
            "avg": Provider.objects.annotate(latest_disk_sequential_read_throughput=Subquery(
                DiskBenchmark.objects.filter(provider=OuterRef('pk'), benchmark_name="FileIO_seqrd").order_by('-created_at').values('read_throughput_mb_ps')[:1]
            )).aggregate(avg=Avg('latest_disk_sequential_read_throughput'))['avg'],
        },
        "sequentialWriteDiskThroughput": {
            "min": Provider.objects.annotate(latest_disk_sequential_write_throughput=Subquery(
                DiskBenchmark.objects.filter(provider=OuterRef('pk'), benchmark_name="FileIO_seqwr").order_by('-created_at').values('write_throughput_mb_ps')[:1]
            )).aggregate(min=Min('latest_disk_sequential_write_throughput'))['min'],
            "max": Provider.objects.annotate(latest_disk_sequential_write_throughput=Subquery(
                DiskBenchmark.objects.filter(provider=OuterRef('pk'), benchmark_name="FileIO_seqwr").order_by('-created_at').values('write_throughput_mb_ps')[:1]
            )).aggregate(max=Max('latest_disk_sequential_write_throughput'))['max'],
            "avg": Provider.objects.annotate(latest_disk_sequential_write_throughput=Subquery(
                DiskBenchmark.objects.filter(provider=OuterRef('pk'), benchmark_name="FileIO_seqwr").order_by('-created_at').values('write_throughput_mb_ps')[:1]
            )).aggregate(avg=Avg('latest_disk_sequential_write_throughput'))['avg'],
        },
        "networkDownloadSpeed": {
            "min": Provider.objects.annotate(latest_network_download_speed=Subquery(
                NetworkBenchmark.objects.filter(provider=OuterRef('pk')).order_by('-created_at').values('mbit_per_second')[:1]
            )).aggregate(min=Min('latest_network_download_speed'))['min'],
            "max": Provider.objects.annotate(latest_network_download_speed=Subquery(
                NetworkBenchmark.objects.filter(provider=OuterRef('pk')).order_by('-created_at').values('mbit_per_second')[:1]
            )).aggregate(max=Max('latest_network_download_speed'))['max'],
            "avg": Provider.objects.annotate(latest_network_download_speed=Subquery(
                NetworkBenchmark.objects.filter(provider=OuterRef('pk')).order_by('-created_at').values('mbit_per_second')[:1]
            )).aggregate(avg=Avg('latest_network_download_speed'))['avg'],
        },

    }
    regions = ["europe", "asia", "us"]
    ping_overview = {}

    for region in regions:
        ping_overview[region] = {
            "min": Provider.objects.annotate(latest_ping=Subquery(
                PingResult.objects.filter(provider=OuterRef('pk'), region=region).order_by('-created_at').values('ping_udp')[:1]
            )).aggregate(min=Min('latest_ping'))['min'],
            "max": Provider.objects.annotate(latest_ping=Subquery(
                PingResult.objects.filter(provider=OuterRef('pk'), region=region).order_by('-created_at').values('ping_udp')[:1]
            )).aggregate(max=Max('latest_ping'))['max'],
            "avg": Provider.objects.annotate(latest_ping=Subquery(
                PingResult.objects.filter(provider=OuterRef('pk'), region=region).order_by('-created_at').values('ping_udp')[:1]
            )).aggregate(avg=Avg('latest_ping'))['avg'],
        }
    overview['ping'] = ping_overview

    return JsonResponse({"overview": overview})


from django.db.models import Avg
from pydantic import BaseModel
from enum import Enum
class PerformanceLevel(str, Enum):
    above_expected = "above expected"
    as_expected = "as expected"
    slightly_below_expected = "slightly below expected"
    worse = "worse"

class GPUPerformanceResponse(BaseModel):
    node_id: str
    performance: PerformanceLevel
    provider_avg_gflops: float
    identical_gpus_avg_gflops: float
    error: str = None  # Optional field for error messages

@api.get(
    "/provider/gpu/performance/comparison/{node_id}",
    tags=["Reputation"],
    summary="Evaluate GPU performance for a specific provider",
    description="This endpoint evaluates the GPU performance of a specific provider compared to other identical GPU models in the database.",
    response={200: GPUPerformanceResponse}
)
def evaluate_gpu_performance(request, node_id: str):
    try:
        provider = Provider.objects.get(node_id=node_id)
    except Provider.DoesNotExist:
        return JsonResponse({"error": "Provider not found"}, status=200)

    # Fetch the GPU tasks for the given provider
    provider_gpu_tasks = GPUTask.objects.filter(provider=provider)

    if not provider_gpu_tasks.exists():
        return JsonResponse({"error": "No GPU tasks found for this provider"}, status=200)

    # Calculate the average gpu_burn_gflops for the provider's GPUs
    provider_avg_gflops = provider_gpu_tasks.aggregate(avg_gflops=Avg('gpu_burn_gflops'))['avg_gflops']

    # Calculate the average gpu_burn_gflops for identical GPU models in the database
    identical_gpus_avg_gflops = GPUTask.objects.filter(
        name__in=provider_gpu_tasks.values_list('name', flat=True)
    ).exclude(provider=provider).aggregate(avg_gflops=Avg('gpu_burn_gflops'))['avg_gflops']

    if identical_gpus_avg_gflops is None:
        return JsonResponse({"error": "No comparison data available"}, status=200)

    # Compare the provider's GPU performance with the average
    if provider_avg_gflops >= identical_gpus_avg_gflops * 1.05:
        performance = "above expected"
    elif provider_avg_gflops >= identical_gpus_avg_gflops * 0.95:
        performance = "as expected"
    elif provider_avg_gflops >= identical_gpus_avg_gflops * 0.85:
        performance = "slightly below expected"
    else:
        performance = "worse"

    return JsonResponse({
        "node_id": node_id,
        "performance": performance,
        "provider_avg_gflops": provider_avg_gflops,
        "identical_gpus_avg_gflops": identical_gpus_avg_gflops
    })