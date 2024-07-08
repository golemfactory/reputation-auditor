from api.models import GPUTask
from api.models import BlacklistedProvider, BlacklistedOperator
from django.db.models import Count, Q
from collections import defaultdict
from django.http import JsonResponse
from django.db.models import Value as V
from ninja import NinjaAPI
from api.models import Provider, TaskCompletion, MemoryBenchmark, DiskBenchmark, CpuBenchmark, NetworkBenchmark, Offer
from .schemas import TaskParticipationSchema, ProviderDetailsResponseSchema
import redis
import json
redis_client = redis.Redis(host='redis', port=6379, db=0)
api = NinjaAPI(
    title="Golem Reputation Stats API",
    version="1.0.0",
    description="Stats API",
    urls_namespace="stats:api",
    docs_url="/docs/"
)


def get_summary(deviation):
    if deviation <= 5:
        return "stable"
    elif deviation <= 15:
        return "varying"
    return "unstable"


def calculate_deviation(scores, normalization_factors=None):
    if not scores or len(scores) < 2:
        print("Not enough scores to calculate deviation")
        return 0
    if normalization_factors:
        scores = [score / factor for score,
                  factor in zip(scores, normalization_factors)]

    # Calculate relative changes
    relative_changes = [(scores[i] - scores[i - 1]) / scores[i - 1]
                        for i in range(1, len(scores))]

    avg_change = sum(relative_changes) / len(relative_changes)
    deviation_percent = (sum((change - avg_change) ** 2 for change in relative_changes)
                         ** 0.5 / len(relative_changes) ** 0.5) * 100
    return deviation_percent


@api.get("/benchmark/cpu/{node_id}")
def get_benchmark(request, node_id: str):
    provider = Provider.objects.filter(node_id=node_id).first()
    if not provider:
        return JsonResponse({"detail": "Provider not found"}, status=404)

    benchmarks = CpuBenchmark.objects.filter(provider=provider).values(
        'benchmark_name', 'events_per_second', 'threads', 'created_at'
    )
    result = {"data": {"single": [], "multi": []},
              "singleDeviation": 0, "multiDeviation": 0, "summary": ""}
    single_scores, multi_scores = [], []
    single_factors, multi_factors = [], []

    for benchmark in benchmarks:
        score_entry = {"score": benchmark['events_per_second'],
                       "timestamp": benchmark['created_at'].timestamp()}
        if "Single-thread" in benchmark['benchmark_name']:
            result["data"]["single"].append(score_entry)
            single_scores.append(benchmark['events_per_second'])
            single_factors.append(benchmark['threads'])
        else:
            result["data"]["multi"].append(score_entry)
            multi_scores.append(benchmark['events_per_second'])
            multi_factors.append(benchmark['threads'])

    result['singleDeviation'] = calculate_deviation(
        single_scores, single_factors)
    result['multiDeviation'] = calculate_deviation(multi_scores, multi_factors)

    result['summary'] = {
        "single": get_summary(result['singleDeviation']),
        "multi": get_summary(result['multiDeviation'])
    }

    return JsonResponse(result)


@api.get("/benchmark/memory/seq/single/{node_id}")
def get_seq_memory_benchmark(request, node_id: str):
    provider = Provider.objects.filter(node_id=node_id).first()
    if not provider:
        return JsonResponse({"detail": "Provider not found"}, status=404)

    benchmarks = MemoryBenchmark.objects.filter(
        provider=provider,
        benchmark_name__in=[
            "Sequential_Write_Performance__Single_Thread_",
            "Sequential_Read_Performance__Single_Thread_"
        ]).values('benchmark_name', 'throughput_mi_b_sec', 'created_at')

    result = {"data": {"sequential_write_single": [], "sequential_read_single": [
    ]}, "writeDeviation": 0, "readDeviation": 0, "summary": ""}
    write_scores, read_scores = [], []

    for benchmark in benchmarks:
        score_entry = {"score": benchmark['throughput_mi_b_sec'],
                       "timestamp": benchmark['created_at'].timestamp()}
        if "Write" in benchmark['benchmark_name']:
            result["data"]["sequential_write_single"].append(score_entry)
            write_scores.append(benchmark['throughput_mi_b_sec'])
        else:
            result["data"]["sequential_read_single"].append(score_entry)
            read_scores.append(benchmark['throughput_mi_b_sec'])

    result['writeDeviation'] = calculate_deviation(write_scores)
    result['readDeviation'] = calculate_deviation(read_scores)

    result['summary'] = {
        "sequential_write_single": get_summary(result['writeDeviation']),
        "sequential_read_single": get_summary(result['readDeviation'])
    }

    return JsonResponse(result)


@api.get("/benchmark/memory/rand/multi/{node_id}")
def get_rand_memory_benchmark(request, node_id: str):
    provider = Provider.objects.filter(node_id=node_id).first()
    if not provider:
        return JsonResponse({"detail": "Provider not found"}, status=404)

    benchmarks = MemoryBenchmark.objects.filter(
        provider=provider,
        benchmark_name__in=[
            "Random_Write_Performance__Multi_threaded_",
            "Random_Read_Performance__Multi_threaded_"
        ]).values('benchmark_name', 'throughput_mi_b_sec', 'created_at')

    result = {
        "data": {
            "random_write_multi": [],
            "random_read_multi": []
        },
        "writeDeviation": 0,
        "readDeviation": 0,
        "summary": ""
    }
    write_scores, read_scores = [], []

    for benchmark in benchmarks:
        score_entry = {"score": benchmark['throughput_mi_b_sec'],
                       "timestamp": benchmark['created_at'].timestamp()}
        if "Write" in benchmark['benchmark_name']:
            result["data"]["random_write_multi"].append(score_entry)
            write_scores.append(benchmark['throughput_mi_b_sec'])
        else:
            result["data"]["random_read_multi"].append(score_entry)
            read_scores.append(benchmark['throughput_mi_b_sec'])

    result['writeDeviation'] = calculate_deviation(write_scores)
    result['readDeviation'] = calculate_deviation(read_scores)

    result['summary'] = {
        "random_write_multi": get_summary(result['writeDeviation']),
        "random_read_multi": get_summary(result['readDeviation'])
    }

    return JsonResponse(result)


@api.get("/benchmark/disk/fileio_rand/{node_id}")
def get_fileio_disk_benchmark(request, node_id: str):
    provider = Provider.objects.filter(node_id=node_id).first()
    if not provider:
        return JsonResponse({"detail": "Provider not found"}, status=404)

    benchmarks = DiskBenchmark.objects.filter(
        provider=provider,
        benchmark_name__in=["FileIO_rndrd", "FileIO_rndwr"]
    ).values('benchmark_name', 'read_throughput_mb_ps', 'write_throughput_mb_ps', 'created_at')

    result = {
        "data": {
            "fileio_rndrd": [],
            "fileio_rndwr": []
        },
        "readDeviation": 0,
        "writeDeviation": 0,
        "summary": ""
    }
    read_scores, write_scores = [], []

    for benchmark in benchmarks:
        if "rndrd" in benchmark['benchmark_name']:
            score_entry = {"score": benchmark['read_throughput_mb_ps'],
                           "timestamp": benchmark['created_at'].timestamp()}
            result["data"]["fileio_rndrd"].append(score_entry)
            read_scores.append(benchmark['read_throughput_mb_ps'])
        else:
            score_entry = {"score": benchmark['write_throughput_mb_ps'],
                           "timestamp": benchmark['created_at'].timestamp()}
            result["data"]["fileio_rndwr"].append(score_entry)
            write_scores.append(benchmark['write_throughput_mb_ps'])

    result['readDeviation'] = calculate_deviation(read_scores)
    result['writeDeviation'] = calculate_deviation(write_scores)

    result['summary'] = {
        "fileio_rndrd": get_summary(result['readDeviation']),
        "fileio_rndwr": get_summary(result['writeDeviation'])
    }

    return JsonResponse(result)


@api.get("/benchmark/disk/fileio_seq/{node_id}")
def get_fileio_seq_disk_benchmark(request, node_id: str):
    provider = Provider.objects.filter(node_id=node_id).first()
    if not provider:
        return JsonResponse({"detail": "Provider not found"}, status=404)

    benchmarks = DiskBenchmark.objects.filter(
        provider=provider,
        benchmark_name__in=["FileIO_seqrd", "FileIO_seqwr"]
    ).values('benchmark_name', 'read_throughput_mb_ps', 'write_throughput_mb_ps', 'created_at')

    result = {
        "data": {
            "fileio_seqrd": [],
            "fileio_seqwr": []
        },
        "readDeviation": 0,
        "writeDeviation": 0,
        "summary": ""
    }
    read_scores, write_scores = [], []

    for benchmark in benchmarks:
        if "seqrd" in benchmark['benchmark_name']:
            score_entry = {"score": benchmark['read_throughput_mb_ps'],
                           "timestamp": benchmark['created_at'].timestamp()}
            result["data"]["fileio_seqrd"].append(score_entry)
            read_scores.append(benchmark['read_throughput_mb_ps'])
        else:
            score_entry = {"score": benchmark['write_throughput_mb_ps'],
                           "timestamp": benchmark['created_at'].timestamp()}
            result["data"]["fileio_seqwr"].append(score_entry)
            write_scores.append(benchmark['write_throughput_mb_ps'])

    result['readDeviation'] = calculate_deviation(read_scores)
    result['writeDeviation'] = calculate_deviation(write_scores)

    result['summary'] = {
        "fileio_seqrd": get_summary(result['readDeviation']),
        "fileio_seqwr": get_summary(result['writeDeviation'])
    }

    return JsonResponse(result)


@api.get("/benchmark/network/{node_id}")
def get_network_benchmark(request, node_id: str):
    provider = Provider.objects.filter(node_id=node_id).first()
    if not provider:
        return JsonResponse({"detail": "Provider not found"}, status=404)

    benchmarks = NetworkBenchmark.objects.filter(provider=provider).values(
        'mbit_per_second', 'created_at'
    )

    scores = [benchmark['mbit_per_second'] for benchmark in benchmarks]

    result = {
        "data": [{"score": benchmark['mbit_per_second'], "timestamp": benchmark['created_at'].timestamp()} for benchmark in benchmarks],
        "deviation": calculate_deviation(scores),
        "summary": get_summary(calculate_deviation(scores))
    }

    return JsonResponse(result)


@api.get("/provider/{node_id}/details", response={200: ProviderDetailsResponseSchema})
def get_provider_details(request, node_id: str):
    provider = Provider.objects.filter(node_id=node_id).first()
    if not provider:
        return api.create_response(request, {"detail": "Provider not found"}, status=404)

    offers = Offer.objects.filter(provider=provider).select_related(
        'task').order_by('-created_at')

    processed_tasks = set()
    task_participations = []

    for offer in offers:
        if offer.task_id in processed_tasks:
            continue
        processed_tasks.add(offer.task_id)

        task_entry = TaskParticipationSchema(
            task_id=offer.task_id,
            completion_status="",
            error_message=None,
            cost=None,
            task_started_at=int(offer.task.started_at.timestamp())
        )

        if offer.accepted:
            try:
                completion = TaskCompletion.objects.get(
                    task_id=offer.task_id, provider=provider)
                try:
                    parts = completion.task_name.split()
                    benchmark_type = parts[1] if len(
                        parts) > 1 else completion.task_name
                except IndexError:
                    # Default or fallback value if task_name is not in the expected format
                    benchmark_type = completion.task_name

                if completion.is_successful:
                    task_entry.completion_status = "Completed Successfully"
                    task_entry.error_message = None
                else:
                    task_entry.completion_status = "Failed"
                    # Update the error message to include the specific benchmark type
                    task_entry.error_message = "{} benchmark - {}".format(
                        benchmark_type.capitalize(), completion.error_message)
                task_entry.cost = completion.cost
            except TaskCompletion.DoesNotExist:
                task_entry.completion_status = "Accepted offer, but the task was not started. Reason unknown."
        else:
            task_entry.completion_status = "Offer Rejected"
            task_entry.error_message = offer.reason

        task_participations.append(task_entry)

    # Sort task_participations by 'task_id'
    task_participations_sorted = sorted(
        task_participations, key=lambda x: x.task_id)

    # Calculate overall task success rate
    successful_tasks = TaskCompletion.objects.filter(
        provider=provider, is_successful=True).count()
    total_tasks = TaskCompletion.objects.filter(provider=provider).count()
    success_rate = (successful_tasks / total_tasks *
                    100) if total_tasks > 0 else None

    return ProviderDetailsResponseSchema(
        offer_history=[],  # Populate as needed
        task_participation=task_participations_sorted,
        success_rate=success_rate  # Add success rate to the response
    )


@api.get("/providers/online")
def online_provider_summary(request):

    # Get the success rate for each provider
    providers = Provider.objects.annotate(
        success_count=Count('taskcompletion', filter=Q(
            taskcompletion__is_successful=True)),
        total_count=Count('taskcompletion')
    ).all()

    # Get the blacklist status for each provider
    blacklisted_providers = set(
        BlacklistedProvider.objects.values_list('provider__node_id', flat=True))
    blacklisted_wallets = set(
        BlacklistedOperator.objects.values_list('wallet', flat=True))

    result = []
    for provider in providers:
        success_rate = (provider.success_count / provider.total_count *
                        100) if provider.total_count > 0 else None
        is_blacklisted_provider = provider.node_id in blacklisted_providers

        # Determine the correct payment address key based on network
        payment_address_key = 'golem.com.payment.platform.erc20-mainnet-glm.address' if provider.network == 'mainnet' else 'golem.com.payment.platform.erc20-holesky-tglm.address'
        is_blacklisted_wallet = provider.payment_addresses.get(
            payment_address_key) in blacklisted_wallets

        result.append({
            "node_id": provider.node_id,
            "success_rate": success_rate,
            "is_blacklisted_provider": is_blacklisted_provider,
            "is_blacklisted_wallet": is_blacklisted_wallet
        })

    return JsonResponse(result, safe=False)


@api.get("/benchmark/gpu/{node_id}")
def get_gpu_benchmark(request, node_id: str):
    provider = Provider.objects.filter(node_id=node_id).first()
    if not provider:
        return JsonResponse({"detail": "Provider not found"}, status=404)

    benchmarks = GPUTask.objects.filter(provider=provider).values(
        'gpu_burn_gflops', 'created_at'
    )

    scores = [benchmark['gpu_burn_gflops'] for benchmark in benchmarks]

    result = {
        "data": [{"score": benchmark['gpu_burn_gflops'], "timestamp": benchmark['created_at'].timestamp()} for benchmark in benchmarks],
        "deviation": calculate_deviation(scores),
        "summary": get_summary(calculate_deviation(scores))
    }

    return JsonResponse(result)


@api.get("/network/uptime", tags=["Stats"])
def get_cached_uptime(request):
    """
    Retrieve cached provider uptime statistics from Redis.

    Returns:
        JsonResponse: A JSON response containing the uptime statistics.
    """
    uptime_data = redis_client.get('stats_provider_uptime')
    if uptime_data:
        return JsonResponse(json.loads(uptime_data))
    else:
        return JsonResponse({"error": "Uptime data not available"}, status=503)


@api.get("/network/success-rate", tags=["Stats"])
def get_cached_success_rate(request):
    """
    Retrieve cached provider success rate statistics from Redis.

    Returns:
        JsonResponse: A JSON response containing the success rate statistics.
    """
    success_rate_data = redis_client.get('stats_provider_success_ratio')
    if success_rate_data:
        return JsonResponse(json.loads(success_rate_data))
    else:
        return JsonResponse({"error": "Success rate data not available"}, status=503)


from api.models import PingResult
@api.get("/ping/average/{node_id}")
def get_average_ping(request, node_id: str):
    provider = Provider.objects.filter(node_id=node_id).first()
    if not provider:
        return JsonResponse({"detail": "Provider not found"}, status=404)

    regions = ['europe', 'asia', 'us']
    p2p_averages = {}
    relay_averages = {}

    for region in regions:
        p2p_pings = PingResult.objects.filter(
            provider=provider, is_p2p=True, region=region
        ).order_by('-created_at')[:3]

        relay_pings = PingResult.objects.filter(
            provider=provider, is_p2p=False, region=region
        ).order_by('-created_at')[:3]

        p2p_avg_tcp = sum(ping.ping_tcp for ping in p2p_pings) / len(p2p_pings) if p2p_pings else None
        p2p_avg_udp = sum(ping.ping_udp for ping in p2p_pings) / len(p2p_pings) if p2p_pings else None
        relay_avg_tcp = sum(ping.ping_tcp for ping in relay_pings) / len(relay_pings) if relay_pings else None
        relay_avg_udp = sum(ping.ping_udp for ping in relay_pings) / len(relay_pings) if relay_pings else None

        p2p_averages[region] = {"tcp": p2p_avg_tcp, "udp": p2p_avg_udp}
        relay_averages[region] = {"tcp": relay_avg_tcp, "udp": relay_avg_udp}

    result = {
        "p2p": p2p_averages,
        "relay": relay_averages
    }

    return JsonResponse(result)


from django.db.models import Avg
from django.utils import timezone
from datetime import timedelta

@api.get("/network/average-latency")
def get_network_average_latency(request):
    regions = ['europe', 'asia', 'us']
    result = {
        "p2p": {},
        "relay": {}
    }

    # Calculate the timestamp for 3 hours ago
    three_hours_ago = timezone.now() - timedelta(hours=3)

    for source_region in regions:
        result["p2p"][source_region] = {}
        result["relay"][source_region] = {}

        for target_region in regions:
            if source_region != target_region:
                p2p_avg = PingResult.objects.filter(
                    is_p2p=True,
                    region=target_region,
                    created_at__gte=three_hours_ago,
                    provider__node_id__startswith=source_region  # Assuming node_id starts with region name
                ).aggregate(
                    avg_tcp=Avg('ping_tcp'),
                    avg_udp=Avg('ping_udp')
                )

                relay_avg = PingResult.objects.filter(
                    is_p2p=False,
                    region=target_region,
                    created_at__gte=three_hours_ago,
                    provider__node_id__startswith=source_region  # Assuming node_id starts with region name
                ).aggregate(
                    avg_tcp=Avg('ping_tcp'),
                    avg_udp=Avg('ping_udp')
                )

                result["p2p"][source_region][target_region] = {
                    "tcp": p2p_avg['avg_tcp'],
                    "udp": p2p_avg['avg_udp']
                }
                result["relay"][source_region][target_region] = {
                    "tcp": relay_avg['avg_tcp'],
                    "udp": relay_avg['avg_udp']
                }

    return JsonResponse(result)