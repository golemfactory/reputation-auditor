from ninja import NinjaAPI, Path
from .models import DiskBenchmark, CpuBenchmark, MemoryBenchmark, Provider, TaskCompletion, PingResult, NodeStatusHistory, Task, Offer
from .schemas import DiskBenchmarkSchema, CpuBenchmarkSchema, MemoryBenchmarkSchema, TaskCompletionSchema, ProviderSuccessRate, TaskCreateSchema, TaskUpdateSchema, ProposalSchema, TaskCostUpdateSchema, BulkTaskCostUpdateSchema, BulkBenchmarkSchema
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from typing import Any, Dict, List
import json
from collections import defaultdict
from django.db.models import Avg, Count, Q
from .tasks import benchmark_providers_task
from .bulkutils import process_disk_benchmark, process_cpu_benchmark, process_memory_benchmark, process_network_benchmark, process_gpu_task
api = NinjaAPI(
    title="Golem Reputation API",
    version="1.0.0",
    description="API for Golem Reputation Backend",
    urls_namespace="api:api",
    docs_url="/docs/"
)
import redis
from datetime import datetime, timedelta
from ninja.security import HttpBearer
import os



class AuthBearer(HttpBearer):
    def authenticate(self, request, token):
        if token == os.environ.get("BACKEND_API_TOKEN"):
            return token

from .scoring import get_provider_benchmark_scores
from django.db.models.functions import Coalesce

r = redis.Redis(host='redis', port=6379, db=0)




@api.get("/providers/scores", tags=["Reputation"])
def list_provider_scores(request, network: str = 'polygon'):
    """
    Retrieve provider scores for a specified network.

    This endpoint fetches provider scores from Redis based on the specified network.
    The scores are precomputed and stored in Redis by the `update_provider_scores` task.

    Args:
        request: The HTTP request object.
        network (str): The network for which to retrieve provider scores. 
                       Valid values are 'polygon', 'mainnet', 'goerli', 'mumbai', and 'holesky'.

    Returns:
        JsonResponse: A JSON response containing the provider scores or an error message.

    Raises:
        JsonResponse: If the network is not found or if the data is not available in Redis.

    Example:
        GET /providers/scores?network=polygon
        Response:
        {
            "providers": [
                {
                    "providerId": "provider1",
                    "scores": {
                        "successRate": 0.95,
                        "uptime": 0.99
                    }
                },
                ...
            ],
            "untestedProviders": [
                {
                    "providerId": "provider2",
                    "scores": {
                        "uptime": 0.98
                    }
                },
                ...
            ],
            "rejectedProviders": [
                {
                    "providerId": "provider3",
                    "reason": "Consecutive failures: 6. Next eligible date: 2023-10-01T00:00:00Z"
                },
                ...
            ],
            "rejectedOperators": [
                {
                    "operator": {
                        "walletAddress": "0x1234567890abcdef",
                    },
                    "reason": "CPU benchmark deviation: multi=0.25, single=0.30 over threshold 0.20. Possibly overprovisioned."
                },
                ...
            ],
            "totalRejectedProvidersMainnet": 5,
            "totalOnlineProvidersMainnet": 50,
            "totalOnlineProvidersTestnet": 20
        }
    """
    if network == 'polygon' or network == 'mainnet':
        response = r.get('provider_scores_v1_mainnet')
    elif network == 'goerli' or network == 'mumbai' or network == 'holesky':
        response = r.get('provider_scores_v1_testnet')
    else:
        return JsonResponse({"error": "Network not found"}, status=404)

    if response:
        return json.loads(response)
    else:
        # Handle the case where data is not yet available in Redis
        return JsonResponse({"error": "Data not available"}, status=503)



@api.post("/benchmark/bulk", auth=AuthBearer(), include_in_schema=False,)
def create_bulk_benchmark(request, bulk_data: BulkBenchmarkSchema):
    organized_data = {"disk": [], "cpu": [], "memory": [], "network": [], "gpu": []}
    for benchmark in bulk_data.benchmarks:
        organized_data[benchmark.type].append(benchmark.data)

    disk_response = process_disk_benchmark(organized_data["disk"])
    cpu_response = process_cpu_benchmark(organized_data["cpu"])
    memory_response = process_memory_benchmark(organized_data["memory"])
    network_response = process_network_benchmark(organized_data["network"])
    gpu_response = process_gpu_task(organized_data["gpu"])
    
    return {
        "disk": disk_response,
        "cpu": cpu_response,
        "memory": memory_response,
        "network": network_response,
        "gpu": gpu_response
    }

    

@api.post("/submit/task/status/bulk", auth=AuthBearer(), include_in_schema=False,)
def create_bulk_task_completion(request, data: List[TaskCompletionSchema]):
    task_completion_data = []
    errors = []

    for item in data:
        try:
            provider = Provider.objects.filter(node_id=item.node_id).first()
            task = Task.objects.filter(id=item.task_id).first()

            if not provider or not task:
                errors.append(f"Provider or Task not found for item with node_id {item.node_id} and task_id {item.task_id}")
                continue

            task_completion_data.append(TaskCompletion(
                provider=provider,
                task=task,
                task_name=item.task_name,
                is_successful=item.is_successful,
                error_message=item.error_message,
                type=item.type,
            ))
        except Exception as e:
            errors.append(f"Error processing item with node_id {item.node_id}: {str(e)}")

    TaskCompletion.objects.bulk_create(task_completion_data)

    if errors:
        return {"status": "error", "message": "Errors occurred during processing", "errors": errors}
    else:
        return {"status": "success", "message": f"Bulk task completion data saved successfully, processed {len(task_completion_data)} items."}



@api.get("scores/task", response=List[ProviderSuccessRate], include_in_schema=False,)
def provider_success_rate(request):
    # Get all providers
    providers = Provider.objects.annotate(
        total_tasks=Count('taskcompletion'),
        successful_tasks=Count('taskcompletion', filter=Q(taskcompletion__is_successful=True))
    )

    # Calculate success rate and prepare response
    success_rates = sorted(
        [
            {
                "node_id": provider.node_id,  # Unique Node ID
                "name": provider.name,  # Name of the provider
                "runtime_version": provider.runtime_version,  # Runtime Version
                "wallet_address": provider.payment_addresses,  # Wallet Address in JSON
                "success_rate": (provider.successful_tasks / provider.total_tasks * 100) if provider.total_tasks > 0 else 0  # Calculating success rate
            }
            for provider in providers
        ],
        key=lambda x: x["success_rate"],  # Sorting by success rate
        reverse=True  # Descending order
    )

    return success_rates

    
    



# @api.get("/provider/{node_id}/scores", response=dict)
# def get_provider_scores(request, node_id: str):
#     try:
#         provider = get_object_or_404(Provider, node_id=node_id)
#         disk_benchmarks = (
#             DiskBenchmark.objects.filter(provider=provider)
#             .values("benchmark_name")
#             .annotate(
#                 avg_read_throughput=Avg("read_throughput_mb_ps"),
#                 avg_write_throughput=Avg("write_throughput_mb_ps"),
#                 latency_95th_percentile=Avg("latency_95th_percentile_ms"),
#             )[:5]
#         )

#         memory_benchmarks = (
#             MemoryBenchmark.objects.filter(provider=provider)
#             .values("benchmark_name")
#             .annotate(
#                 avg_total_data_transferred=Avg("total_data_transferred_mi_b"),
#                 avg_throughput=Avg("throughput_mi_b_sec"),
#                 avg_latency_95th_percentile=Avg("latency_95th_percentile_ms"),
#             )[:5]
#         )

#         cpu_benchmarks = (
#             CpuBenchmark.objects.filter(provider=provider)
#             .values("benchmark_name")
#             .annotate(
#                 avg_events_per_second=Avg("events_per_second"),
#                 total_events=Avg("total_events"),
#                 threads=Avg("threads"),
#             )[:5]
#         )

#         avg_ping = (
#             PingResult.objects.filter(provider=provider)
#             .aggregate(
#                 avg_ping_tcp=Avg("ping_tcp"),
#                 avg_ping_udp=Avg("ping_udp")
#             )
#         )

#         uptime_percentage = (
#             NodeStatus.objects.filter(provider=provider)
#             .aggregate(uptime=Avg("uptime_percentage"))
#             .get("uptime", 0)
#         )
#         task_counts = TaskCompletion.objects.filter(provider=provider).aggregate(
#         total=Count('id'),
#         successful=Count('id', filter=Q(is_successful=True)))

#         success_rate = (task_counts['successful'] / task_counts['total'] * 100) if task_counts['total'] > 0 else 0

#         disk_scores = [{"benchmark_name": db["benchmark_name"], "avg_read_throughput": db["avg_read_throughput"], 
#                         "avg_write_throughput": db["avg_write_throughput"], "latency_95th_percentile": db["latency_95th_percentile"]} 
#                         for db in disk_benchmarks]

#         memory_scores = [{"benchmark_name": mb["benchmark_name"], "avg_total_data_transferred": mb["avg_total_data_transferred"], 
#                         "avg_throughput": mb["avg_throughput"], "avg_latency_95th_percentile": mb["avg_latency_95th_percentile"]} 
#                         for mb in memory_benchmarks]

#         cpu_scores = [{"benchmark_name": cb["benchmark_name"], "avg_events_per_second": cb["avg_events_per_second"], 
#                         "total_events": cb["total_events"], "threads": cb["threads"]} 
#                     for cb in cpu_benchmarks]

#         scores = {
#             "disk": disk_scores,
#             "memory": memory_scores,
#             "cpu": cpu_scores,
#             "ping": avg_ping,
#             "uptime_percentage": uptime_percentage,
#             "task_success_rate": success_rate
#         }

#         return scores
#     except Exception as e:
#         print(e)
#         return {"status": "error", "message": "Error retrieving provider scores",}
    

from django.utils import timezone
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Avg, StdDev, FloatField, Q, Subquery, OuterRef, F
from django.db.models.functions import Cast
from .models import BlacklistedOperator, BlacklistedProvider
@api.get(
    "/blacklisted-operators",
    tags=["Blacklist"],
    summary="Retrieve a list of blacklisted operator wallets",
    description="""
    This endpoint retrieves a list of wallets associated with blacklisted operators.
    The response is a list of wallet addresses that have been blacklisted.
    """,
    response=List[str]
)
def blacklisted_operators(request):
    rejected_operators = BlacklistedOperator.objects.all().values('wallet')
    # Extracting just the wallet field from each object
    rejected_wallets_list = [operator['wallet'] for operator in rejected_operators]
    print(rejected_wallets_list, "rejected_wallets_list")
    return rejected_wallets_list


@api.get(
    "/blacklisted-providers",
    tags=["Blacklist"],
    summary="Retrieve a list of blacklisted provider node IDs",
    description="""
    This endpoint retrieves a list of node IDs associated with blacklisted providers.
    The response is a list of node IDs that have been blacklisted.
    """,
    response=List[str]
)
def blacklisted_providers(request):
    rejected_providers = BlacklistedProvider.objects.all().values('provider__node_id')
    # Extracting just the provider__node_id field from each object
    rejected_node_ids_list = [provider['provider__node_id'] for provider in rejected_providers]
    return rejected_node_ids_list


@api.post("/task/start",  auth=AuthBearer(), include_in_schema=False,)
def start_task(request, payload: TaskCreateSchema):
    task = Task.objects.create(name=payload.name, started_at=timezone.now())
    return {"id": task.id, "name": task.name, "started_at": task.started_at}

@api.post("/task/end/{task_id}",  auth=AuthBearer(), include_in_schema=False,)
def end_task(request, task_id: int, cost: float):
    try:
        task = Task.objects.get(id=task_id)
    except Task.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Task does not exist"}, status=404)
    task.finished_at = timezone.now()
    task.cost = cost
    task.save()
    return {"id": task.id, "finished_at": task.finished_at}

from django.shortcuts import get_object_or_404

from .schemas import BulkTaskCostUpdateSchema

@api.post("/tasks/update-costs", auth=AuthBearer(), include_in_schema=False,)
def bulk_update_task_costs(request, payload: BulkTaskCostUpdateSchema):
    try:
        task_completions_to_update = []

        for update in payload.updates:
            task_exists = Task.objects.filter(id=update.task_id).exists()
            if not task_exists:
                print(f"Task with ID {update.task_id} not found.")
                continue  # Skip this update

            provider_exists = Provider.objects.filter(node_id=update.provider_id).exists()
            if not provider_exists:
                print(f"Provider with node ID {update.provider_id} not found.")
                continue  # Skip this update

            try:
                task_completion = TaskCompletion.objects.select_related('provider', 'task').get(
                    provider__node_id=update.provider_id, task__id=update.task_id)
                
                # Update the cost
                task_completion.cost = update.cost
                task_completions_to_update.append(task_completion)
            
            except TaskCompletion.DoesNotExist as e:
                print(e)
                print(f"TaskCompletion not found for task ID {update.task_id} and provider ID {update.provider_id}.")
                continue  # Skip this update

        # Bulk update
        if task_completions_to_update:
            TaskCompletion.objects.bulk_update(task_completions_to_update, ['cost'])

        return JsonResponse({"status": "success", "message": "Bulk task cost update completed"})

    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return JsonResponse({"status": "error", "message": "An error occurred"}, status=500)




redis_client = redis.Redis(host='redis', port=6379, db=0)  # Update with your Redis configuration

@api.post("/task/offer/{task_id}", auth=AuthBearer(), include_in_schema=False,)
def store_offer(request, task_id: int):
    try:
        json_data = json.loads(request.body)
        node_id = json_data.get('node_id')
        offer = json_data.get('offer')
        reason = json_data.get('reason', '')  # Default to an empty string if reason is not provided
        accepted = json_data.get('accepted', False)  # Default to False if accepted is not provided

        if not node_id or offer is None:
            return JsonResponse({"status": "error", "error": "Missing node_id or offer"}, status=400)

        # Include reason and accepted in the offer dictionary
        offer_extended = {
            'offer': offer,
            'reason': reason,
            'accepted': accepted
        }

        # Create a unique key for Redis, e.g., using task ID and node ID
        redis_key = f"offer:{task_id}:{node_id}"
        redis_client.set(redis_key, json.dumps(offer_extended))  # Store the extended offer data
    except Exception as e:
        return JsonResponse({"status": "error", "error": str(e)}, status=500)

    return JsonResponse({"status": "success", "message": "Offer stored in Redis"})


@api.get("/benchmark", auth=AuthBearer(), include_in_schema=False,)
def start_benchmark(request):
    # benchmark_providers_task.delay()
    return {"status": "ok"}


from .scoring import get_top_80_percent_cpu_multithread_providers


@api.get(
    "/provider-whitelist",
    tags=["Reputation"],
    summary="Retrieve a whitelist of providers",
    description="""
    This endpoint retrieves a whitelist of providers based on their CPU multi-thread benchmark scores.
    The providers are filtered to include only the top percentage of performers within a specified number of days.

    - If the `paymentNetwork` parameter is 'polygon' or 'mainnet', it fetches the top providers from the mainnet.
    - If the `paymentNetwork` parameter is 'goerli', 'mumbai', or 'holesky', it returns an empty list.
    - If the `paymentNetwork` parameter does not match any of the above, it returns a 404 error.

    The response includes a list of providers who are in the top specified percentage based on their CPU multi-thread benchmark scores.

    Args:
        request: The HTTP request object.
        paymentNetwork (str): The network for which to retrieve the whitelist. 
                              Valid values are 'polygon', 'mainnet', 'goerli', 'mumbai', and 'holesky'.
        topPercent (int): The top percentage of providers to include in the whitelist. Default is 80.
        maxCheckedDaysAgo (int): The maximum number of days ago to consider for the benchmark scores. Default is 3.

    Returns:
        JsonResponse: A JSON response containing the whitelist of providers or an error message.

    Raises:
        JsonResponse: If the network is not found or if the data is not available.

    Example:
        GET /provider-whitelist?paymentNetwork=polygon&topPercent=80&maxCheckedDaysAgo=3
        Response:
        [
            {
                "providerId": "provider1",
                "cpuMultiThreadScore": 95.0
            },
            ...
        ]
    """,
)
def gnv_whitelist(request, paymentNetwork: str = 'polygon', topPercent=80, maxCheckedDaysAgo=3):
    if paymentNetwork == 'polygon' or paymentNetwork == 'mainnet':
        response = get_top_80_percent_cpu_multithread_providers(maxCheckedDaysAgo=maxCheckedDaysAgo, topPercent=topPercent)
    elif paymentNetwork == 'goerli' or paymentNetwork == 'mumbai' or paymentNetwork == 'holesky':
        response = []
    else:
        return JsonResponse({"error": "Network not found"}, status=404)

    if response or response == []:
        return response
    else:
        # Handle the case where data is not yet available in Redis
        return JsonResponse({"error": "Data not available"}, status=503)