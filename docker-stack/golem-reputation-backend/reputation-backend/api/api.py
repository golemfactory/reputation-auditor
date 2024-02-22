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
from .bulkutils import process_disk_benchmark, process_cpu_benchmark, process_memory_benchmark, process_network_benchmark
api = NinjaAPI(
    title="Golem Reputation API",
    version="1.0.0",
    description="API for Golem Reputation Backend",
    urls_namespace="api",
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


@api.get("/providers/scores")
def list_provider_scores(request):
    response = r.get('provider_scores_v1')

    if response:
        return json.loads(response)
    else:
        # Handle the case where data is not yet available in Redis
        return JsonResponse({"error": "Data not available"}, status=503)



@api.post("/benchmark/bulk", auth=AuthBearer())
def create_bulk_benchmark(request, bulk_data: BulkBenchmarkSchema):
    organized_data = {"disk": [], "cpu": [], "memory": [], "network": []}
    for benchmark in bulk_data.benchmarks:
        organized_data[benchmark.type].append(benchmark.data)

    disk_response = process_disk_benchmark(organized_data["disk"])
    cpu_response = process_cpu_benchmark(organized_data["cpu"])
    memory_response = process_memory_benchmark(organized_data["memory"])
    network_response = process_network_benchmark(organized_data["network"])
    
    return {
        "disk": disk_response,
        "cpu": cpu_response,
        "memory": memory_response,
        "network": network_response
    }

    

@api.post("/submit/task/status/bulk", auth=AuthBearer())
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
            ))
        except Exception as e:
            errors.append(f"Error processing item with node_id {item.node_id}: {str(e)}")

    TaskCompletion.objects.bulk_create(task_completion_data)

    if errors:
        return {"status": "error", "message": "Errors occurred during processing", "errors": errors}
    else:
        return {"status": "success", "message": f"Bulk task completion data saved successfully, processed {len(task_completion_data)} items."}



@api.get("scores/task", response=List[ProviderSuccessRate])
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

@api.get("/blacklisted-operators", response=List[str])
def blacklisted_operators(request):
    now = timezone.now()
    recent_tasks = TaskCompletion.objects.filter(
        timestamp__gte=now - timedelta(days=3)  # Adjust the days according to your requirement
    ).values('provider__payment_addresses__golem.com.payment.platform.erc20-mainnet-glm.address').annotate(
        successful_tasks=Count('pk', filter=Q(is_successful=True)),
        total_tasks=Count('pk'),
        success_ratio=Cast('successful_tasks', FloatField()) / Cast('total_tasks', FloatField())
    ).exclude(total_tasks=0)

    success_stats = recent_tasks.aggregate(
        average_success_ratio=Avg('success_ratio'),
        stddev_success_ratio=StdDev('success_ratio')
    )

    avg_success_ratio = success_stats['average_success_ratio']
    stddev_success_ratio = success_stats['stddev_success_ratio']

    operators_with_z_scores = recent_tasks.annotate(
        z_score=(F('success_ratio') - avg_success_ratio) / stddev_success_ratio
    )
    for operator in operators_with_z_scores:
        print(operator)
    
    z_score_threshold = -1
    blacklisted_operators = operators_with_z_scores.filter(
        z_score__lte=z_score_threshold,
        total_tasks__gte=5
    ).values_list(
        'provider__payment_addresses__golem.com.payment.platform.erc20-mainnet-glm.address', flat=True
    ).distinct()

    return list(blacklisted_operators)

@api.get("/blacklisted-providers", response=List[str])
def blacklisted_providers(request):
    now = timezone.now()

    # Subquery to get the most recent tasks for each provider
    recent_tasks = TaskCompletion.objects.filter(
        provider=OuterRef('node_id')
    ).order_by('-timestamp')

    # Annotate each provider with its most recent tasks
    providers_with_tasks = Provider.objects.annotate(
        recent_task=Subquery(recent_tasks.values('is_successful')[:1])
    )

    # Filter providers whose most recent task was a failure
    failed_providers = providers_with_tasks.filter(recent_task=False)

    blacklisted_providers = []
    for provider in failed_providers:
        consecutive_failures = TaskCompletion.objects.filter(
            provider=provider.node_id,
            is_successful=False,
            timestamp__gte=now - timedelta(days=3)  # Assuming we look at the last 3 days
        ).count()

        # Apply a cap to the consecutive_failures
        max_consecutive_failures = 6  # Maximum failures to keep backoff within 14 days
        effective_failures = min(consecutive_failures, max_consecutive_failures)

        backoff_hours = 10 * (2 ** (effective_failures - 1))  # Exponential backoff formula
        next_eligible_date = provider.taskcompletion_set.latest('timestamp').timestamp + timedelta(hours=backoff_hours)

        if now < next_eligible_date:
            blacklisted_providers.append(provider.node_id)

    return blacklisted_providers


@api.post("/task/start",  auth=AuthBearer())
def start_task(request, payload: TaskCreateSchema):
    task = Task.objects.create(name=payload.name, started_at=timezone.now())
    return {"id": task.id, "name": task.name, "started_at": task.started_at}

@api.post("/task/end/{task_id}",  auth=AuthBearer())
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

@api.post("/tasks/update-costs", auth=AuthBearer())
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

@api.post("/task/offer/{task_id}", auth=AuthBearer())
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


@api.get("/benchmark", auth=AuthBearer())
def start_benchmark(request):
    benchmark_providers_task.delay()
    return {"status": "ok"}