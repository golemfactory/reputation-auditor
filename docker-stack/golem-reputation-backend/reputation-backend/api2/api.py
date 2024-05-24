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